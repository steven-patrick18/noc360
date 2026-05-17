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
apt-get install -y asterisk certbot \
  asterisk-modules || apt-get install -y asterisk certbot

log "Issuing TLS certificate for $PBX_HOST (certbot standalone needs :80 free) ..."
if [ ! -f "/etc/letsencrypt/live/$PBX_HOST/fullchain.pem" ]; then
  # Free port 80 momentarily if Asterisk's http is bound there.
  systemctl stop asterisk 2>/dev/null || true
  certbot certonly --standalone --non-interactive --agree-tos -m "$CERT_EMAIL" -d "$PBX_HOST" || {
    err "certbot failed. Ensure DNS $PBX_HOST -> this VPS and port 80 is free, then re-run / click Enable Telephony again."
  }
fi

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
