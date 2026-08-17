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
PROTOCOL_REF = "feaaa79559b8c9396cb35723c701fe56cb81fab5"
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
    "core/utils/opportunities/equity/equity_sync.py": "44966c6e07de6efe766adb3d4a287aeccdd48eee89f1563afb33d71a8e6336d7",
    "core/utils/opportunities/equity/funder_finder.py": "5e928b2c2add015b753fc62751ec992ec4c92b9e24299ba6e9fb317487d1706f",
    "core/utils/opportunities/equity/funder_manager.py": "336f21234602524c56bf110f229744db124a97abff20d1b8f955899bebf8a826",
    "core/utils/opportunities/equity/verify_sources.py": "b6602aedc5d33f55fde27d68bb10fd6c4cbd486a98e9b83085dda7383fa7bcce",
    "core/utils/opportunities/grants/scrapers/f4c.py": "9c3a233571166e66fdbc2a0ffa6f5b15f8c4f179f7a0f4c0012d3b0626905f1b",
    "core/utils/opportunities/maintenance/index.py": "110517d30cb4e7ccbda16df09b16c428f7d0354ff4d10587a62c8000a1f8cdaf",
    "core/utils/opportunities/registry_orchestrator/healers.py": "9b627944c459d4f5917481891053748c2425e76d7feae6b1ee11bb59b7f9da44",
    "core/utils/opportunities/registry_orchestrator/index.py": "ad6fce694c814faf8d8a9ac05bf44fb6547ba4e2b833f0da75bdf02d9e66c7df",
    "core/utils/opportunities/registry_orchestrator/scanners.py": "6eb3f8b4a5c68543905824e05b6889892f35cd507577a05f7637a656a6beaaee",
    "core/utils/opportunities/registry_orchestrator/send_registry_emails.py": "ec1e8b5c2a0ea23ad817e9ab933e1e870b42443e0cd53ffb752c5a1c30be1f72",
    "core/utils/opportunities/registry_orchestrator/updaters.py": "5c7901d45036035c3f31532ad648c45aa16d9ec45519400a4142a7b1a16aee2f",
    "core/utils/opportunities/response_kits/index.py": "2196399a9d3c2478a96ad284a55a530f4f18f887beef9d016bf44bd52e2f9dc7",
    "core/utils/opportunities/tenders/api/ocds.py": "b5c2cfe9a2208e224629f729ebff6fd8d5475ab4292337b736b07e86497eade7",
    "core/utils/opportunities/tenders/enrichment/extract_requirements.py": "6140d9448022a2d2225b49fbf05d1ecf1fcbe690e24c296faf3c08e41c64f500",
    "core/utils/opportunities/tenders/enrichment/pdf_to_md.py": "c5c18683c0939fa8d5b31456e043fda8eb39479f1cb0e516485c6fc506702029",
    "core/utils/opportunities/tenders/index.py": "0d7e4a80ed63cd962b85588216814c28b191a82dbe84e7ac89968f7eda7abff1",
    "core/utils/opportunities/tenders/scrapers/musina.py": "ed745650c14aea177212c9fc04b8efa35c37546e8533adfb25255e1dac4c83e9",
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
