# compliance-ignore-file: structural-special-dirs
#!/usr/bin/env python3
"""
The-Rokct-Protocol scaffold: handle_groq_output.py
Fetches handle_groq_output.py from GitHub, executes it.
"""
import os, sys, subprocess, tempfile, urllib.request

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main"
DELEGATE_PATH   = "core/utils/agent_deligation/handle_groq_output.py"


def resolve_delegate():
    """Fetch the delegate from GitHub with retries; fall back to (and
    refresh) a local cache under .rokct/tmp/delegate_cache/ so a transient
    raw.githubusercontent.com failure cannot kill a workflow mid-run.
    initiate.py pre-populates the cache at workflow start."""
    import time
    url = f"{GITHUB_RAW_BASE}/{DELEGATE_PATH}"
    cache = os.path.join(".rokct", "tmp", "delegate_cache", os.path.basename(DELEGATE_PATH))
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "X-Trace-Id": "agent-bootstrap"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    code = resp.read().decode("utf-8")
                    try:
                        os.makedirs(os.path.dirname(cache), exist_ok=True)
                        with open(cache, "w", encoding="utf-8") as f:
                            f.write(code)
                    except OSError:
                        pass
                    return code, "github"
        except Exception:
            pass
        if attempt < 2:
            time.sleep(2 ** attempt)
    if os.path.exists(cache):
        print(f"[scaffold] GitHub fetch failed after 3 attempts; using cached {os.path.basename(cache)}", file=sys.stderr)
        with open(cache, encoding="utf-8") as f:
            return f.read(), "cache"
    return None, None


def main():
    code, source = resolve_delegate()
    if not code:
        print("Error: handle_groq_output.py not found on GitHub.", file=sys.stderr)
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
