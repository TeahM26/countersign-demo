"""
Countersign. Two way trust checks for digital money payments.
FIS Digital Assets Hackathon 2026, Challenge 1 prototype.

A small Flask API that holds the decision engine, escrow state, rules and
a hash chained audit log. index.html calls this API.

All data is synthetic. State is kept in memory per "room" (?room=name),
so each team or judge can run their own copy of the demo.
Run:  python app.py   then open http://localhost:5050
"""
import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static", static_url_path="/static")
LOCK = threading.Lock()

PROVIDER = "Northwind Pay"  # the payment processor whose compliance team uses the Countersign console
REVIEWER = "A. Patel"
SECOND_APPROVER = "J. Okafor"

# --------------------------------------------------------------------------
# Synthetic reference data (stand ins for the real public sources)
# --------------------------------------------------------------------------
DATA = {
    # In production: FCA Financial Services Register API
    "fca_register": [
        {"frn": "812345", "name": "Harbour & Finch Investments Ltd", "status": "Authorised",
         "domain": "harbourfinch.co.uk", "wallet": "0x4f1c9a07b2e5d6c3a8f0e1b2c3d4e5f6a7b888d2",
         "phone": "020 7946 0321"},
    ],
    # In production: FCA Warning List
    "warning_list": [
        {"domain": "harbour-finch-invest.com", "note": "Clone of FCA authorised firm (FRN 812345)", "added": "14 Nov 2026"},
    ],
    # In production: OFAC SDN digital currency addresses, UK Sanctions List, Chainalysis free API
    "sanctions": [
        {"wallet": "0x8e21d4c0aa13f9b7e65c2d90f1a3b4c5d6e7f0a9", "ref": "SDN-SYN-0042", "list": "OFAC SDN (synthetic sample)"},
    ],
    # Verified merchant credentials, issued by the payment provider after business checks (KYB)
    "credentials": {
        "0x9b2e77f1c0d3a4b5e6f708192a3b4c5d6e7fc41a": {"holder": "Lumen Coffee Roasters Ltd", "issuer": "Northwind Pay", "status": "valid", "expires": "30 Jun 2027"},
        "0x6d4a19c2b8e7f0a1d3c5e7f9a2b4c6d8e0f1a3c7": {"holder": "Kiln Homeware Ltd", "issuer": "Northwind Pay", "status": "valid", "expires": "31 Jan 2027"},
        "0x2ac5b9e8f7d6c5b4a3928170f6e5d4c3b2a17e3b": {"holder": "Atlas Electronics Ltd", "issuer": "Northwind Pay", "status": "valid", "expires": "31 Mar 2027"},
    },
}

LUMEN = {"name": "Lumen Coffee Roasters", "domain": "lumencoffee.co.uk", "path": "/checkout",
         "wallet": "0x9b2e77f1c0d3a4b5e6f708192a3b4c5d6e7fc41a", "claims_frn": None,
         "color": "#3B2418", "accent": "#A8602F"}
KILN = {"name": "Kiln Homeware", "domain": "kilnhomeware.co.uk", "path": "/checkout",
        "wallet": "0x6d4a19c2b8e7f0a1d3c5e7f9a2b4c6d8e0f1a3c7", "claims_frn": None,
        "color": "#2F3A2E", "accent": "#5E7552"}
ATLAS = {"name": "Atlas Electronics", "domain": "atlas-electronics.co.uk", "path": "/checkout",
         "wallet": "0x2ac5b9e8f7d6c5b4a3928170f6e5d4c3b2a17e3b", "claims_frn": None,
         "color": "#111318", "accent": "#2E3440"}
CLONE = {"name": "Harbour & Finch Investments", "domain": "harbour-finch-invest.com", "path": "/deposit",
         "wallet": "0x13ab7c6d5e4f30214a5b6c7d8e9f0a1b2c3dff02", "claims_frn": "812345",
         "phone": "0161 555 0199", "color": "#0B3D2E", "accent": "#1E7A57", "financial": True}

