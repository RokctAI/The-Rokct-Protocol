# compliance-ignore-file: structural-special-dirs
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
The-Rokct-Protocol scaffold: crypto_utils.py
Wrapper that exposes encrypt_pii and decrypt_pii by importing from privacy.py,
fetched pinned to PROTOCOL_REF and SHA-256 verified before it is executed.
"""

import hashlib, os, sys, urllib.request, importlib.util

# Pinned by tools/gen_protocol_lock.py - do not edit these constants by hand.
PROTOCOL_REF = "b6f1085be28dd610e8cd72e881868e37876ded3e"
DELEGATE_PATH = "core/utils/agent_delegation/privacy.py"
DELEGATE_SHA256 = "b094c70ed64d75a5d2036c2ea4483315e7ec1b7a5aacc97cbc1da903429bd7f9"
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
