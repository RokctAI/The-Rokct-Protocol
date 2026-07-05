#!/usr/bin/env python3
"""
The-Rokct-Protocol: compose.py wrapper
Fetches compose_backend.py from GitHub, executes it locally in the target app shell.
"""
import os, sys, subprocess, tempfile, urllib.request

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main"
COMPOSER_PATH   = "core/utils/frappe/compose_backend.py"


def resolve_composer():
    url = f"{GITHUB_RAW_BASE}/{COMPOSER_PATH}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "X-Trace-Id": "frappe-bootstrap"})

        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return resp.read().decode("utf-8")
    except Exception:
        pass
    return None


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
