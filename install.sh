#!/bin/bash
# Rokct Protocol Installer (Unix/macOS/Linux)
# Usage: curl -sSL https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/install.sh | bash

set -e

PROTOCOL_DIR="The-Rokct-Protocol"
REPO_URL="https://github.com/RokctAI/The-Rokct-Protocol.git"

echo "[install] Rokct Protocol Setup (Workspace Mode)"

if ! command -v git &> /dev/null; then
    echo "[install] ERROR: git is required but not installed."
    exit 1
fi

if [ ! -d "$PROTOCOL_DIR" ]; then
    echo "[install] Cloning The-Rokct-Protocol..."
    git clone --depth 1 "$REPO_URL" "$PROTOCOL_DIR"
else
    echo "[install] The-Rokct-Protocol already exists, pulling latest..."
    git -C "$PROTOCOL_DIR" pull --ff-only
fi

echo "[install] Running local workspace init..."
cd "$PROTOCOL_DIR"
python3 profiles/local/initiate.py

echo "[install] Done. Run 'python .rokct/end_protocol.py' when session ends."
