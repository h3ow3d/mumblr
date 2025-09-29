#!/usr/bin/env bash
set -euo pipefail

INI="/etc/mumble-server.ini"
ICE_HOST="${ICE_HOST:-127.0.0.1}"
ICE_PORT="${ICE_PORT:-6502}"
CHANNEL_DEFAULT="${CHANNEL_DEFAULT:-My Channel}"

echo "[Mumblr] Installing Mumble server + ICE ..."
sudo apt update
sudo apt install -y mumble-server zeroc-ice-slice

echo "[Mumblr] Backing up ${INI} ..."
if [ ! -f "${INI}.bak" ]; then
  sudo cp "${INI}" "${INI}.bak"
fi

echo "[Mumblr] Configuring ICE endpoint and secrets ..."
SECRET="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p -c 64)"

# Set ICE endpoint
if grep -qE '^ice=' "$INI"; then
  sudo sed -i "s|^ice=.*|ice=\"tcp -h ${ICE_HOST} -p ${ICE_PORT}\"|g" "$INI"
else
  echo "ice=\"tcp -h ${ICE_HOST} -p ${ICE_PORT}\"" | sudo tee -a "$INI" >/dev/null
fi

# Ensure secrets (same for read/write for simplicity)
sudo sed -i -E '/^icesecret(read|write)=/d' "$INI"
{
  echo "icesecretread=${SECRET}"
  echo "icesecretwrite=${SECRET}"
} | sudo tee -a "$INI" >/dev/null

echo "[Mumblr] Restarting service ..."
sudo systemctl restart mumble-server
sudo systemctl enable mumble-server >/dev/null

# Prepare an env file for the ICE ensure service
ICE_ENV="/etc/mumblr-ice.env"
sudo bash -c "cat > ${ICE_ENV}" <<EOF
ICE_ENDPOINT=Meta:tcp -h ${ICE_HOST} -p ${ICE_PORT}
ICE_SECRET=${SECRET}
TARGET_CHANNEL=${CHANNEL_DEFAULT}
SLICE=/usr/share/slice/Murmur.ice
EOF
sudo chmod 0644 "${ICE_ENV}"

echo
echo "✅ Mumble server installed with ICE."
echo "   ICE endpoint: Meta:tcp -h ${ICE_HOST} -p ${ICE_PORT}"
echo "   Secret stored in: ${ICE_ENV}"
echo
echo "Optional: to auto-ensure a channel at boot,"
echo "  1) copy the systemd units:   sudo cp systemd/mumblr-ice-ensure.service /etc/systemd/system/"
echo "  2) enable the service:       sudo systemctl enable --now mumblr-ice-ensure"
echo
echo "Done."
