# NOC360

NOC360 is a FastAPI + React Vite telecom NOC command dashboard for VOS portals, dialer clusters, RDP/media nodes, routing gateways, client billing, reports, and business intelligence.

## Installation

Quick install on Ubuntu 22.04/24.04:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/steven-patrick18/noc360/main/install.sh) --demo
```

Open:

```text
http://SERVER_IP
```

Default login:

```text
admin / admin123
```

Update after pushing new code:

```bash
bash /opt/noc360/update.sh
```

Full install guide: [docs/INSTALLATION.md](docs/INSTALLATION.md)

## Local Backend

```powershell
cd backend
venv\Scripts\activate
pip install -r requirements.txt
python seed.py --reset
python -m uvicorn main:app --reload
```

The local API runs on `http://127.0.0.1:8000`. SQLite is used by default. If `DATABASE_URL` exists, the backend uses PostgreSQL.

## Local Frontend

```powershell
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`. For production builds, use:

```bash
VITE_API_URL=/api npm run build
```

Do not commit `frontend/.env.local`.

## Render

`render.yaml` is included. Backend start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Features

- VOS Portal Master is the source of truth for RDP/media and RTNG inventory.
- Management Portal controls cluster/client, RDP-to-cluster, and RTNG media mappings.
- Client billing ledger with USD/INR totals, payments, outstanding, reports, and customer-only access.
- Business AI billing intelligence dashboard.
- User Access page with page/action permissions.
- RDP/media and routing validation with duplicate/missing alerts.
- Demo seed reset: `cd backend` then `python seed.py --reset`.
- Seed logins: `admin / admin123`, `noc / noc123`, `viewer / viewer123`, `im1 / 123`, `im2 / 123`, `rolex / 123`.
