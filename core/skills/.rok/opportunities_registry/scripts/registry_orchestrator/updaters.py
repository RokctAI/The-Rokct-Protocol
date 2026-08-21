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

# Licensed under the MIT License.
# Copyright 2024 RokctAI
# compliance-silent
"""The-Rokct-Protocol opportunities wrapper.

Fetches the `core/utils/opportunities/` backend from the repository archive
pinned to PROTOCOL_REF (an immutable commit SHA, not `main`), verifies the
SHA-256 of every extracted file against the embedded EXPECTED_SHA256 pins
BEFORE anything is written to the cache or executed, then runs the backend
script that mirrors this wrapper's path. The cache is keyed by PROTOCOL_REF
and is re-verified on every use, so neither a moved branch nor a tampered
cache can inject code. A fetch failure or a hash mismatch aborts with exit 1;
there is no unverified fallback.

All wrappers under core/skills/.rok/opportunities_registry/scripts/ are
byte-identical copies of this file — only their location differs, which
selects the backend script to execute.
"""

import hashlib, io, os, sys, subprocess, urllib.request, zipfile

# Pinned by tools/gen_protocol_lock.py - do not edit these constants by hand.
PROTOCOL_REF = "f6b885f9302621d03c35e5568e47c42368d19a4d"
BACKEND_PREFIX = "core/utils/opportunities/"
GITHUB_ZIP_URL = (
    f"https://github.com/RokctAI/The-Rokct-Protocol/archive/{PROTOCOL_REF}.zip"
)
ZIP_PREFIX = f"The-Rokct-Protocol-{PROTOCOL_REF}/{BACKEND_PREFIX}"

# Expected SHA-256 of every backend file at PROTOCOL_REF, keyed by
# repo-relative path. Pinned by tools/gen_protocol_lock.py.
EXPECTED_SHA256 = {
    "core/utils/opportunities/check_links.py": "021da6d43f94c1dbc5974eded6e0a0e790945f7edb3c66e3ff8ce6cb63440516",
    "core/utils/opportunities/ci/check_links.py": "021da6d43f94c1dbc5974eded6e0a0e790945f7edb3c66e3ff8ce6cb63440516",
    "core/utils/opportunities/eeip/discover_eeip.py": "cef800250a8ac174694948d7b4765879973b9cd7f7b84bd9a93232d7487b85b3",
    "core/utils/opportunities/equity/discover_sources.py": "be3dec053301d61298e8d6feabd8dc341aff4e6bb5b198b4580a7395937c37b4",
    "core/utils/opportunities/equity/equity_sync.py": "2766c359e48d88bffad8340b82a5c4b6fef8a38e63368218194c62b89d47dd13",
    "core/utils/opportunities/equity/funder_finder.py": "2edfbd505a518d120168a67b3d3c68eaf1b2e2beeb5d84a3d9f7d93cf0659faf",
    "core/utils/opportunities/equity/funder_manager.py": "d182c2b7785be644098896131358cdb96c9a7cccc19884bcdef564e4a0c8d55d",
    "core/utils/opportunities/equity/verify_sources.py": "b6602aedc5d33f55fde27d68bb10fd6c4cbd486a98e9b83085dda7383fa7bcce",
    "core/utils/opportunities/grants/scrapers/f4c.py": "7b80d8160d4371e3c438bbd99e7b85e331eddfd7c95e06cb4a972889bba32ea4",
    "core/utils/opportunities/maintenance/index.py": "110517d30cb4e7ccbda16df09b16c428f7d0354ff4d10587a62c8000a1f8cdaf",
    "core/utils/opportunities/registry_orchestrator/healers.py": "9b627944c459d4f5917481891053748c2425e76d7feae6b1ee11bb59b7f9da44",
    "core/utils/opportunities/registry_orchestrator/index.py": "bec11cf2a07d95f1eb60d3f5f328fa3f46ba08364ccff37612980c373f218f2a",
    "core/utils/opportunities/registry_orchestrator/scanners.py": "ba7a61ae6dd90a34c5a467ba7122dcee30cfec267a1ac9c1e238fecc675a0cfe",
    "core/utils/opportunities/registry_orchestrator/send_registry_emails.py": "ec1e8b5c2a0ea23ad817e9ab933e1e870b42443e0cd53ffb752c5a1c30be1f72",
    "core/utils/opportunities/registry_orchestrator/updaters.py": "1b957f307f39f37fba52f444ac621387f83e4c3968100f3adbee6c1844bc74ac",
    "core/utils/opportunities/response_kits/index.py": "2196399a9d3c2478a96ad284a55a530f4f18f887beef9d016bf44bd52e2f9dc7",
    "core/utils/opportunities/tenders/api/ocds.py": "57f77189c2af44747a693de8968861e97e0bdd698c5de42dd87ce9e9b09e22e0",
    "core/utils/opportunities/tenders/enrichment/extract_requirements.py": "74119520b47c2ce8adaf5d2b432b02d333d93b453a958db9408fcb07f3bd095f",
    "core/utils/opportunities/tenders/enrichment/pdf_to_md.py": "c0c911678fd77a5787d4204b1845263f84e38dc14c90df1a5505bb83802e8c7e",
    "core/utils/opportunities/tenders/enrichment/test_extract_requirements.py": "8a2c2d9aa87173718ceebfbcbc1ab2575225ca717384aed02d4e168d5fd8ef95",
    "core/utils/opportunities/tenders/index.py": "b7b0269dcc403670710ea7416edc6c1c94296fd6c2a96ec80f30f82fe0219fe1",
    "core/utils/opportunities/tenders/scrapers/musina.py": "a8f490caabf52e714458248397c87f24d4365cf7df482a3da5dbe63bf37c4fc2",
    "core/utils/opportunities/tenders/scrapers/test_musina_dates.py": "9abd791589e3fa47dffc66fec80c591c8cacda4e97f19f18068d97d8e3b19775",
    "core/utils/opportunities/tenders/utils/tender_resolver.py": "4ec8d661ca08d2def7749a8399c665238796790d511fab61d366c35fe973a827",
}


