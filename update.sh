#!/usr/bin/env bash
set -Eeuo pipefail

trap 'echo "ERROR: NOC360 update failed at line $LINENO. Check the output above and retry." >&2' ERR

APP_DIR="/opt/noc360"
BACKUP_DIR="${APP_DIR}/backend/backups"
TIMESTAMP="$(date +%F_%H%M)"

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: update.sh must be run as root. Use: sudo bash /opt/noc360/update.sh" >&2
  exit 1
fi

if [[ ! -d "${APP_DIR}/.git" ]]; then
  echo "ERROR: ${APP_DIR} is not a git checkout. Was NOC360 installed with install.sh?" >&2
  exit 1
fi

echo "==> Backing up database before update"
mkdir -p "${BACKUP_DIR}"
if [[ -f "${APP_DIR}/backend/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${APP_DIR}/backend/.env"
  set +a
fi

backup_sqlite_file() {
  local source_file="$1"
  if [[ -f "${source_file}" ]]; then
    cp "${source_file}" "${BACKUP_DIR}/noc360_before_update_${TIMESTAMP}.db"
    echo "SQLite backup: ${BACKUP_DIR}/noc360_before_update_${TIMESTAMP}.db"
  fi
}

backup_sqlite_file "${APP_DIR}/backend/noc360.db"

if [[ "${DATABASE_URL:-}" == sqlite:///* ]]; then
  SQLITE_PATH="${DATABASE_URL#sqlite:///}"
  if [[ "${SQLITE_PATH}" != /* ]]; then
    SQLITE_PATH="${APP_DIR}/backend/${SQLITE_PATH}"
  fi
  backup_sqlite_file "${SQLITE_PATH}"
elif [[ "${DATABASE_URL:-}" == postgresql://* || "${DATABASE_URL:-}" == postgres://* ]]; then
  if ! command -v pg_dump >/dev/null 2>&1; then
    echo "ERROR: pg_dump is required to back up PostgreSQL before update." >&2
    exit 1
  fi
  pg_dump "${DATABASE_URL}" > "${BACKUP_DIR}/noc360_before_update_${TIMESTAMP}.sql"
  echo "PostgreSQL backup: ${BACKUP_DIR}/noc360_before_update_${TIMESTAMP}.sql"
fi

echo "==> Updating NOC360"
cd "${APP_DIR}"
BRANCH="${NOC360_BRANCH:-main}"
git fetch origin "${BRANCH}"
git reset --hard "origin/${BRANCH}"

echo "==> Updating backend requirements"
cd "${APP_DIR}/backend"
"${APP_DIR}/backend/venv/bin/python" -m pip install --upgrade pip
"${APP_DIR}/backend/venv/bin/pip" install -r requirements.txt
systemctl restart noc360
echo "==> Backend restarted. Startup will create missing tables/columns only; no seed/reset is run."

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
for i in {1..10}; do
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null || curl -fsS http://127.0.0.1:8000/health >/dev/null; then
    echo "NOC360 update complete."
    exit 0
  fi
  sleep 2
done

echo "ERROR: backend health failed after 10 attempts. Tried http://127.0.0.1:8000/api/health and /health. Run: journalctl -u noc360 -f" >&2
exit 1