# Every demo scenario is a crypto (stablecoin) payment. The engine also supports rail "cbdc" for later.
# payer.type: "bank" (digital pound wallet at a bank), "exchange" (connected exchange account),
#             "self" (self custody wallet)
SCENARIOS = {
    "s1": {"label": "Normal payment", "rail": "stablecoin", "asset": "GBPx", "group": "Crypto",
           "merchant": dict(KILN),
           "item": {"title": "Stoneware dinner set", "variant": "12 pieces, oat glaze", "art": "bowl",
                    "desc": "Thrown in Stoke on Trent. Dishwasher safe.", "price": 180},
           "payer": {"name": "Kestrel Exchange", "provider": "Connected exchange account", "type": "exchange",
                     "network": "Ethereum", "wallet": "0x51d0a3b2c4e5f60718293a4b5c6d7e8f9a0b11e9",
                     "age_days": 420, "balance": 1240}},
    "s2": {"label": "Clone site", "rail": "stablecoin", "asset": "GBPx", "group": "Crypto",
           "merchant": dict(CLONE),
           "item": {"title": "Fixed yield bond", "variant": "12% a year, guaranteed", "art": "bond",
                    "desc": "Limited allocation closes tonight. Deposit in GBPx to secure your place.", "price": 5000},
           "payer": {"name": "Kestrel Exchange", "provider": "Connected exchange account", "type": "exchange",
                     "network": "Ethereum", "wallet": "0x51d0a3b2c4e5f60718293a4b5c6d7e8f9a0b11e9",
                     "age_days": 420, "balance": 6200}},
    "s3": {"label": "Held for review", "rail": "stablecoin", "asset": "GBPx", "group": "Crypto",
           "merchant": dict(ATLAS),
           "item": {"title": "UltraBook Pro 14", "variant": "32GB, 1TB, Graphite", "art": "laptop",
                    "desc": "14 inch OLED, 22 hour battery. Free next day delivery.", "price": 2400},
           "payer": {"name": "Self custody wallet", "provider": "Browser wallet", "type": "self",
                     "network": "Ethereum", "wallet": "0x7f3e2d1c0b9a8f7e6d5c4b3a29180f7e6d5c90b4",
                     "age_days": 2, "balance": 2650}},
    "s4": {"label": "Sanctioned wallet", "rail": "stablecoin", "asset": "GBPx", "group": "Crypto",
           "merchant": dict(ATLAS),
           "item": {"title": "Studio headphones X5", "variant": "Adaptive noise cancelling", "art": "headphones",
                    "desc": "40 hour battery. Folds flat.", "price": 320},
           "payer": {"name": "Self custody wallet", "provider": "Browser wallet", "type": "self",
                     "network": "Ethereum", "wallet": "0x8e21d4c0aa13f9b7e65c2d90f1a3b4c5d6e7f0a9",
                     "age_days": 160, "balance": 900}},
}

# Synthetic history used to replay a proposed rule change
HISTORY = [
    ("TX-0981", "Atlas Electronics", 1850, 3), ("TX-0982", "Lumen Coffee Roasters", 38, 600),
    ("TX-0983", "Atlas Electronics", 650, 1), ("TX-0984", "Brightside Travel", 1200, 45),
    ("TX-0985", "Atlas Electronics", 780, 5), ("TX-0986", "Kiln Homeware", 96, 220),
    ("TX-0987", "Brightside Travel", 2300, 12), ("TX-0988", "Atlas Electronics", 940, 4),
    ("TX-0989", "Kiln Homeware", 540, 2), ("TX-0990", "Lumen Coffee Roasters", 22, 30),
    ("TX-0991", "Atlas Electronics", 1499, 6), ("TX-0992", "Brightside Travel", 860, 9),
    ("TX-0993", "Kiln Homeware", 310, 1), ("TX-0994", "Atlas Electronics", 2100, 300),
    ("TX-0995", "Brightside Travel", 700, 3), ("TX-0996", "Atlas Electronics", 1100, 8),
]
HISTORY = [{"id": i, "merchant": m, "amount": a, "age_days": d} for i, m, a, d in HISTORY]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def short(w):
    return w[:6] + "…" + w[-4:] if w.startswith("0x") else w