def _refuse(origin):
    print(
        f"[wrapper] Refusing to execute unverified code ({origin}, ref {PROTOCOL_REF}).",
        file=sys.stderr,
    )
    sys.exit(1)


def _verify(rel, payload, origin):
    """Abort unless `payload` matches the embedded pin for the backend file."""
    repo_path = BACKEND_PREFIX + rel
    expected = EXPECTED_SHA256.get(repo_path)
    if expected is None:
        print(
            f"[wrapper] Unpinned file in {origin}: {repo_path} has no embedded hash.",
            file=sys.stderr,
        )
        _refuse(origin)
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected:
        print(
            f"[wrapper] Integrity check failed for {repo_path} ({origin}, ref {PROTOCOL_REF}):",
            file=sys.stderr,
        )
        print(f"[wrapper]   expected sha256 {expected}", file=sys.stderr)
        print(f"[wrapper]   actual   sha256 {digest}", file=sys.stderr)
        _refuse(origin)


def _safe_path(base_dir, rel):
    """Resolve a relative path under `base_dir`, refusing anything that escapes it."""
    target = os.path.realpath(os.path.join(base_dir, rel))
    base = os.path.realpath(base_dir)
    if os.path.commonpath([base, target]) != base:
        print(
            f"[wrapper] Refusing path outside the cache directory: {rel}",
            file=sys.stderr,
        )
        sys.exit(1)
    return target


def _fetch_verified():
    """Download the pinned archive and return {rel: bytes}, fully verified.

    Every file under the archive's opportunities prefix must carry a matching
    embedded hash, and every pinned file must be present — anything else is a
    hard abort. Nothing is written to disk until the whole set has verified.
    """
    print(f"[wrapper] Fetching opportunities scripts pinned to {PROTOCOL_REF}...")
    try:
        req = urllib.request.Request(
            GITHUB_ZIP_URL,
            headers={"User-Agent": "Mozilla/5.0", "X-Trace-Id": "agent-http"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            z = zipfile.ZipFile(io.BytesIO(resp.read()))
    except Exception as e:
        print(f"Error downloading opportunities script archive: {e}", file=sys.stderr)
        sys.exit(1)
    files = {}
    for name in z.namelist():
        if name.startswith(ZIP_PREFIX) and not name.endswith("/"):
            rel = name[len(ZIP_PREFIX) :]
            data = z.read(name)
            _verify(rel, data, "github")
            files[rel] = data
    missing = sorted(set(EXPECTED_SHA256) - {BACKEND_PREFIX + rel for rel in files})
    if missing:
        print(
            f"Error: archive at ref {PROTOCOL_REF} is missing pinned files: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        sys.exit(1)
    return files


def _write_cache(cache_dir, files):
    """Write the already-verified files into the ref-keyed cache."""
    for rel, data in files.items():
        dest = _safe_path(cache_dir, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
    print(f"[wrapper] Fetched and verified {len(files)} files to cache.")


def _verify_cache(cache_dir):
    """Re-verify every cached backend file against the embedded pins."""
    for repo_path in sorted(EXPECTED_SHA256):
        rel = repo_path[len(BACKEND_PREFIX) :]
        path = _safe_path(cache_dir, rel)
        if not os.path.exists(path):
            print(f"Error: cached file missing: {path}", file=sys.stderr)
            print(
                "[wrapper] Delete the cache directory to force a re-fetch.",
                file=sys.stderr,
            )
            sys.exit(1)
        with open(path, "rb") as f:
            _verify(rel, f.read(), "cache")


def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = current_dir
    while repo_root:
        if os.path.exists(os.path.join(repo_root, ".rokct")):
            break
        parent = os.path.dirname(repo_root)
        if parent == repo_root:
            break
        repo_root = parent

    cache_dir = os.path.join(repo_root, ".rokct", "tmp", "opportunities", PROTOCOL_REF)

    if not os.path.exists(cache_dir):
        files = _fetch_verified()
        os.makedirs(cache_dir, exist_ok=True)
        _write_cache(cache_dir, files)
    else:
        _verify_cache(cache_dir)

    skills_scripts_dir = os.path.join(
        repo_root, ".rokct", "skills", ".rok", "opportunities_registry", "scripts"
    )
    rel_path = os.path.relpath(os.path.abspath(__file__), skills_scripts_dir)
    target_script = os.path.join(cache_dir, rel_path)

    if not os.path.exists(target_script):
        print(
            f"Error: Target script not found in cache: {target_script}", file=sys.stderr
        )
        sys.exit(1)

    res = subprocess.run([sys.executable, target_script] + sys.argv[1:])
    sys.exit(res.returncode)


if __name__ == "__main__":
    main()
