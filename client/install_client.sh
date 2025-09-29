#!/usr/bin/env bash
set -euo pipefail
echo "[Mumblr] Installing client dependencies ..."
sudo apt update
sudo apt install -y python3-venv python3-pip libportaudio2 libopus0
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip wheel
pip install pymumble sounddevice numpy
echo "[Mumblr] Client ready. Activate with: source $(pwd)/.venv/bin/activate"
