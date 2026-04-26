#!/usr/bin/env bash
set -Eeuo pipefail

trap 'echo "ERROR: NOC360 install failed at line $LINENO. Check the output above and retry." >&2' ERR

APP_DIR="/opt/noc360"
DB_PATH="${APP_DIR}/backend/noc360.db"
REPO_URL="${NOC360_REPO_URL:-https://github.com/steven-patrick18/noc360.git}"
BRANCH="${NOC360_BRANCH:-main}"
RUN_DEMO="false"

usage() {
  echo "Usage: bash install.sh [--demo|--no-demo]"
}

for arg in "$@"; do
  case "$arg" in
    --demo) RUN_DEMO="true" ;;
    --no-demo) RUN_DEMO="false" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; usage; exit 1 ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: install.sh must be run as root. Use: sudo bash install.sh --demo" >&2
  exit 1
fi

echo "==> Installing NOC360"
echo "==> Demo data: ${RUN_DEMO}"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl gnupg git nginx python3 python3-pip python3-venv openssl

echo "==> Installing Node.js 20 LTS"
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs
NODE_MAJOR="$(node -p "process.versions.node.split('.')[0]")"
if [[ "${NODE_MAJOR}" -lt 20 ]]; then
  echo "ERROR: Node.js 20+ is required, found $(node -v)" >&2
  exit 1
fi

systemctl stop noc360 2>/dev/null || true

echo "==> Cloning NOC360 to ${APP_DIR}"
if [[ -f "${DB_PATH}" ]]; then
  echo "ERROR: Existing database found at ${DB_PATH}. Use update.sh instead of install.sh to protect live data." >&2
  exit 1
fi
if [[ -d "${APP_DIR}" ]]; then
  rm -rf "${APP_DIR}"
fi
git clone --branch "${BRANCH}" "${REPO_URL}" "${APP_DIR}"

echo "==> Configuring backend"
cd "${APP_DIR}/backend"
python3 -m venv venv
"${APP_DIR}/backend/venv/bin/python" -m pip install --upgrade pip
"${APP_DIR}/backend/venv/bin/pip" install -r requirements.txt

SECRET_KEY="$(openssl rand -hex 32)"
cat > "${APP_DIR}/backend/.env" <<EOF
DATABASE_URL=sqlite:////opt/noc360/backend/noc360.db
SECRET_KEY=${SECRET_KEY}
ENV=production
EOF
chmod 600 "${APP_DIR}/backend/.env"
touch "${APP_DIR}/backend/.db_protected"

if [[ "${RUN_DEMO}" == "true" ]]; then
  echo "==> Loading demo data into empty protected database"
  "${APP_DIR}/backend/venv/bin/python" seed.py
fi

echo "==> Creating systemd service"
cat > /etc/systemd/system/noc360.service <<EOF
[Unit]
Description=NOC360 Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}/backend
EnvironmentFile=${APP_DIR}/backend/.env
ExecStart=${APP_DIR}/backend/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable noc360
systemctl restart noc360

echo "==> Building frontend"
cd "${APP_DIR}/frontend"
rm -f .env.local
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
VITE_API_URL=/api npm run build
test -f "${APP_DIR}/frontend/dist/index.html"

echo "==> Configuring Nginx"
cat > /etc/nginx/sites-available/noc360 <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    root ${APP_DIR}/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

rm -f /etc/nginx/sites-enabled/default
ln -sfn /etc/nginx/sites-available/noc360 /etc/nginx/sites-enabled/noc360
nginx -t
systemctl restart nginx

echo "==> Verifying backend health"
for i in {1..30}; do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null && curl -fsS http://127.0.0.1/api/health >/dev/null; then
    break
  fi
  if [[ "$i" -eq 30 ]]; then
    echo "ERROR: health check failed. Run: journalctl -u noc360 -f" >&2
    exit 1
  fi
  sleep 2
done

SERVER_IP="$(hostname -I | awk '{print $1}')"
SERVER_IP="${SERVER_IP:-SERVER_IP}"

echo
echo "NOC360 Installed Successfully"
echo "Open: http://${SERVER_IP}"
echo "Admin Login: admin / admin123"
echo "Database: ${DB_PATH}"
echo "Backend: systemctl status noc360"
echo "Logs: journalctl -u noc360 -f"
echo "Update: bash ${APP_DIR}/update.sh"
