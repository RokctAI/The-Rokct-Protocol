#!/bin/bash

# Rokct Protocol Installer (Bash)
# Usage: curl -sSL https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/install.sh | bash

set -e

# Pinned by tools/gen_protocol_lock.py - do not edit these constants by hand.
# The initiate.py fetch is pinned to this commit and its SHA-256 is verified
# before it is executed; a mismatch aborts the install.
PROTOCOL_REF="111b33289dec7e1de06f480a0496c6b948d4bb2d"
INITIATE_SHA256_LOCAL="2b95b7d810e430b43dbf48b9c87a6f4007886b94874d58b96bf611a79348abee"
INITIATE_SHA256_WEB="d500751d085a2c3d2eab06d0e7e5364e4fa74c4fef7ade0949d851adc3b3bf6a"

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
