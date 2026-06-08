#!/bin/bash
# Rokct Protocol Installer (UNIX)
# Usage: curl -sSL https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/install.sh | bash

set -euo pipefail

PROTOCOL_RAW="https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main"

echo "[install] Rokct Protocol Setup"
echo "Select profile:"
echo "  1) Local (desktop/CLI)"
echo "  2) Web (cloud sandbox / AI agent)"
read -r -p "Enter 1 or 2: " choice

case "$choice" in
1 | "") PROFILE="local" ;;
2) PROFILE="web" ;;
*)
  echo "[install] Invalid choice"
  exit 1
  ;;
esac

INIT_FILE="profiles/$PROFILE/initiate.py"

if ! command -v python3 &>/dev/null; then
  echo "[install] ERROR: python3 is required but not installed." >&2
  exit 1
fi

mkdir -p .rokct

echo "[install] Fetching $PROFILE initiate.py from protocol..."
curl -fsSL "$PROTOCOL_RAW/$INIT_FILE" -o ".rokct/initiate.py"

echo "[install] Running init..."
python3 .rokct/initiate.py

echo "[install] Done. Run 'python .rokct/end_protocol.py' when session ends."
