#!/usr/bin/env python3
"""
The-Rokct-Protocol: compose.py wrapper
Fetches compose_backend.py from GitHub pinned to PROTOCOL_REF, verifies its
SHA-256, then executes it locally in the target app shell.
"""

import hashlib, os, sys, subprocess, tempfile, urllib.request

# Pinned by tools/gen_protocol_lock.py - do not edit these constants by hand.
PROTOCOL_REF = "3c9e561e83ac563cdc11d8e0d30ce77eb9551020"
COMPOSER_PATH = "core/utils/frappe/compose_backend.py"
COMPOSER_SHA256 = "bab4608166e7669ef6e4e713ec064e0ff86cbbe69f473a9e292c895f51abb33a"
GITHUB_RAW_BASE = (
    f"https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/{PROTOCOL_REF}"
)


def resolve_composer():
    url = f"{GITHUB_RAW_BASE}/{COMPOSER_PATH}"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0", "X-Trace-Id": "frappe-bootstrap"}
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                return None
            data = resp.read()
    except Exception:
        return None
    digest = hashlib.sha256(data).hexdigest()
    if digest != COMPOSER_SHA256:
        print(
            f"[compose] Integrity check failed for {COMPOSER_PATH} (ref {PROTOCOL_REF}):",
            file=sys.stderr,
        )
        print(f"[compose]   expected sha256 {COMPOSER_SHA256}", file=sys.stderr)
        print(f"[compose]   actual   sha256 {digest}", file=sys.stderr)
        print("[compose] Refusing to execute unverified code.", file=sys.stderr)
        sys.exit(1)
    return data.decode("utf-8")


def main():
    code = resolve_composer()
    if not code:
        print("Error: compose_backend.py not found on GitHub.", file=sys.stderr)
        sys.exit(1)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        result = subprocess.run([sys.executable, tmp_path] + sys.argv[1:], check=False)
        sys.exit(result.returncode)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


if __name__ == "__main__":
    main()
