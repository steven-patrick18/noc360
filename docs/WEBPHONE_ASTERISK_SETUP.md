# NOC360 Webphone Asterisk WebRTC Gateway Setup

This guide prepares an Asterisk WebRTC gateway for NOC360 DID test calls.

Flow:

```text
NOC360 Webphone -> WSS/WebRTC -> Asterisk -> SIP trunk/VOS/carrier -> DID
```

## Server Requirements

- Ubuntu 22.04 or 24.04
- Asterisk 18 or 20 with PJSIP
- Public DNS name, for example `pbx.domain.com`
- Valid TLS certificate from Certbot/Let's Encrypt
- Firewall open:
  - TCP `8089` for WSS
  - UDP `10000-20000` for RTP

## Install Basics

```bash
apt update
apt install -y asterisk certbot
certbot certonly --standalone -d pbx.domain.com
```

Replace `pbx.domain.com` in the examples below with your real PBX hostname.

## `/etc/asterisk/http.conf`

```ini
[general]
enabled=yes
bindaddr=0.0.0.0
bindport=8088
tlsenable=yes
tlsbindaddr=0.0.0.0:8089
tlscertfile=/etc/letsencrypt/live/pbx.domain.com/fullchain.pem
tlsprivatekey=/etc/letsencrypt/live/pbx.domain.com/privkey.pem
```

## `/etc/asterisk/rtp.conf`

```ini
[general]
rtpstart=10000
rtpend=20000
icesupport=yes
stunaddr=stun.l.google.com:19302
```

## `/etc/asterisk/pjsip.conf`

```ini
[transport-wss]
type=transport
protocol=wss
bind=0.0.0.0

[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0

[1001]
type=endpoint
transport=transport-wss
context=from-webphone
disallow=all
allow=opus,ulaw,alaw
auth=1001-auth
aors=1001
webrtc=yes
use_avpf=yes
media_encryption=dtls
dtls_verify=fingerprint
dtls_setup=actpass
ice_support=yes
rtcp_mux=yes
direct_media=no
force_rport=yes
rewrite_contact=yes

[1001]
type=aor
max_contacts=5
remove_existing=yes

[1001-auth]
type=auth
auth_type=userpass
username=1001
password=change_this_password

; Placeholder trunk to VOS/carrier. Update host, auth, codecs, and routing.
[vos_trunk]
type=endpoint
transport=transport-udp
context=from-vos
disallow=all
allow=ulaw,alaw
aors=vos_trunk
direct_media=no
from_domain=pbx.domain.com

[vos_trunk]
type=aor
contact=sip:VOS_OR_CARRIER_IP:5060
```

## `/etc/asterisk/extensions.conf`

```ini
[from-webphone]
exten => _X.,1,NoOp(Webphone DID test)
 same => n,Dial(PJSIP/${EXTEN}@vos_trunk,60)
 same => n,Hangup()
```

## Reload Asterisk

```bash
asterisk -rx "module reload res_http_websocket.so"
asterisk -rx "module reload res_pjsip.so"
asterisk -rx "core reload"
asterisk -rx "http show status"
asterisk -rx "pjsip show endpoint 1001"
```

## NOC360 Profile Example

Create a Webphone profile in NOC360:

- Profile Name: `Asterisk DID Test`
- SIP Username: `1001`
- SIP Password: `change_this_password`
- WebSocket URL: `wss://pbx.domain.com:8089/ws`
- SIP Domain: `pbx.domain.com`
- CLI: your test caller ID

## Troubleshooting

- Registration fails: confirm `wss://pbx.domain.com:8089/ws` opens from the browser and certificate is valid.
- Microphone denied: allow microphone permission in the browser site settings.
- No audio: verify RTP UDP `10000-20000` is open and `icesupport=yes`.
- Calls fail: run `asterisk -rvvv`, place a test call, and inspect PJSIP dialplan/trunk errors.
- Browser only supports WebRTC WSS. UDP/TCP SIP cannot run directly inside the browser.
