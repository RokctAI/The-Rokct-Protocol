# compliance-ignore-file: structural-special-dirs
#!/usr/bin/env python3
# Copyright (c) 2026 ROKCT INTELLIGENCE (PTY) LTD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
The-Rokct-Protocol scaffold: update_classifications.py
Wrapper that exposes is_duplicate_theme by importing from job_manager.py,
fetched pinned to PROTOCOL_REF and SHA-256 verified before it is executed.
"""

import hashlib, os, sys, urllib.request, importlib.util

# Pinned by tools/gen_protocol_lock.py - do not edit these constants by hand.
PROTOCOL_REF = "9e4d350f09fd2c7123178f94a0f723e49f96b7b8"
DELEGATE_PATH = "core/utils/agent_delegation/job_manager.py"
DELEGATE_SHA256 = "61369a6164e7443dba43561f092f7eabad0f2b2c1d5a04ee27911a41ff39e2a9"
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
    spec = importlib.util.spec_from_loader("job_manager", loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(code, module.__dict__)
    return module


_mod = _load_module()
if _mod:
    is_duplicate_theme = _mod.is_duplicate_theme
else:

    def is_duplicate_theme(*args, **kwargs):
        raise RuntimeError("Failed to load job_manager.py from GitHub")


if __name__ == "__main__":
    if _mod and hasattr(_mod, "main"):
        # If run directly as a script, execute the CLI with "classify" subcommand
        import tempfile, subprocess

        code = _fetch_verified()
        if code is None:
            print(
                "Error running classify: could not fetch job_manager.py",
                file=sys.stderr,
            )
            sys.exit(1)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(code)
            tmp_path = tmp.name
        try:
            result = subprocess.run(
                [sys.executable, tmp_path, "classify"] + sys.argv[1:], check=False
            )
            sys.exit(result.returncode)
        finally:
            os.unlink(tmp_path)
