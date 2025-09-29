#!/usr/bin/env bash
set -euo pipefail
USER_NAME="${1:-$USER}"

echo "[Mumblr] Installing systemd units ..."
sudo cp ../systemd/mumblr@.service /etc/systemd/system/mumblr@.service
sudo cp ../systemd/mumblr-ice-ensure.service /etc/systemd/system/mumblr-ice-ensure.service
sudo systemctl daemon-reload

echo
echo "To run a client instance at boot for user '${USER_NAME}':"
echo "  1) Create /home/${USER_NAME}/mumblur/client/${USER_NAME}.env (see client/env.examples)"
echo "  2) sudo systemctl enable --now mumblr@${USER_NAME}"
echo "  3) View logs: journalctl -u mumblr@${USER_NAME} -f"
echo
echo "To run ICE channel ensure at boot (optional):"
echo "  - Make sure /etc/mumblr-ice.env exists (created by server/install_server.sh)"
echo "  - sudo systemctl enable --now mumblr-ice-ensure"
