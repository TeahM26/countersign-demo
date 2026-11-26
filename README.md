# Countersign live demo (Flask)

Two way trust checks for digital money payments. Both sides are checked before money moves, and both see the decision and the reason.
FIS Digital Assets Hackathon 2026, Challenge 1 prototype. All data is synthetic.

## What's in here

| File | What it does |
|---|---|
| `app.py` | Flask API with the decision engine, escrow, versioned rules with two person approval, and a SHA256 audit chain |
| `index.html` | The demo page. The shopper view, and the Countersign console as used by Northwind Pay, the payment processor. It calls the API, and runs the same engine in the browser when no server is found. |
| `requirements.txt` | Flask and gunicorn |
| `render.yaml` | Settings for Render |

## Run it

First time only, from the project folder:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then each time:

```
source .venv/bin/activate
python app.py
```

Open http://localhost:5050. (Port 5050, because macOS uses 5000 for AirPlay Receiver.) You can also double click `index.html` with no server and everything works except the reviewer link.

## Scenarios

All four are crypto payments in GBPx, a synthetic pound stablecoin, made on a normal online shop. Press 1 to 4 or use the top bar. The page opens on scenario 1. Picking a scenario clears the decisions and review queue so each run starts clean. R resets everything.

| Key | Scenario | What happens |
|---|---|---|
| 1 | Normal payment | £180 from a connected exchange account to a verified merchant. Approved straight away |
| 2 | Clone site | £5,000 to a fake copy of an FCA authorised firm. Blocked, and the shopper is told why |
| 3 | Held for review | £2,400 from a wallet created 2 days ago. Held in escrow while Northwind Pay reviews it |
| 4 | Sanctioned wallet | £320 from a wallet on a sanctions list. Blocked. The shopper only sees a neutral message |

## Review flow (scenario 3)

1. The shopper is asked whether anyone told them to make the payment. Their answer appears in the console straight away.
2. The reviewer can deny and refund, or approve and release.
3. Approving needs the reviewer to accept liability: if the funds turn out to be fraudulent, the business carries the loss. The API refuses an approval without `accept_liability: true`, and the acceptance is written to the audit log.

## Two devices

Use the link button in the console header and open it on a second laptop or phone. That device shows only the console. Add `?room=anything` to the URL for a separate copy of the demo.

## API

All endpoints accept `?room=name` (default `demo`).

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/scenarios` | Demo scenarios (merchant, item, payer, rail) |
| POST | `/api/payments` | `{"scenario": "s1"}` runs the checks and returns the shopper safe decision |
| GET | `/api/payments/<id>` | Shopper safe status, used for live updates |
| POST | `/api/payments/<id>/feedback` | `{"feedback": "self" \| "coached"}` |
| POST | `/api/payments/<id>/review` | `{"approve": true, "accept_liability": true}` releases, `{"approve": false}` refunds |
| POST | `/api/session/clear` | Clears decisions and the review queue. Rules and the audit log stay |
| GET | `/api/state` | Full business view with decisions, queue, rules and audit log |
| POST | `/api/rules/propose` | `{"amount": 500, "age_days": 14}` proposes a change and replays it on history |
| POST | `/api/rules/approve` and `/api/rules/discard` | Second approver accepts or discards the change |
| GET | `/api/audit/verify` | Recomputes the SHA256 chain and returns `broken_at` |
| POST | `/api/audit/tamper` | Demo only. Edits a stored record so verification fails |
| POST | `/api/reset` | Clears the room |

## Data sources (production versions)

- FCA Financial Services Register API and FCA Warning List (here a cached synthetic snapshot)
- OFAC SDN digital currency addresses, UK Sanctions List, Chainalysis free sanctions API (here a synthetic sample)
- Verified merchant credentials issued after business checks (here synthetic)
