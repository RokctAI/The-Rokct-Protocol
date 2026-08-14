# compliance-ignore-file: structural-special-dirs
#!/usr/bin/env python3
"""
The-Rokct-Protocol scaffold: check_health.py
Fetches reporter.py from GitHub pinned to PROTOCOL_REF, verifies its
SHA-256, then executes it with the health subcommand.
"""

import os, sys, subprocess, tempfile, urllib.request

# Pinned by tools/gen_protocol_lock.py - do not edit these constants by hand.
PROTOCOL_REF = "42c7e71a78aa6eb6350ada15987ed53cc001ca1f"
DELEGATE_PATH = "core/utils/agent_delegation/reporter.py"
DELEGATE_SHA256 = "eda3f3c956a2a7443e1e798936e667055f895ede9d6c57cad2df829c2182f736"
GITHUB_RAW_BASE = (
    f"https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/{PROTOCOL_REF}"
)


def resolve_delegate():
    """Fetch the delegate pinned to PROTOCOL_REF from GitHub with retries and
    verify its SHA-256 against the embedded DELEGATE_SHA256 before it can be
    executed; fall back to (and refresh) a local cache under
    .rokct/tmp/delegate_cache/ - also verified - so a transient
    raw.githubusercontent.com failure cannot kill a workflow mid-run.
    initiate.py pre-populates the cache at workflow start."""
    import hashlib, time

    def verified(data, origin):
        digest = hashlib.sha256(data).hexdigest()
        if digest != DELEGATE_SHA256:
            print(
                f"[scaffold] Integrity check failed for {DELEGATE_PATH} ({origin}, ref {PROTOCOL_REF}):",
                file=sys.stderr,
            )
            print(f"[scaffold]   expected sha256 {DELEGATE_SHA256}", file=sys.stderr)
            print(f"[scaffold]   actual   sha256 {digest}", file=sys.stderr)
            print("[scaffold] Refusing to execute unverified code.", file=sys.stderr)
            sys.exit(1)
        return data.decode("utf-8")

    url = f"{GITHUB_RAW_BASE}/{DELEGATE_PATH}"
    cache = os.path.join(
        ".rokct", "tmp", "delegate_cache", os.path.basename(DELEGATE_PATH)
    )
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0", "X-Trace-Id": "agent-bootstrap"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = resp.read()
                    code = verified(data, "github")
                    try:
                        os.makedirs(os.path.dirname(cache), exist_ok=True)
                        with open(cache, "wb") as f:
                            f.write(data)
                    except OSError:
                        pass
                    return code, "github"
        except Exception:
            pass
        if attempt < 2:
            time.sleep(2**attempt)
    if os.path.exists(cache):
        with open(cache, "rb") as f:
            data = f.read()
        code = verified(data, "cache")
        print(
            f"[scaffold] GitHub fetch failed after 3 attempts; using verified cached {os.path.basename(cache)}",
            file=sys.stderr,
        )
        return code, "cache"
    return None, None


def main():
    code, source = resolve_delegate()
    if not code:
        print("Error: reporter.py not found on GitHub.", file=sys.stderr)
        sys.exit(1)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path, "health"] + sys.argv[1:], check=False
        )
        sys.exit(result.returncode)
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    main()
