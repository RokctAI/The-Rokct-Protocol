#!/bin/bash

# Rokct Protocol Installer (Bash)
# Usage: curl -sSL https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/install.sh | bash

set -e

# Pinned by tools/gen_protocol_lock.py - do not edit these constants by hand.
# The initiate.py fetch is pinned to this commit and its SHA-256 is verified
# before it is executed; a mismatch aborts the install.
PROTOCOL_REF="7cc8f36286b29c093478063095fb4dc6a03878b5"
INITIATE_SHA256_LOCAL="a144ca9325cb2f223a9f719d2de0fdd07e65eef862a28e4ebdfd4faafffe4f43"
INITIATE_SHA256_WEB="dd950edd61c15fe10f34a11e71078fb842d8d6d0310d1a195db802f44bf5ec0b"

PROTOCOL_RAW="https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/$PROTOCOL_REF"

echo "[install] Rokct Protocol Setup"
echo "Are you a Human or an Agent?"
echo "  H) Human"
echo "  A) Agent"
read -p "Enter H or A: " USER_TYPE

if [[ "$USER_TYPE" == "H" ]]; then
  ROKCT_PROFILE="local"
elif [[ "$USER_TYPE" == "A" ]]; then
  echo "Select Agent profile:"
  echo "  1) Web (cloud sandbox / AI agent)"
  read -p "Enter 1: " CHOICE
  ROKCT_PROFILE="web"
else
  echo "[install] Invalid input. Defaulting to Local."
  ROKCT_PROFILE="local"
fi

INIT_FILE="profiles/$ROKCT_PROFILE/initiate.py"
if [[ "$ROKCT_PROFILE" == "web" ]]; then
  INITIATE_SHA256="$INITIATE_SHA256_WEB"
else
  INITIATE_SHA256="$INITIATE_SHA256_LOCAL"
fi

if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
  echo "[install] ERROR: python is required but not installed."
  exit 1
fi

# Determine python command
PYTHON_CMD=$(command -v python3 || command -v python)

mkdir -p .rokct

echo "[install] Fetching $ROKCT_PROFILE initiate.py from protocol (ref $PROTOCOL_REF)..."
# BEGIN fetch-and-verify (tests/test_install.sh replaces this block with a local copy)
curl -sSL "$PROTOCOL_RAW/$INIT_FILE" -o .rokct/initiate.py
if command -v sha256sum &>/dev/null; then
  ACTUAL_SHA256=$(sha256sum .rokct/initiate.py | cut -d' ' -f1)
else
  ACTUAL_SHA256=$(shasum -a 256 .rokct/initiate.py | cut -d' ' -f1)
fi
if [[ "$ACTUAL_SHA256" != "$INITIATE_SHA256" ]]; then
  echo "[install] ERROR: integrity check failed for $INIT_FILE (ref $PROTOCOL_REF)." >&2
  echo "[install]   expected sha256 $INITIATE_SHA256" >&2
  echo "[install]   actual   sha256 $ACTUAL_SHA256" >&2
  echo "[install] Refusing to execute unverified code." >&2
  rm -f .rokct/initiate.py
  exit 1
fi
# END fetch-and-verify

# BEGIN requirements-install (tests/test_install.sh replaces this block with a local copy)
echo "[install] Installing Python dependencies (ref $PROTOCOL_REF)..."
if ! curl -fsSL "$PROTOCOL_RAW/requirements.txt" -o .rokct/requirements.txt; then
  echo "[install] ERROR: failed to fetch requirements.txt (ref $PROTOCOL_REF)." >&2
  exit 1
fi
if ! $PYTHON_CMD -m pip install -r .rokct/requirements.txt; then
  echo "[install] ERROR: failed to install Python dependencies from requirements.txt." >&2
  exit 1
fi
# END requirements-install

echo "[install] Running init..."
$PYTHON_CMD .rokct/initiate.py

echo "[install] Done. Run 'python .rokct/end_protocol.py' when session ends."
