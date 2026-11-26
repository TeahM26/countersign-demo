# Countersign: live demo (Flask)

Two-way trust checks for digital-asset payments.
FIS Digital Assets Hackathon 2026, Challenge 1 prototype. All data is synthetic.

## What's in here?

| File | What it does |
|---|---|
| `app.py` | Flask API: decision engine, escrow, rules with versioning and two-person approval, SHA-256 audit chain |
| `index.html` | The demo page (customer view and business console), which calls the API. It can sit next to `app.py` or in a `static` folder. |
| `requirements.txt` | Flask and gunicorn |
| `render.yaml` | One-click settings for Render |

## Quick look with no setup

Double-click `index.html`. With no server running it switches to **Offline mode** (shown top right) and runs
the same engine inside the browser. Everything works except the two-device reviewer link.

## Using the demo

- **Scenarios:** buttons 1–4 in the top bar (or keys 1–4). **R** resets.
- **Two devices:** click **Copy reviewer link** and open it on a second laptop or phone. That device shows only the
  business console. Approve or deny a held payment there, and the customer screen updates within a couple of seconds.
- **Rooms:** add `?room=anything` to the URL to get your own separate copy of the demo (e.g. one per judge).
- **API tab:** shows the real requests and responses. Customer endpoints never return internal reasons or sanctions details.

## API

All endpoints accept `?room=name` (default `demo`).

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/scenarios` | Demo scenarios (merchant, item, payer) |
| POST | `/api/payments` | `{"scenario": "s1"}` → runs the checks, returns the **customer-safe** decision |
| GET | `/api/payments/<id>` | Customer-safe status (used for live updates) |
| POST | `/api/payments/<id>/feedback` | `{"feedback": "self" \| "coached"}` |
| POST | `/api/payments/<id>/review` | `{"approve": true \| false}` → releases or refunds escrow |
| GET | `/api/state` | Full business view: decisions, queue, rules, audit log |
| POST | `/api/rules/propose` | `{"amount": 500, "age_days": 14}` → pending change plus replay on history |
| POST | `/api/rules/approve` / `/api/rules/discard` | Second approver accepts or discards the change |
| GET | `/api/audit/verify` | Recomputes the SHA-256 chain, returns `broken_at` |
| POST | `/api/audit/tamper` | Demo only: edits a stored record so verification fails |
| POST | `/api/reset` | Clears the room |

## Data sources (production versions)

- FCA Financial Services Register API and FCA Warning List (here: cached synthetic snapshot)
- OFAC SDN digital currency addresses, UK Sanctions List, Chainalysis free sanctions API (here: synthetic sample)
- Verified-merchant credentials issued by the payment provider after business checks (here: synthetic)
