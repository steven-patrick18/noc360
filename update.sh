#!/usr/bin/env bash
set -Eeuo pipefail

trap 'echo "ERROR: NOC360 update failed at line $LINENO. Check the output above and retry." >&2' ERR

APP_DIR="/opt/noc360"

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: update.sh must be run as root. Use: sudo bash /opt/noc360/update.sh" >&2
  exit 1
fi

if [[ ! -d "${APP_DIR}/.git" ]]; then
  echo "ERROR: ${APP_DIR} is not a git checkout. Was NOC360 installed with install.sh?" >&2
  exit 1
fi

echo "==> Updating NOC360"
cd "${APP_DIR}"
git pull --ff-only

echo "==> Updating backend requirements"
cd "${APP_DIR}/backend"
"${APP_DIR}/backend/venv/bin/python" -m pip install --upgrade pip
"${APP_DIR}/backend/venv/bin/pip" install -r requirements.txt
systemctl restart noc360

echo "==> Rebuilding frontend"
cd "${APP_DIR}/frontend"
rm -f .env.local
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
VITE_API_URL=/api npm run build
test -f "${APP_DIR}/frontend/dist/index.html"

echo "==> Restarting Nginx"
nginx -t
systemctl restart nginx

echo "==> Verifying health"
for i in {1..30}; do
  if curl -fsS http://127.0.0.1/api/health >/dev/null; then
    echo "NOC360 update complete."
    exit 0
  fi
  sleep 2
done

echo "ERROR: /api/health failed after update. Run: journalctl -u noc360 -f" >&2
exit 1
