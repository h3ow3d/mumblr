#!/usr/bin/env bash
# Mumblr Server Setup (Dependencies only)
# Installs mumble-server, Ice bindings, and Python venv with required packages.
set -euo pipefail

REPO_ROOT="$(pwd)"            # assume you run this from your mumblr repo
VENV_DIR="${REPO_ROOT}/.venv"
SLICE_PATH="/usr/share/slice/Murmur.ice"

# -----------------------------
# 1) Install / enable mumble-server
# -----------------------------
echo "[1/4] Installing mumble-server ..."
sudo apt update
sudo apt install -y mumble-server

echo "[2/4] Enabling and starting mumble-server ..."
sudo systemctl enable --now mumble-server

# -----------------------------
# 2) Install ICE deps for Python and verify Slice
# -----------------------------
echo "[3/4] Installing ICE Python bindings + slice ..."
sudo apt install -y python3-zeroc-ice zeroc-ice-slice

if [ ! -f "$SLICE_PATH" ]; then
  echo "ERROR: ${SLICE_PATH} not found (zeroc-ice-slice should provide it)"
  exit 1
fi

# -----------------------------
# 3) Python venv (system site packages) + pip install
# -----------------------------
echo "[4/4] Setting up Python venv (${VENV_DIR}) ..."
rm -rf "${VENV_DIR}" || true
python3 -m venv "${VENV_DIR}" --system-site-packages
# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

pip install --upgrade pip wheel
pip install -r "${REPO_ROOT}/requirements.txt"

echo "[   ] Verifying Ice and Murmur.ice ..."
python - <<'PY'
import Ice, os
print("Ice OK:", Ice.stringVersion())
p = "/usr/share/slice/Murmur.ice"
print("Has Murmur.ice:", os.path.exists(p), p)
PY

echo
echo "✅ Dependencies ready. Activate with:"
echo "    source ${VENV_DIR}/bin/activate"
echo "Then run your script, e.g.:"
echo "    python3 server/main.py"
in