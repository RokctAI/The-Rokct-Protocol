# compliance-ignore-file: structural-special-dirs
#!/usr/bin/env python3
"""
The-Rokct-Protocol scaffold: crypto_utils.py
Wrapper that exposes encrypt_pii and decrypt_pii by importing from privacy.py,
fetched pinned to PROTOCOL_REF and SHA-256 verified before it is executed.
"""

import hashlib, os, sys, urllib.request, importlib.util

# Pinned by tools/gen_protocol_lock.py - do not edit these constants by hand.
PROTOCOL_REF = "42c7e71a78aa6eb6350ada15987ed53cc001ca1f"
DELEGATE_PATH = "core/utils/agent_delegation/privacy.py"
DELEGATE_SHA256 = "0cb353f487d07d95da9b46061e2d4fb55a0177b17c99eacb3ed1a5de9e109dd3"
GITHUB_RAW_BASE = (
    f"https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/{PROTOCOL_REF}"
)


def _fetch_verified():
    """Fetch DELEGATE_PATH pinned to PROTOCOL_REF; verify its SHA-256 against
    the embedded DELEGATE_SHA256 before anything can execute it. Returns the
    code, or None when the fetch failed. A hash mismatch aborts outright -
    there is no unverified fallback."""
    url = f"{GITHUB_RAW_BASE}/{DELEGATE_PATH}"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0", "X-Trace-Id": "agent-bootstrap"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                return None
            data = resp.read()
    except Exception:
        return None
    digest = hashlib.sha256(data).hexdigest()
    if digest != DELEGATE_SHA256:
        print(
            f"[scaffold] Integrity check failed for {DELEGATE_PATH} (ref {PROTOCOL_REF}):",
            file=sys.stderr,
        )
        print(f"[scaffold]   expected sha256 {DELEGATE_SHA256}", file=sys.stderr)
        print(f"[scaffold]   actual   sha256 {digest}", file=sys.stderr)
        print("[scaffold] Refusing to execute unverified code.", file=sys.stderr)
        sys.exit(1)
    return data.decode("utf-8")


def _load_module():
    code = _fetch_verified()
    if code is None:
        return None
    # Create a temporary module to load the functions
    spec = importlib.util.spec_from_loader("privacy", loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(code, module.__dict__)
    return module


_mod = _load_module()
if _mod:
    encrypt_pii = _mod.encrypt_pii
    decrypt_pii = _mod.decrypt_pii
else:

    def encrypt_pii(*args, **kwargs):
        raise RuntimeError("Failed to load privacy.py from GitHub")

    def decrypt_pii(*args, **kwargs):
        raise RuntimeError("Failed to load privacy.py from GitHub")


if __name__ == "__main__":
    if _mod and hasattr(_mod, "main"):
        _mod.main()
