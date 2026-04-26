# Asterisk WebRTC Gateway for NOC360 Webphone

This guide sets up `pbx.voipzap.com` on the same VPS as the NOC360 production server.

Target flow:

```text
noc360.voipzap.com Webphone -> WSS/WebRTC -> pbx.voipzap.com Asterisk -> SIP trunk/VOS -> DID
```

The browser must use secure WebRTC over `wss://`. UDP/TCP SIP is not supported from the browser.

## 1. Install Asterisk Manually

NOC360 does not install Asterisk and does not ask for a root password. A server admin should install Asterisk once on the VPS, then use NOC360 Webphone -> PBX Setup to write the known WebRTC configuration templates.

```bash
apt update
apt install -y asterisk certbot
```

## 2. DNS

Point this DNS record to the VPS public IP:

```text
pbx.voipzap.com -> SERVER_IP
```

## 3. SSL Certificate

Stop anything temporarily using ports `80/443` if needed, then issue the cert:

```bash
certbot certonly --standalone -d pbx.voipzap.com
```

Certificate paths used below:

```text
/etc/letsencrypt/live/pbx.voipzap.com/fullchain.pem
/etc/letsencrypt/live/pbx.voipzap.com/privkey.pem
```

## 4. Firewall

Allow WSS and RTP:

```bash
ufw allow 8089/tcp
ufw allow 10000:20000/udp
ufw allow 5060/udp
```

After this manual install and SSL step, open NOC360 -> Webphone -> PBX Setup. Use the simplified flow: Connect, then Enable WebRTC. NOC360 will write the known WebRTC templates, attach the SSL certificate paths, restart Asterisk, and create the browser Webphone profile.

## 5. `/etc/asterisk/http.conf`

The PBX Setup tab can generate this known template after Asterisk and SSL are installed.

```ini
[general]
enabled=yes
bindaddr=0.0.0.0
bindport=8088
tlsenable=yes
tlsbindaddr=0.0.0.0:8089
tlscertfile=/etc/letsencrypt/live/pbx.voipzap.com/fullchain.pem
tlsprivatekey=/etc/letsencrypt/live/pbx.voipzap.com/privkey.pem
```

## 6. `/etc/asterisk/rtp.conf`

```ini
[general]
rtpstart=10000
rtpend=20000
icesupport=yes
stunaddr=stun.l.google.com:19302
```

## 7. `/etc/asterisk/pjsip.conf`

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
context=webphone-test
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
password=CHANGE_STRONG_PASSWORD

; Replace this placeholder with your VOS/carrier trunk.
[your_trunk]
type=endpoint
transport=transport-udp
context=from-trunk
disallow=all
allow=ulaw,alaw
aors=your_trunk
direct_media=no

[your_trunk]
type=aor
contact=sip:VOS_OR_CARRIER_IP:5060
```

## 8. `/etc/asterisk/extensions.conf`

```ini
[webphone-test]
exten => _X.,1,NoOp(NOC360 Webphone DID Test)
 same => n,Dial(PJSIP/${EXTEN}@your_trunk)
 same => n,Hangup()
```

## 9. Reload and Verify

```bash
systemctl restart asterisk
asterisk -rx "http show status"
asterisk -rx "pjsip show endpoint 1001"
asterisk -rx "pjsip show transports"
```

Expected WebSocket URL for NOC360:

```text
wss://pbx.voipzap.com:8089/ws
```

## 10. NOC360 Webphone Profile

Create this profile in NOC360:

```text
Profile Name: pbx.voipzap.com DID Test
SIP Username: 1001
SIP Password: CHANGE_STRONG_PASSWORD
WebSocket URL: wss://pbx.voipzap.com:8089/ws
SIP Domain: pbx.voipzap.com
CLI: your test caller ID
```

## Troubleshooting

- If registration fails, verify the certificate and that `wss://pbx.voipzap.com:8089/ws` is reachable.
- If the browser blocks calling, allow microphone access for `noc360.voipzap.com`.
- If there is no audio, verify UDP RTP ports `10000-20000` are open.
- If calls do not route, run `asterisk -rvvv` and inspect the `webphone-test` dialplan and `your_trunk` status.
