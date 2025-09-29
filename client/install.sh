#!/usr/bin/env bash
# Mumblr Client Setup (no server, audio enabled)
set -euo pipefail

REPO_ROOT="$(pwd)"
VENV_DIR="${REPO_ROOT}/.venv"

echo "[1/3] Installing system packages ..."
sudo apt update
sudo apt install -y python3-venv python3-pip portaudio19-dev libportaudio2 libportaudiocpp0

echo "[2/3] Creating Python venv at ${VENV_DIR} ..."
rm -rf "${VENV_DIR}" || true
python3 -m venv "${VENV_DIR}"
# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

echo "[3/3] Installing Python dependencies ..."
pip install --upgrade pip wheel
pip install -r "${REPO_ROOT}/client/requirements_client.txt"

echo
echo "✅ Client ready. Activate with:"
echo "    source ${VENV_DIR}/bin/activate"
echo
echo "Run a client, for example:"
echo "    python3 client/main.py --mode both --host <SERVER_IP> --name node01 --input hw:2,0 --output hw:2,0 --channel 'My Channel'"
