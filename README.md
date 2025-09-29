# Mumblr (with ICE + services)

Mumblr lets you run a **Mumble server** and **unified Python clients** (TX/RX/BOTH) on Raspberry Pis, with **ICE** admin and **systemd** services.

---
## 1) Server (with ICE)
```bash
cd server
./install_server.sh
```
- ICE endpoint: `Meta:tcp -h 127.0.0.1 -p 6502`
- Secret stored in `/etc/mumblr-ice.env` (both read/write set to same value).
- Slice path: `/usr/share/slice/Murmur.ice`

Optional: auto-ensure a channel at boot:
```bash
sudo cp ../systemd/mumblr-ice-ensure.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mumblr-ice-ensure
```
It runs `server/channels_ice.py` using `/etc/mumblr-ice.env`.

---
## 2) Client install
```bash
cd client
./install_client.sh
source .venv/bin/activate
```
Run manually:
```bash
python mumblr_client.py --mode both --host <SERVER_IP> --name node01 --input hw:2,0 --output hw:2,0 --channel "My Channel"
```

---
## 3) Run clients as services (recommended)
Install units:
```bash
cd client
./install_systemd.sh <your-username>   # e.g. pi
```
Create an env file `/home/<user>/mumblur/client/<user>.env` (examples in `client/env.examples`), e.g.:
```
HOST=127.0.0.1
PORT=64738
USER_NAME=node01
MODE=both
ALSA_INPUT=hw:2,0
ALSA_OUTPUT=hw:2,0
TARGET_CHANNEL=My Channel
```
Enable:
```bash
sudo systemctl enable --now mumblr@<user>
journalctl -u mumblr@<user> -f
```

---
## 4) Audio tips
- List devices: `arecord -l` (mic), `aplay -l` (headphones).
- Volume/mute: `alsamixer -c <card>` (e.g., `alsamixer -c 2` for H340).
- Reduce latency: set `FRAME=480` in `client/mumblr_client.py` (10 ms).

---
## 5) Troubleshooting
- No RX audio: check output device name and channel membership.
- No TX audio: check mic device and that it’s unmuted.
- Feedback: use closed-back headphones or separate TX/RX nodes.

Enjoy! 🎧
