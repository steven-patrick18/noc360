#!/bin/bash

set -e

APP_DIR="/opt/noc360"
REPO="https://github.com/steven-patrick18/noc360.git"
DB_NAME="noc360"
DB_USER="nocuser"
DB_PASS="noc360pass123"

echo "🚀 Installing NOC360..."

apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git nginx postgresql postgresql-contrib curl

# Node install
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs

# PostgreSQL setup
sudo -u postgres psql <<EOF
DROP DATABASE IF EXISTS $DB_NAME;
DROP USER IF EXISTS $DB_USER;
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';
ALTER DATABASE $DB_NAME OWNER TO $DB_USER;
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOF

# Clone project
rm -rf $APP_DIR
git clone $REPO $APP_DIR

# Backend setup
cd $APP_DIR/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# ENV
cat > .env <<EOF
DATABASE_URL=postgresql://$DB_USER:$DB_PASS@localhost/$DB_NAME
SECRET_KEY=$(openssl rand -hex 32)
ENV=production
EOF

# Seed data
python seed.py --reset || true

# Service
cat > /etc/systemd/system/noc360.service <<EOF
[Unit]
Description=NOC360 Backend
After=network.target postgresql.service

[Service]
User=root
WorkingDirectory=$APP_DIR/backend
ExecStart=$APP_DIR/backend/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable noc360
systemctl restart noc360

# Frontend
cd $APP_DIR/frontend
npm install
npm run build

# Nginx
cat > /etc/nginx/sites-available/noc360 <<EOF
server {
    listen 80;
    server_name _;

    root $APP_DIR/frontend/dist;
    index index.html;

    location / {
        try_files \$uri /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
    }
}
EOF

rm -f /etc/nginx/sites-enabled/default
ln -s /etc/nginx/sites-available/noc360 /etc/nginx/sites-enabled/

nginx -t
systemctl restart nginx

echo "✅ NOC360 Installed Successfully"
echo "🌐 Open: http://YOUR_SERVER_IP"
echo "👤 Admin: admin / admin123"