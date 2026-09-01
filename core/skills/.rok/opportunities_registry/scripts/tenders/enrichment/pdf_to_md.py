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
PROTOCOL_REF = "b1a56d12419ea52ed0dad7505b28f5d08f52b410"
BACKEND_PREFIX = "core/utils/opportunities/"
GITHUB_ZIP_URL = (
    f"https://github.com/RokctAI/The-Rokct-Protocol/archive/{PROTOCOL_REF}.zip"
)
ZIP_PREFIX = f"The-Rokct-Protocol-{PROTOCOL_REF}/{BACKEND_PREFIX}"

# Expected SHA-256 of every backend file at PROTOCOL_REF, keyed by
# repo-relative path. Pinned by tools/gen_protocol_lock.py.
EXPECTED_SHA256 = {
    "core/utils/opportunities/check_links.py": "03e462c93b4c4b0072a1519f9262a87e775d8f033244ed43d97f5a77718e2e12",
    "core/utils/opportunities/ci/check_links.py": "03e462c93b4c4b0072a1519f9262a87e775d8f033244ed43d97f5a77718e2e12",
    "core/utils/opportunities/eeip/discover_eeip.py": "50c19454cf7594ccf5f81c8f803cb9e63281f4b0335498715fab693a1dfb86a8",
    "core/utils/opportunities/equity/discover_sources.py": "70b9b0e7e3c5e6e64898c395ed62a88f5654082a54ab8c960923e5debc88a381",
    "core/utils/opportunities/equity/equity_sync.py": "ef7b3fa822ecaa13fcb72096b68d31dc0b7cd519c31ab7858f743bd82be51e7d",
    "core/utils/opportunities/equity/funder_finder.py": "c9e0f76c8474c85b0f346944fa148556f16882ea74ada4f5f377a9cf0cf42aeb",
    "core/utils/opportunities/equity/funder_manager.py": "ab9c151d58cd6c35b876a8e30a00c5cc18366e25f044e19f87f8af0b22a299dd",
    "core/utils/opportunities/equity/test_funder_filtering.py": "cea9ace59810b0f476d5ee5dc58ada6de3e8d320810f65d8c4ce7939f00e0838",
    "core/utils/opportunities/equity/verify_sources.py": "c1cd3d5dacc61b1a81a03da6c310b60d5728c7fb2450633c9eeed0b878109810",
    "core/utils/opportunities/grants/scrapers/f4c.py": "2bdc2f8ee7ec994b1a3d4b6ba183e73c09e9bdcdf3119af2bd7fc710bc1c1cc3",
    "core/utils/opportunities/maintenance/index.py": "baddb01cf8b729bc4688cb0a49f85114bd90f490cedb0d49f316eb86aac1b7f3",
    "core/utils/opportunities/registry_orchestrator/healers.py": "16f9221248092e40e8301d3cab3f918d1339ec3d07e587d5555461f68d11c301",
    "core/utils/opportunities/registry_orchestrator/index.py": "033756d0507e82f0b02bc1ea3bb22bda50c0a26d024f79120f20d01c8779c475",
    "core/utils/opportunities/registry_orchestrator/scanners.py": "f09dcecc90a00532ca68b9b5e5905328997abd69514eba504939d381d1c0d103",
    "core/utils/opportunities/registry_orchestrator/send_registry_emails.py": "30b7f7f24834c02ca65c5f9cfe1bdaf1e43340a5f278b8d3b932e11e0260463c",
    "core/utils/opportunities/registry_orchestrator/updaters.py": "224b21d18806a4df55ab4de038390a577d65e2f219567b7619b5e84b129a435f",
    "core/utils/opportunities/response_kits/index.py": "962f7df2b43463bfda70564dc8a4c4d91a65821eb5a45e717f4863c3a6fd1d65",
    "core/utils/opportunities/tenders/api/ocds.py": "e78ef9ff97bcd2255d9581e985138f16b1292154a364cc8df888001efb0b007f",
    "core/utils/opportunities/tenders/enrichment/extract_requirements.py": "03eabbdbdd3173d7587ed6150e1fdef01a432eb6079d0ad473ee976b4a1c1217",
    "core/utils/opportunities/tenders/enrichment/pdf_to_md.py": "3579698ed9c7911fc191fcab29c3ef2855199fb962563ca409d2a5e9b061c735",
    "core/utils/opportunities/tenders/enrichment/test_extract_requirements.py": "0fee0a2843436b78f3dc87f31bf0de608ed3681414e1fedabf610700f92e859a",
    "core/utils/opportunities/tenders/index.py": "aac74cd91e19adf35fafea9074119a3a8de328e0e211b7a3fb9013c47bb1bd5e",
    "core/utils/opportunities/tenders/scrapers/musina.py": "ba386d2cee84ff74a4cd8c5f03e7231d522801647c5daf18d317afaa25cf9349",
    "core/utils/opportunities/tenders/scrapers/test_musina_dates.py": "eda31f0003c8af38be552921bef613f6c42de140666642093e0cfe21328f090e",
    "core/utils/opportunities/tenders/utils/tender_resolver.py": "cc63d3ce227c33ada596441e937e9add05133c69e713a1ebeed9d66b321d1a26",
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
