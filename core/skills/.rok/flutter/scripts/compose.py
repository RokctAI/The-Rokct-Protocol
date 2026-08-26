#!/usr/bin/env python3
# Copyright (c) 2026 RokctAI
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
The-Rokct-Protocol: compose.py wrapper for Flutter
Fetches sdk_composer.py and sdk_installer_base.py from GitHub pinned to
PROTOCOL_REF, verifies their SHA-256, then executes the composer locally.
"""

import hashlib, os, sys, subprocess, tempfile, urllib.request

# Pinned by tools/gen_protocol_lock.py - do not edit these constants by hand.
PROTOCOL_REF = "48bac4e33877de630148876f6f3e88c34ce208d7"
COMPOSER_PATH = "core/utils/flutter/sdk_composer.py"
INSTALLER_BASE_PATH = "core/utils/flutter/sdk_installer_base.py"
GITHUB_RAW_BASE = (
    f"https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/{PROTOCOL_REF}"
)
EXPECTED_SHA256 = {
    "core/utils/flutter/sdk_composer.py": "aa631fb7571b0beb2cf36162573d58cffade39be7e2cdd35a0375ba814d40713",
    "core/utils/flutter/sdk_installer_base.py": "5ee76c82d4fbc8e7da1e995b4dc147e6b1b68495ea60f4ce74ea0decc33d63ba",
}


def fetch_script(path):
    url = f"{GITHUB_RAW_BASE}/{path}"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0", "X-Trace-Id": "flutter-bootstrap"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                return None
            data = resp.read()
    except Exception:
        return None
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256[path]:
        print(
            f"[compose] Integrity check failed for {path} (ref {PROTOCOL_REF}):",
            file=sys.stderr,
        )
        print(f"[compose]   expected sha256 {EXPECTED_SHA256[path]}", file=sys.stderr)
        print(f"[compose]   actual   sha256 {digest}", file=sys.stderr)
        print("[compose] Refusing to execute unverified code.", file=sys.stderr)
        sys.exit(1)
    return data.decode("utf-8")


def main():
    composer_code = fetch_script(COMPOSER_PATH)
    installer_base_code = fetch_script(INSTALLER_BASE_PATH)

    if not composer_code or not installer_base_code:
        print("Error: Flutter composer scripts not found on GitHub.", file=sys.stderr)
        sys.exit(1)

    # Write both to the current working directory temporarily so imports match.
    # sdk_installer_base.py must land in .rokct/ specifically: each cached SDK's
    # install.py does sys.path.append(os.path.join(os.getcwd(), '.rokct')) before
    # importing it, so writing it to the cwd root (as this used to do) causes
    # "ModuleNotFoundError: No module named 'sdk_installer_base'" for every SDK.
    tmp_composer = os.path.join(os.getcwd(), "_tmp_sdk_composer.py")
    rokct_dir = os.path.join(os.getcwd(), ".rokct")
    os.makedirs(rokct_dir, exist_ok=True)
    tmp_installer_base = os.path.join(rokct_dir, "sdk_installer_base.py")

    with open(tmp_composer, "w", encoding="utf-8") as f:
        f.write(composer_code)

    # Always overwrite with the freshly-fetched copy: a stale local file left
    # over from a prior run must never shadow fixes pushed to GitHub.
    with open(tmp_installer_base, "w", encoding="utf-8") as f:
        f.write(installer_base_code)

    try:
        result = subprocess.run(
            [sys.executable, tmp_composer] + sys.argv[1:], check=False
        )
        sys.exit(result.returncode)
    finally:
        if os.path.exists(tmp_composer):
            os.unlink(tmp_composer)
        if os.path.exists(tmp_installer_base):
            os.unlink(tmp_installer_base)


if __name__ == "__main__":
    main()
