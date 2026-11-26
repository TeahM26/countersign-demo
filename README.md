# Countersign: live demo (Flask)

Two-way trust checks for digital-asset payments.
FIS Digital Assets Hackathon 2026, Challenge 1 prototype. All data is synthetic.

## What's in here

| File | What it does |
|---|---|
| `app.py` | Flask API: decision engine, escrow, rules with versioning and two-person approval, SHA-256 audit chain |
| `index.html` | The demo page (customer view and business console), which calls the API. It can sit next to `app.py` or in a `static` folder. |
| `requirements.txt` | Flask and gunicorn |
| `render.yaml` | One-click settings for Render |

## Quick look with no setup

Double-click `index.html`. With no server running it switches to **Offline mode** (shown top right) and runs
the same engine inside the browser. Everything works except the two-device reviewer link.

## Run it on your laptop with the real backend (2 minutes)

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

## Put it online

The app keeps demo data in memory, so it must run as **one process** (the settings below already do this).
If the server restarts, the demo simply starts fresh.

### Option A: PythonAnywhere (free, no GitHub needed, about 10 minutes)

1. Sign up for a free "Beginner" account at pythonanywhere.com.
2. Go to the **Web** tab → **Add a new web app** → **Flask** → pick the newest Python version.
   Keep the suggested path, e.g. `/home/YOURNAME/mysite/flask_app.py`.
3. Go to the **Files** tab → open `/home/YOURNAME/mysite/`:
   - Upload `app.py` and `index.html`.
4. Back on the **Web** tab, click the **WSGI configuration file** link. Change the last line from
   `from flask_app import app as application` to
   `from app import app as application` and click **Save**.
5. Click the green **Reload** button. Your site is live at `https://YOURNAME.pythonanywhere.com`.

### Option B: Render (free, needs a GitHub account, about 10 minutes)

1. Create a new GitHub repository and upload all the files in this folder.
2. On render.com → **New** → **Blueprint** → choose the repo. Render reads `render.yaml` and deploys.
   (Or **New** → **Web Service** with build command `pip install -r requirements.txt` and start command
   `gunicorn app:app --workers 1 --threads 8 --bind 0.0.0.0:$PORT`, instance type **Free**.)
3. Your site is live at `https://countersign-demo.onrender.com` (or similar).

Render's free plan sleeps after about 15 minutes without visitors, and the first visit then takes up to a minute.
**Open the link 5 minutes before you present.**

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
