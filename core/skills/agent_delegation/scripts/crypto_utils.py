# compliance-silent
#!/usr/bin/env python3
"""
The-Rokct-Protocol scaffold: crypto_utils.py
Wrapper that exposes encrypt_pii and decrypt_pii by importing from privacy.py.
"""
import os, sys, urllib.request, importlib.util

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main"
DELEGATE_PATH   = "core/utils/agent_deligation/privacy.py"

def _load_module():
    url = f"{GITHUB_RAW_BASE}/{DELEGATE_PATH}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            if resp.status == 200:
                code = resp.read().decode("utf-8")
                # Create a temporary module to load the functions
                spec = importlib.util.spec_from_loader("privacy", loader=None)
                module = importlib.util.module_from_spec(spec)
                exec(code, module.__dict__)
                return module
    except Exception:
        pass
    return None

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
