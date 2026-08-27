# Copyright (c) 2026 ROKCT INTELLIGENCE (PTY) LTD
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
# Copyright 2024 ROKCT INTELLIGENCE (PTY) LTD
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
PROTOCOL_REF = "2e579d592d6d09211bb14fae917169fc09d0a157"
BACKEND_PREFIX = "core/utils/opportunities/"
GITHUB_ZIP_URL = (
    f"https://github.com/RokctAI/The-Rokct-Protocol/archive/{PROTOCOL_REF}.zip"
)
ZIP_PREFIX = f"The-Rokct-Protocol-{PROTOCOL_REF}/{BACKEND_PREFIX}"

# Expected SHA-256 of every backend file at PROTOCOL_REF, keyed by
# repo-relative path. Pinned by tools/gen_protocol_lock.py.
EXPECTED_SHA256 = {
    "core/utils/opportunities/check_links.py": "8a0258c843b84e15facf5d254dfad1be2603bba3e3690795872362590f817d2e",
    "core/utils/opportunities/ci/check_links.py": "8a0258c843b84e15facf5d254dfad1be2603bba3e3690795872362590f817d2e",
    "core/utils/opportunities/eeip/discover_eeip.py": "2c1e338efa8e9137236c99150b0f2c2e43512148ad9a670d42c6d0510689ef28",
    "core/utils/opportunities/equity/discover_sources.py": "9b5c3856adaa8502aed4fcececf8c2856de26e41e353403881711a47ed70159f",
    "core/utils/opportunities/equity/equity_sync.py": "82e858ae07d63d0d82fccf282f307b3daaee969143b5522ad2b45e6790dc964e",
    "core/utils/opportunities/equity/funder_finder.py": "f6346a8f93e7ddd248b43f405d43aecca1ddcc302dca4ccb2d0cc9967004ae37",
    "core/utils/opportunities/equity/funder_manager.py": "31de870ae43a0789a2523e513ba19e832f49c9f616a3ac67c181603205dfbfe3",
    "core/utils/opportunities/equity/test_funder_filtering.py": "3521e5aa1be3e7075caa108f4bae29308ffec12912ba19343fa9b761f563e8ec",
    "core/utils/opportunities/equity/verify_sources.py": "3d452982d20077c11d61d2c74072185f0daa1d801f0ca2defb9f5ce09225eb46",
    "core/utils/opportunities/grants/scrapers/f4c.py": "a7adfc9077159eac70534ef5aadefcfe82191c70058344f2d130ea1c49c76d52",
    "core/utils/opportunities/maintenance/index.py": "87efee2006d8161f869b13c92d0ddbcfde54c4be89ea73e858bd8191a9a912d9",
    "core/utils/opportunities/registry_orchestrator/healers.py": "f6b8c18e2f7c2a88575fedc592dd3496ffb3072d48071028f38e47c0de079c3e",
    "core/utils/opportunities/registry_orchestrator/index.py": "1ea62105127995cf16fe5a79b03a089a6a7876e42d70e90d4000bb3bce2f0f9e",
    "core/utils/opportunities/registry_orchestrator/scanners.py": "a1a2962bc9f7fa03f5e1818b079a3eee04b07f7f55bb2e6f114477218810261c",
    "core/utils/opportunities/registry_orchestrator/send_registry_emails.py": "767961146f8e3b836e3f7badf18628cae3dfa34e7470a4d0c326683bc0c52ab9",
    "core/utils/opportunities/registry_orchestrator/updaters.py": "f78cca2435be8294fe05578165dde558ddd77f021329ca480d13d6c86fa466c0",
    "core/utils/opportunities/response_kits/index.py": "3c0c47cf0bc8a63490f1e9f2fd73587504d5b8ef6db641d3d055e2056fc8e3f7",
    "core/utils/opportunities/tenders/api/ocds.py": "660f040806a32b5c3d680081c2a2f6f20051b57ba97348682b310fff30339846",
    "core/utils/opportunities/tenders/enrichment/extract_requirements.py": "82033e92dd9bc8c51f403826ac08dd4dffc24779bc0b886afb8d9a3b56cac226",
    "core/utils/opportunities/tenders/enrichment/pdf_to_md.py": "94b26764829b5809164f6cb4eb4649f3a647bfacfd8c6cd6498e47ec831de8d5",
    "core/utils/opportunities/tenders/enrichment/test_extract_requirements.py": "026d006b734b986cc6b9488a596ec7feccb920ed5f07ba201541650e8a56c7ae",
    "core/utils/opportunities/tenders/index.py": "c16fcb6711cb2b5223c5d7af7fcc665fcdcf7cda604299a388008fb9a2c5acb2",
    "core/utils/opportunities/tenders/scrapers/musina.py": "f88f367c1c591d31c87146b77fbc5ce32965d7a148fd5cf539576e946502625d",
    "core/utils/opportunities/tenders/scrapers/test_musina_dates.py": "5d58ede28620f7b1e68b5f6e363058d72397dd93a2411c5e09b25d0fb705af51",
    "core/utils/opportunities/tenders/utils/tender_resolver.py": "b2aa40505e5f5f954133b8f4ae462ed928feb9fb420bceaac381708080640c26",
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
