#!/bin/bash

# test_install.sh - Tests the Rokct Protocol Installer for Human and Agent paths.
# This script is designed to run on Ubuntu/Linux environments.

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get the root of the protocol repo
REPO_ROOT=$(pwd)
TEST_ROOT="$REPO_ROOT/tests/tmp_test"

cleanup() {
  rm -rf "$TEST_ROOT"
}

# Ensure cleanup on exit
trap cleanup EXIT

setup_temp_env() {
  cleanup
  mkdir -p "$TEST_ROOT"
  cp "$REPO_ROOT/install.sh" "$TEST_ROOT/"
  cp -r "$REPO_ROOT/profiles" "$TEST_ROOT/"
  chmod +x "$TEST_ROOT/install.sh"
}

# Patch install.sh to use local profiles instead of GitHub
patch_installer() {
  # Replace the curl line with a cp line
  # Original: curl -sSL "$PROTOCOL_RAW/$INIT_FILE" -o .rokct/initiate.py
  # Patched: cp "profiles/$INIT_FILE" .rokct/initiate.py
  sed -i 's|curl -sSL "$PROTOCOL_RAW/\$INIT_FILE" -o .rokct/initiate.py|cp "profiles/\$INIT_FILE" .rokct/initiate.py|' "$TEST_ROOT/install.sh"
}

test_human() {
  echo "Testing Human path..."
  setup_temp_env
  patch_installer

  cd "$TEST_ROOT"
  # Pipe 'H' for Human
  echo "H" | bash install.sh >test_output.log 2>&1

  if [[ -d ".rokct" && -f ".rokct/initiate.py" ]]; then
    echo -e "${GREEN}PASS: Human path created .rokct/${NC}"
  else
    echo -e "${RED}FAIL: Human path failed to create .rokct/${NC}"
    cat test_output.log
    exit 1
  fi
  cd "$REPO_ROOT"
}

test_agent() {
  echo "Testing Agent path..."
  setup_temp_env
  patch_installer

  cd "$TEST_ROOT"
  # Pipe 'A' for Agent, then '1' for Web profile
  printf "A\n1\n" | bash install.sh >test_output.log 2>&1

  if [[ -d ".rokct" && -f ".rokct/initiate.py" ]]; then
    echo -e "${GREEN}PASS: Agent path created .rokct/${NC}"
  else
    echo -e "${RED}FAIL: Agent path failed to create .rokct/${NC}"
    cat test_output.log
    exit 1
  fi
  cd "$REPO_ROOT"
}

test_end_protocol() {
  echo "Testing End Protocol cleanup..."
  setup_temp_env
  patch_installer

  cd "$TEST_ROOT"
  # 1. Install the protocol
  echo "H" | bash install.sh >/dev/null 2>&1

  # Verify a workflow file was created in the root (e.g., session_logging.md)
  # Note: initiate.py copies workflows to the root
  if [[ ! -f "session_logging.md" ]]; then
    echo -e "${RED}FAIL: Installation didn't create workflow files for cleanup test${NC}"
    exit 1
  fi

  # 2. Run end_protocol.py
  python3 .rokct/end_protocol.py >test_output.log 2>&1

  # 3. Verify cleanup
  # session_logging.md should be deleted
  if [[ -f "session_logging.md" ]]; then
    echo -e "${RED}FAIL: end_protocol.py failed to delete session_logging.md${NC}"
    exit 1
  fi

  # init_protocol.md should be preserved
  if [[ ! -f "init_protocol.md" ]]; then
    echo -e "${RED}FAIL: end_protocol.py deleted init_protocol.md (should be preserved)${NC}"
    exit 1
  fi

  echo -e "${GREEN}PASS: End Protocol cleanup verified${NC}"
  cd "$REPO_ROOT"
}

# Run tests
test_human
test_agent
test_end_protocol

echo -e "\n${GREEN}All protocol tests passed!${NC}"
