# compliance-silent
#!/usr/bin/env python3
"""
The-Rokct-Protocol scaffold: privacy_sync.py
Fetches privacy_sync.py from GitHub, executes it.
"""
import os, sys, subprocess, tempfile, urllib.request

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main"
DELEGATE_PATH   = "core/utils/agent_deligation/privacy_sync.py"


def resolve_delegate():
    url = f"{GITHUB_RAW_BASE}/{DELEGATE_PATH}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            if resp.status == 200:
                return resp.read().decode("utf-8"), "github"
    except Exception:
        pass
    return None, None


def main():
    code, source = resolve_delegate()
    if not code:
        print("Error: privacy_sync.py not found on GitHub.", file=sys.stderr)
        sys.exit(1)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        result = subprocess.run([sys.executable, tmp_path] + sys.argv[1:], check=False)
        sys.exit(result.returncode)
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    main()