def gbp(n):
    return f"£{n:,.0f}" if float(n).is_integer() else f"£{n:,.2f}"


# --------------------------------------------------------------------------
# State (one per room)
# --------------------------------------------------------------------------
ROOMS = {}
MAX_ROOMS = 200


def fresh_state():
    st = {"ruleset": [1, 4], "params": {"amount": 1000, "age_days": 7}, "pending": None,
          "tx_seq": 1041, "decisions": [], "queue": [], "audit": [], "rev": 0}
    audit(st, "LEDGER_INIT", "system",
          f"Ruleset {rs_ver(st)} loaded · FCA Register and Warning List snapshot cached · sanctions list (synthetic sample) loaded")
    return st


def room_name():
    return re.sub(r"[^a-zA-Z0-9_-]", "", request.args.get("room", "demo"))[:40] or "demo"


def get_room():
    name = room_name()
    if name not in ROOMS:
        if len(ROOMS) >= MAX_ROOMS:
            ROOMS.pop(next(iter(ROOMS)))
        ROOMS[name] = fresh_state()
    return ROOMS[name]


def rs_ver(st):
    return f"v{st['ruleset'][0]}.{st['ruleset'][1]}"


# --------------------------------------------------------------------------
# Audit log: each entry stores the SHA256 of the previous one
# --------------------------------------------------------------------------
def entry_hash(e):
    payload = json.dumps([e["seq"], e["ts"], e["event"], e["actor"], e["detail"], e["ruleset"], e["prev"]],
                         ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def audit(st, event, actor, detail):
    prev = st["audit"][-1]["hash"] if st["audit"] else "0" * 64
    e = {"seq": len(st["audit"]) + 1, "ts": now_iso(), "event": event, "actor": actor,
         "detail": detail, "ruleset": rs_ver(st), "prev": prev}
    e["hash"] = entry_hash(e)
    st["audit"].append(e)
    st["rev"] += 1


def verify_chain(st):
    prev = "0" * 64
    for e in st["audit"]:
        if e["prev"] != prev or entry_hash(e) != e["hash"]:
            return e["seq"]
        prev = e["hash"]
    return None


# --------------------------------------------------------------------------
# Rules (policy as code). Each cites its source.
# --------------------------------------------------------------------------
def rules(st):
    p = st["params"]
    return [
        {"id": "R1", "name": "Regulated firm impersonation", "outcome": "DENY",
         "cond": "Payee claims to be an FCA authorised firm but its domain or wallet does not match the FCA Register, "
                 "or the domain is on the FCA Warning List.",
         "src": "FCA Financial Services Register API · FCA Warning List"},
        {"id": "R2", "name": "Sanctions screening", "outcome": "DENY",
         "cond": "Payer or payee wallet matches a sanctions list entry. The shopper only sees a neutral message, "
                 "to avoid tipping off.",
         "src": "OFAC SDN digital currency addresses · UK Sanctions List · Chainalysis free sanctions API"},
        {"id": "R3", "name": "Merchant credential", "outcome": "HOLD",
         "cond": "Payee wallet has no valid verified merchant credential.",
         "src": "Countersign credential registry, issued by Northwind Pay after business checks (KYB)"},
        {"id": "R4", "name": "New wallet, high value", "outcome": "HOLD", "editable": True,
         "cond": f"Payer wallet younger than {p['age_days']} days and amount over £{p['amount']:,}.",
         "src": "Internal risk policy · supports PSR APP scam reimbursement and FCA Consumer Duty"},
    ]


# --------------------------------------------------------------------------
# Decision engine
# --------------------------------------------------------------------------
def evaluate(st, tx):
    m, p, amount = tx["merchant"], tx["payer"], tx["amount"]
    bank_payer = tx["rail"] == "cbdc"
    checks, fired = [], []

    # 1. Merchant credential
    cred = DATA["credentials"].get(m["wallet"])
    if cred and cred["status"] == "valid":
        checks.append({"t": "Merchant credential", "s": "pass",
                       "d": f"Verified by {cred['issuer']} after business checks, valid to {cred['expires']}"})
    else:
        checks.append({"t": "Merchant credential", "s": "fail", "d": "No verified merchant credential for this wallet"})
        fired.append({"id": "R3", "outcome": "HOLD",
                      "internal": f"Payee wallet {short(m['wallet'])} has no credential in the registry.",
                      "business": "Payee is not a verified merchant.",
                      "consumer": "This seller hasn't been verified."})

    # 2. FCA Register (only when the payee claims to be a regulated firm)
    r1 = []
    if m.get("claims_frn"):
        firm = next((f for f in DATA["fca_register"] if f["frn"] == m["claims_frn"]), None)
        if firm and firm["domain"] == m["domain"] and firm["wallet"] == m["wallet"]:
            checks.append({"t": "FCA Register", "s": "pass", "d": f"{firm['name']}, FRN {firm['frn']}, {firm['status']}"})
        else:
            checks.append({"t": "FCA Register", "s": "fail",
                           "d": f"Claims to be {firm['name']} (FRN {firm['frn']}), but the web address and wallet "
                                f"don't match the FCA record"})
            r1.append(f"Claims FRN {firm['frn']} ({firm['name']}). Register domain {firm['domain']} ≠ {m['domain']}; "
                      f"register wallet {short(firm['wallet'])} ≠ payee {short(m['wallet'])}; "
                      f"register phone {firm['phone']} ≠ site phone {m.get('phone')}.")
    else:
        checks.append({"t": "FCA Register", "s": "na", "d": "Not offering regulated financial services, so not needed"})

    # 3. FCA Warning List
    warn = next((w for w in DATA["warning_list"] if w["domain"] == m["domain"]), None)
    if warn:
        checks.append({"t": "FCA Warning List", "s": "fail", "d": f"Listed {warn['added']}. {warn['note']}"})
        r1.append(f"Domain on FCA Warning List since {warn['added']} ({warn['note']}).")
    else:
        checks.append({"t": "FCA Warning List", "s": "pass", "d": "Not listed"})

    if r1:
        firm = DATA["fca_register"][0]
        fired.append({"id": "R1", "outcome": "DENY", "internal": " ".join(r1),
                      "business": "Payee is impersonating an FCA authorised firm. The clone is on the FCA Warning List.",
                      "consumer": f"This site is copying {firm['name']}, a firm authorised by the FCA. Its web address "
                                  f"and wallet don't match the FCA record, and the FCA has warned about it."})

    # 4. Sanctions. For digital pound payments the payer was screened by their bank, so only the payee is screened.
    if bank_payer:
        hit = next((s for s in DATA["sanctions"] if s["wallet"] == m["wallet"]), None)
    else:
        hit = next((s for s in DATA["sanctions"] if s["wallet"] in (p["wallet"], m["wallet"])), None)
    if hit:
        checks.append({"t": "Sanctions screening", "s": "fail", "d": "Screening did not clear"})
        fired.append({"id": "R2", "outcome": "DENY", "sensitive": True,
                      "internal": f"Wallet {short(hit['wallet'])} matches {hit['list']} entry {hit['ref']}.",
                      "business": "Payer wallet matches a sanctions list. Do not tell the customer why (tipping off "
                                  "risk). Escalate to the MLRO.",
                      "consumer": "We can't complete this payment. Please contact your wallet provider."})
    elif bank_payer:
        checks.append({"t": "Sanctions screening", "s": "inherit",
                       "d": f"Payer screened by {p.get('provider', 'their bank')}. Payee clear"})
    else:
        checks.append({"t": "Sanctions screening", "s": "pass", "d": "Payer and payee wallets clear"})

    # 5. Payer risk (R4). Not repeated for bank held digital pound wallets (R5).
    prm = st["params"]
    if bank_payer:
        checks.append({"t": "Payer risk", "s": "inherit",
                       "d": f"Identity and account history held by {p.get('provider', 'their bank')}"})
        fired_r5 = {"id": "R5", "outcome": "INHERIT",
                    "internal": f"Digital pound wallet at {p.get('provider')}. Payer KYC, sanctions and risk inherited.",
                    "business": "Payer checks covered by the issuing bank.", "consumer": ""}
        tx["inherited"] = fired_r5
    elif p["age_days"] < prm["age_days"] and amount > prm["amount"]:
        checks.append({"t": "Payer risk", "s": "warn", "d": f"Wallet is {p['age_days']} days old and sending {gbp(amount)}"})
        fired.append({"id": "R4", "outcome": "HOLD",
                      "internal": f"Payer wallet age {p['age_days']} days (< {prm['age_days']}) and amount "
                                  f"{gbp(amount)} (> {gbp(prm['amount'])}).",
                      "business": "First large payment from a brand new self custody wallet. This pattern is common in "
                                  "account takeover and in scams where someone coaches the victim to pay.",
                      "consumer": "This is a large payment from a wallet that's only a few days old, so we're taking "
                                  "a quick extra look before it's sent."})
    else:
        checks.append({"t": "Payer risk", "s": "pass", "d": f"Wallet {p['age_days']} days old, amount within normal pattern"})

    if any(f["outcome"] == "DENY" for f in fired):
        outcome = "DENY"
        fired = [f for f in fired if f["outcome"] == "DENY"]  # deny reasons take precedence
    elif any(f["outcome"] == "HOLD" for f in fired):
        outcome = "HOLD"
    else:
        outcome = "APPROVE"
    return {"outcome": outcome, "checks": checks, "fired": fired,
            "sensitive": any(f.get("sensitive") for f in fired)}


# --------------------------------------------------------------------------
# Views: the consumer only ever receives consumer safe fields
# --------------------------------------------------------------------------
def safe_checks(r):
    """Never show the shopper that sanctions screening failed (tipping off)."""
    if not r["sensitive"]:
        return r["checks"]
    return [{"t": "Wallet checks", "s": "na", "d": "Couldn't be completed"} if c["t"] == "Sanctions screening" else c
            for c in r["checks"]]


def consumer_view(tx):
    r = tx["result"]
    return {
        "id": tx["id"], "amount": tx["amount"], "asset": tx["asset"], "rail": tx["rail"],
        "merchant": tx["merchant"]["name"],
        "outcome": r["outcome"], "status": tx["status"], "reviewed": tx.get("reviewed", False),
        "sensitive": r["sensitive"], "checks": safe_checks(r),
        "messages": [f["consumer"] for f in r["fired"]],
        "escrow": tx.get("escrow"), "feedback": tx.get("feedback"), "ruleset": tx["ruleset"],
    }


def replay(params):
    return [h["id"] for h in HISTORY if h["age_days"] < params["age_days"] and h["amount"] > params["amount"]]


def business_state(st):
    pend = None
    if st["pending"]:
        before, after = replay(st["params"]), replay(st["pending"])
        pend = {**st["pending"], "before": len(before), "after": len(after), "total": len(HISTORY),
                "added": [i for i in after if i not in before], "removed": [i for i in before if i not in after]}
    return {"rev": st["rev"], "ruleset": rs_ver(st), "params": st["params"], "rules": rules(st), "pending": pend,
            "provider": PROVIDER, "reviewer": REVIEWER, "decisions": list(reversed(st["decisions"])), "queue": st["queue"],
            "audit": list(reversed(st["audit"]))}


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.get("/")
def index():
    # Works with index.html in a "static" folder or next to app.py
    folder = os.path.join(BASE_DIR, "static")
    if not os.path.exists(os.path.join(folder, "index.html")):
        folder = BASE_DIR
    return send_from_directory(folder, "index.html")


@app.get("/healthz")
def health():
    return {"ok": True}


@app.get("/api/scenarios")
def api_scenarios():
    return jsonify(SCENARIOS)


@app.get("/api/state")
def api_state():
    with LOCK:
        return jsonify(business_state(get_room()))


@app.post("/api/payments")
def api_create_payment():
    body = request.get_json(silent=True) or {}
    sc = SCENARIOS.get(body.get("scenario"))
    if not sc:
        return {"error": "unknown scenario"}, 400
    with LOCK:
        st = get_room()
        tx_id = f"TX-{st['tx_seq']}"
        st["tx_seq"] += 1
        tx = {"id": tx_id, "merchant": sc["merchant"], "payer": sc["payer"], "amount": sc["item"]["price"],
              "asset": sc["asset"], "rail": sc["rail"], "ts": now_iso(), "ruleset": rs_ver(st)}
        audit(st, "PAYMENT_INITIATED", "customer",
              f"{tx_id} · {gbp(tx['amount'])} {tx['asset']} · {short(tx['payer']['wallet'])} → {sc['merchant']['name']} "
              f"({short(sc['merchant']['wallet'])})")
        res = evaluate(st, tx)
        tx["result"], tx["status"] = res, res["outcome"]
        st["decisions"].append(tx)
        fired_ids = [f["id"] for f in res["fired"]] + (["R5"] if tx.get("inherited") else [])
        audit(st, "DECISION", "engine",
              f"{tx_id} · {res['outcome']} · rules fired: {', '.join(fired_ids) or 'none'} · "
              f"{' '.join(f['internal'] for f in res['fired']) or 'All checks passed.'}"
              + (f" {tx['inherited']['internal']}" if tx.get("inherited") else ""))
        if res["outcome"] == "HOLD":
            tx["escrow"] = {"addr": "0xe5c0" + hashlib.sha256(tx_id.encode()).hexdigest()[:34], "state": "Locked"}
            st["queue"].append(tx_id)
            audit(st, "ESCROW_LOCKED", "engine",
                  f"{tx_id} · {gbp(tx['amount'])} {tx['asset']} locked in escrow {short(tx['escrow']['addr'])}")
        return jsonify(consumer_view(tx)), 201


def find_tx(st, tx_id):
    return next((t for t in st["decisions"] if t["id"] == tx_id), None)


@app.get("/api/payments/<tx_id>")
def api_get_payment(tx_id):
    with LOCK:
        tx = find_tx(get_room(), tx_id)
        return (jsonify(consumer_view(tx)), 200) if tx else ({"error": "not found"}, 404)


@app.post("/api/payments/<tx_id>/feedback")
def api_feedback(tx_id):
    f = (request.get_json(silent=True) or {}).get("feedback")
    if f not in ("self", "coached"):
        return {"error": "feedback must be 'self' or 'coached'"}, 400
    with LOCK:
        st = get_room()
        tx = find_tx(st, tx_id)
        if not tx or tx["status"] != "HOLD":
            return {"error": "payment is not on hold"}, 409
        tx["feedback"] = f
        tx["feedback_ts"] = now_iso()
        audit(st, "CUSTOMER_RESPONSE", "customer",
              f"{tx_id} · " + ("Customer says they are making this payment themselves" if f == "self"
                               else "Customer says someone asked them to make this payment (possible coaching)"))
        return jsonify(consumer_view(tx))


@app.post("/api/payments/<tx_id>/review")
def api_review(tx_id):
    body = request.get_json(silent=True) or {}
    approve = bool(body.get("approve"))
    with LOCK:
        st = get_room()
        tx = find_tx(st, tx_id)
        if not tx or tx["status"] != "HOLD":
            return {"error": "payment is not on hold"}, 409
        if approve and not body.get("accept_liability"):
            return {"error": "approving needs the reviewer to accept liability for the funds"}, 400
        tx["status"], tx["reviewed"] = ("APPROVE" if approve else "DENY"), True
        tx["escrow"]["state"] = "Released to merchant" if approve else "Refunded to payer"
        st["queue"] = [i for i in st["queue"] if i != tx_id]
        fb = {"self": "customer said they made it themselves", "coached": "customer said someone asked them to pay"}
        audit(st, "REVIEW_DECISION", f"reviewer: {REVIEWER}",
              f"{tx_id} · {'APPROVED' if approve else 'DENIED'} after review · "
              + (fb[tx['feedback']] if tx.get("feedback") else "no customer response"))
        if approve:
            tx["liability"] = {"by": REVIEWER, "ts": now_iso()}
            audit(st, "LIABILITY_ACCEPTED", f"reviewer: {REVIEWER}",
                  f"{tx_id} · {gbp(tx['amount'])} {tx['asset']} · the business accepts liability if these funds "
                  f"prove to be fraudulent"
                  + (" · approved against the customer's coaching report" if tx.get("feedback") == "coached" else ""))
        audit(st, "ESCROW_RELEASED" if approve else "ESCROW_REFUNDED", "engine",
              f"{tx_id} · {gbp(tx['amount'])} {tx['asset']} "
              + (f"released to {tx['merchant']['name']}" if approve else "returned to payer"))
        return jsonify(consumer_view(tx))


@app.post("/api/session/clear")
def api_clear():
    """Starts a fresh scenario: clears decisions and the review queue. Rules and the audit log stay."""
    with LOCK:
        st = get_room()
        st["decisions"], st["queue"] = [], []
        st["rev"] += 1
        return jsonify(business_state(st))


@app.post("/api/rules/propose")
def api_propose():
    body = request.get_json(silent=True) or {}
    try:
        amount, age = max(0, int(body.get("amount"))), max(0, int(body.get("age_days")))
    except (TypeError, ValueError):
        return {"error": "amount and age_days must be whole numbers"}, 400
    with LOCK:
        st = get_room()
        if amount == st["params"]["amount"] and age == st["params"]["age_days"]:
            return {"error": "no change"}, 400
        st["pending"] = {"amount": amount, "age_days": age, "by": REVIEWER}
        audit(st, "RULE_CHANGE_PROPOSED", REVIEWER,
              f"R4: amount £{st['params']['amount']} → £{amount}; wallet age {st['params']['age_days']} → {age} days")
        return jsonify(business_state(st))


@app.post("/api/rules/approve")
def api_approve_rule():
    with LOCK:
        st = get_room()
        if not st["pending"]:
            return {"error": "nothing pending"}, 409
        old = dict(st["params"])
        st["params"] = {"amount": st["pending"]["amount"], "age_days": st["pending"]["age_days"]}
        st["pending"] = None
        st["ruleset"][1] += 1
        audit(st, "RULE_CHANGE_APPROVED", f"{SECOND_APPROVER} (second approver)",
              f"R4 now: amount over £{st['params']['amount']}, wallet younger than {st['params']['age_days']} days "
              f"(was £{old['amount']}, {old['age_days']} days). Ruleset → {rs_ver(st)}")
        return jsonify(business_state(st))


@app.post("/api/rules/discard")
def api_discard_rule():
    with LOCK:
        st = get_room()
        if st["pending"]:
            st["pending"] = None
            audit(st, "RULE_CHANGE_DISCARDED", REVIEWER, "Pending R4 change discarded")
        return jsonify(business_state(st))


@app.get("/api/audit/verify")
def api_verify():
    with LOCK:
        st = get_room()
        return jsonify({"broken_at": verify_chain(st), "entries": len(st["audit"])})


@app.post("/api/audit/tamper")
def api_tamper():
    """Demo only: edits a stored record without updating its hash."""
    with LOCK:
        st = get_room()
        target = next((e for e in st["audit"] if e["event"] == "DECISION" and re.search("DENY|HOLD", e["detail"])), None) \
            or next((e for e in st["audit"] if e["event"] == "DECISION"), None) or st["audit"][0]
        target["detail"] = re.sub("DENY|HOLD", "APPROVE", target["detail"], count=1) + " [edited]"
        st["rev"] += 1
        return jsonify({"edited": target["seq"], "broken_at": verify_chain(st)})


@app.post("/api/reset")
def api_reset():
    with LOCK:
        name = room_name()
        ROOMS[name] = fresh_state()
        return jsonify(business_state(ROOMS[name]))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5050)), debug=False, threaded=True)
