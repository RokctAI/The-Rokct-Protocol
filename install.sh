#!/bin/bash
# Rokct Protocol Installer (UNIX)
# Usage: curl -sSL https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/install.sh | bash

set -euo pipefail

PROTOCOL_RAW="https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main"
INIT_PATH="profiles/local/initiate.py"

echo "[install] Rokct Protocol Setup (Standalone)"

if ! command -v python3 &> /dev/null; then
    echo "[install] ERROR: python3 is required but not installed." >&2
    exit 1
fi

mkdir -p .rokct

echo "[install] Fetching initiate.py from protocol..."
curl -fsSL "$PROTOCOL_RAW/$INIT_PATH" -o ".rokct/initiate.py"

echo "[install] Running init..."
python3 .rokct/initiate.py

echo "[install] Done. Run 'python .rokct/end_protocol.py' when session ends."
