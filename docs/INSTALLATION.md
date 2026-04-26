# NOC360 Installation

## Server Requirements

- Ubuntu 22.04 or Ubuntu 24.04
- Root or sudo access
- Recommended VPS: 4 GB RAM or higher
- Open inbound HTTP port 80
- Optional domain name for SSL

## One-Line Install

Install NOC360 with demo telecom data:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/steven-patrick18/noc360/main/install.sh) --demo
```

Install without demo data:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/steven-patrick18/noc360/main/install.sh) --no-demo
```

If you already cloned the repository on the server:

```bash
bash install.sh --demo
bash install.sh --no-demo
```

The installer will:

- Install Node.js 20 LTS
- Install Python, Nginx, Git, and Curl
- Clone NOC360 to `/opt/noc360`
- Use the protected SQLite database at `/opt/noc360/backend/noc360.db`
- Install backend dependencies
- Build the frontend with `VITE_API_URL=/api`
- Configure Nginx
- Create and start the `noc360` systemd service
- Verify `/health` and `/api/health`

## Open NOC360

After install:

```text
http://SERVER_IP
```

Default admin login:

```text
admin / admin123
```

Demo customer logins when installed with `--demo`:

```text
im1 / 123
im2 / 123
rolex / 123
```

## Update After Git Push

```bash
bash /opt/noc360/update.sh
```

The updater backs up the database first, fetches the latest code, resets the app code to the selected GitHub branch, updates backend requirements, rebuilds the frontend with `/api`, restarts services, and verifies `/api/health`.

Production update safety:

- `update.sh` does not run `seed.py`.
- `update.sh` does not reset, drop, or delete database tables.
- SQLite backups are written to `/opt/noc360/backend/backups/`.
- The production database path is fixed: `/opt/noc360/backend/noc360.db`.
- The protection marker is `/opt/noc360/backend/.db_protected`.
- On backend startup, NOC360 creates missing tables and adds missing columns only. Existing rows and values are not overwritten.

## Service Commands

Check backend status:

```bash
systemctl status noc360
```

Restart backend:

```bash
systemctl restart noc360
```

Restart Nginx:

```bash
systemctl restart nginx
```

Watch backend logs:

```bash
journalctl -u noc360 -f
```

Check Nginx config:

```bash
nginx -t
```

## Health Checks

Backend directly:

```bash
curl http://127.0.0.1:8000/health
```

Through Nginx:

```bash
curl http://127.0.0.1/api/health
```

Both should return:

```json
{"status":"ok"}
```

## Real User IP in Activity Logs

NOC360 reads `X-Forwarded-For` first, then `X-Real-IP`, then the direct client address. Keep these headers in the Nginx `/api/` proxy block so Activity Logs show the real public IP instead of `127.0.0.1`:

```nginx
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
```

Approximate country, city, and ISP are resolved from public IP only. Local/private IPs are shown as `Local, Internal - Local / Internal`.

The `Upgrade` and long timeout headers are also required for SSH Terminal Center WebSocket sessions.

## Common Errors

### Nginx shows the default page

The frontend build probably failed or the Nginx site is not enabled.

```bash
cd /opt/noc360/frontend
rm -f .env.local
VITE_API_URL=/api npm run build
nginx -t
systemctl restart nginx
```

### Login request failed

Make sure the frontend was built with `/api`:

```bash
grep -R "127.0.0.1:800" /opt/noc360/frontend/dist || true
```

There should be no frontend calls to port `8000`.

Check backend health through Nginx:

```bash
curl http://127.0.0.1/api/health
```

### Node version error

NOC360 requires Node.js 20+.

```bash
node -v
```

Re-run the installer if Node is older.

### Backend does not start

```bash
journalctl -u noc360 -n 100 --no-pager
cat /opt/noc360/backend/.env
```

Check the fixed database file:

```bash
ls -lh /opt/noc360/backend/noc360.db
ls -lh /opt/noc360/backend/.db_protected
```

## Domain and SSL

Point your domain A record to the VPS IP, then update Nginx:

```bash
nano /etc/nginx/sites-available/noc360
```

Change:

```nginx
server_name _;
```

to:

```nginx
server_name yourdomain.com;
```

Install Certbot and enable SSL:

```bash
apt-get update
apt-get install -y certbot python3-certbot-nginx
certbot --nginx -d yourdomain.com
```

Renewal is handled automatically by Certbot.
