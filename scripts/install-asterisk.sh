#!/usr/bin/env bash
#
# NOC360 Asterisk auto-installer for the Webphone telephony engine.
#
# Installs Asterisk + PJSIP/WebRTC modules + certbot, issues a Let's Encrypt
# TLS cert (browsers require wss://), opens the firewall, and enables the
# service. NOC360 then writes the WebRTC gateway + carriers from
# Webphone -> PBX Setup -> Enable Telephony. Idempotent.
#
# Auto (called by the backend "Enable Telephony" button):
#   sudo PBX_HOST=pbx.example.com CERT_EMAIL=admin@example.com \
#        bash scripts/install-asterisk.sh --yes
#
set -euo pipefail

YES="${1:-}"
log() { echo "[noc360-ast] $*"; }
err() { echo "[noc360-ast] $*" >&2; }

if [ "$(id -u)" -ne 0 ]; then
  err "Run as root: sudo bash scripts/install-asterisk.sh"
  exit 1
fi

ask() {
  local __var="$1" __prompt="$2" __def="${3:-}" __cur
  __cur="$(eval "echo \${$__var:-}")"
  if [ -n "$__cur" ]; then return; fi
  if [ "$YES" = "--yes" ]; then eval "$__var=\"$__def\""; return; fi
  read -r -p "$__prompt [$__def]: " __ans || true
  eval "$__var=\"${__ans:-$__def}\""
}

ask PBX_HOST   "WebRTC/PBX hostname (must resolve to this VPS)" "pbx.voipzap.com"
ask CERT_EMAIL "Email for the Let's Encrypt cert"               "admin@${PBX_HOST#pbx.}"

log "Host=$PBX_HOST"

export DEBIAN_FRONTEND=noninteractive
log "Installing Asterisk + certbot ..."
apt-get update -y
# asterisk-modules carries res_pjsip_transport_websocket (WSS for the
# browser softphone). It must NOT be dropped, so install it explicitly and
# fail loudly rather than silently falling back without it.
apt-get install -y asterisk asterisk-modules certbot
if ! dpkg -s asterisk-modules >/dev/null 2>&1; then
  err "asterisk-modules failed to install; the browser softphone (WSS) will not work."
fi

log "Hardening modules.conf for WebRTC (PJSIP WSS) ..."
MODCONF="/etc/asterisk/modules.conf"
if [ -f "$MODCONF" ]; then
  # chan_sip grabs the 'sip' WebSocket subprotocol first, making
  # res_pjsip_transport_websocket decline to load. NOC360 is PJSIP-only,
  # so disable chan_sip and preload the websocket deps for clean ordering.
  grep -q '^noload => chan_sip.so' "$MODCONF"            || sed -i '/^\[modules\]/a noload => chan_sip.so' "$MODCONF"
  grep -q '^preload => res_http_websocket.so' "$MODCONF" || sed -i '/^\[modules\]/a preload => res_http_websocket.so' "$MODCONF"
fi

log "Issuing TLS certificate for $PBX_HOST ..."
if [ ! -f "/etc/letsencrypt/live/$PBX_HOST/fullchain.pem" ]; then
  CERT_OK=""
  WEBROOT="/opt/noc360/frontend/dist"
  # Preferred: webroot challenge served by the already-running nginx. NOC360's
  # own UI is on :80 here, so standalone can never bind it -- webroot avoids
  # the fight entirely (no nginx/asterisk downtime).
  if systemctl is-active --quiet nginx && [ -d "$WEBROOT" ]; then
    log "Trying webroot challenge via nginx ($WEBROOT) ..."
    certbot certonly --webroot -w "$WEBROOT" --non-interactive --agree-tos \
      -m "$CERT_EMAIL" -d "$PBX_HOST" && CERT_OK=1 || true
  fi
  # Fallback: standalone on a momentarily-free :80 (dedicated PBX box, or if
  # the webroot attempt failed). Stop nginx+asterisk, then restore nginx.
  if [ -z "$CERT_OK" ]; then
    log "Webroot unavailable/failed; trying standalone (frees :80 briefly) ..."
    systemctl stop asterisk 2>/dev/null || true
    NGINX_WAS_UP=""
    if systemctl is-active --quiet nginx; then NGINX_WAS_UP=1; systemctl stop nginx 2>/dev/null || true; fi
    certbot certonly --standalone --non-interactive --agree-tos -m "$CERT_EMAIL" -d "$PBX_HOST" && CERT_OK=1 || true
    [ -n "$NGINX_WAS_UP" ] && { systemctl start nginx 2>/dev/null || true; }
  fi
  if [ -z "$CERT_OK" ]; then
    err "certbot failed for $PBX_HOST. Most common cause: the DNS A-record for $PBX_HOST is not pointing at this VPS yet. Verify with:  dig +short $PBX_HOST   vs   curl -s ifconfig.me   -- then click Enable Telephony again."
  fi
fi

log "Installing certbot deploy hook (keeps Asterisk's cert copy fresh on renewal) ..."
HOOK_DIR="/etc/letsencrypt/renewal-hooks/deploy"
mkdir -p "$HOOK_DIR"
cat > "$HOOK_DIR/noc360-asterisk.sh" <<HOOK
#!/usr/bin/env bash
# Managed by NOC360. Copies the renewed LE cert into an asterisk-readable
# location and reloads Asterisk so WSS keeps working after renewals.
set -e
LIVE="/etc/letsencrypt/live/$PBX_HOST"
KEYS="/etc/asterisk/keys"
[ -f "\$LIVE/fullchain.pem" ] || exit 0
mkdir -p "\$KEYS"
cp "\$LIVE/fullchain.pem" "\$KEYS/noc360-fullchain.pem"
cp "\$LIVE/privkey.pem"   "\$KEYS/noc360-privkey.pem"
chown -R asterisk:asterisk "\$KEYS" 2>/dev/null || true
chmod 750 "\$KEYS"; chmod 644 "\$KEYS/noc360-fullchain.pem"; chmod 640 "\$KEYS/noc360-privkey.pem"
systemctl reload asterisk 2>/dev/null || systemctl restart asterisk 2>/dev/null || true
HOOK
chmod +x "$HOOK_DIR/noc360-asterisk.sh"

log "Opening firewall (ufw) for WSS + RTP ..."
if command -v ufw >/dev/null 2>&1; then
  ufw allow 8089/tcp            || true
  ufw allow 10000:20000/udp     || true
  ufw allow 5060/udp            || true
fi

log "Persisting PBX host for the backend ..."
ENV_FILE="/opt/noc360/backend/.env"
if [ -f "$ENV_FILE" ] && ! grep -q "NOC360_PBX_DOMAIN=" "$ENV_FILE"; then
  echo "NOC360_PBX_DOMAIN=$PBX_HOST" >> "$ENV_FILE"
fi

systemctl enable asterisk 2>/dev/null || true
systemctl restart asterisk 2>/dev/null || true
sleep 2
log "Asterisk install step finished. NOC360 will now write the WebRTC config."
