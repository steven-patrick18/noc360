# NOC360

NOC360 is a FastAPI + React Vite telecom NOC dashboard for VOS portals, dialer clusters, RDP/media servers, and routing gateways.

## Backend

```powershell
cd backend
venv\Scripts\activate
pip install -r requirements.txt
python seed.py --reset
python -m uvicorn main:app --reload
```

The API runs locally on `http://localhost:8000`. SQLite is used by default. If `DATABASE_URL` exists, the backend uses it, which makes the same code ready for PostgreSQL on Render.

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

The dashboard runs on `http://localhost:5173` and talks to the local backend. Set `VITE_API_URL` if the API is hosted somewhere else.

## Render

`render.yaml` is included. Backend start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Features

- VOS Portal Master is the source of truth for RDP/media and RTNG inventory.
- Management Portal is the main assignment page for cluster accounts, RDP-to-cluster assignment, and RTNG media mapping.
- Customer Billing Portal with role-based login, ledger billing, customer-only data scoping, and CSV exports.
- Demo seed reset: `cd backend` then `python seed.py --reset`.
- Seed logins: `admin / admin123`, `noc / noc123`, `viewer / viewer123`, `im1 / 123`, `im2 / 123`, `rolex / 123`.
- RDP / Media Servers is generated from VOS records whose `portal_type` starts with `RDP`; only assignment fields are edited there.
- Routing Gateway Manager selects `RTNG*` gateways and `RDP*` media servers from VOS Portal Master and auto-fills IPs.
- Prevents assigning the same active RDP to multiple active clusters.
- Auto-fills `assigned_rdp_ip` from the selected VOS RDP portal.
- Dashboard alerts for duplicate assignments and missing IP values including `#N/A`.
- Search, status dropdowns, RDP assignment dropdown, CSV export, and seeded telecom sample data.
