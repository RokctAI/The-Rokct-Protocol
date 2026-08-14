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
PROTOCOL_REF = "45e126edb2998a43b32b48151891d7dac8c9805e"
BACKEND_PREFIX = "core/utils/opportunities/"
GITHUB_ZIP_URL = (
    f"https://github.com/RokctAI/The-Rokct-Protocol/archive/{PROTOCOL_REF}.zip"
)
ZIP_PREFIX = f"The-Rokct-Protocol-{PROTOCOL_REF}/{BACKEND_PREFIX}"

# Expected SHA-256 of every backend file at PROTOCOL_REF, keyed by
# repo-relative path. Pinned by tools/gen_protocol_lock.py.
EXPECTED_SHA256 = {
    "core/utils/opportunities/check_links.py": "265a29d5d653bb6c991f68c9df8ea14fc0ba9837cc06339f5c9c62fad4777fd8",
    "core/utils/opportunities/ci/check_links.py": "265a29d5d653bb6c991f68c9df8ea14fc0ba9837cc06339f5c9c62fad4777fd8",
    "core/utils/opportunities/eeip/discover_eeip.py": "257510d7f242810ea6487f1cbe0cb6026ad029c1d12451d3682d466a9648cf3d",
    "core/utils/opportunities/equity/discover_sources.py": "06e3dc0fa82cd6461b1e23cfc4f357e936d7f4b60f5c853560456f09b3ea0c74",
    "core/utils/opportunities/equity/equity_sync.py": "e11bf436eaba948f59c3666f07741df223b692aac673bba9e1f73e192fc45ee2",
    "core/utils/opportunities/equity/funder_finder.py": "fac31472a7db641a2f662bf9f4a273e75d0198979b4cf61924cd698c314d09d8",
    "core/utils/opportunities/equity/funder_manager.py": "20d351388c4ec6c67633b09c36e843831af5534a79b8cb79472f15485da35042",
    "core/utils/opportunities/equity/verify_sources.py": "a58a2de1a6d0f67b1e59f8c7c67248195ad3220603d21d54417966ccda4bf244",
    "core/utils/opportunities/grants/scrapers/f4c.py": "59ffbc89c8f8c8e6c41b9f8d76ecdd99442ae367f33354f3cf2669b0485f999d",
    "core/utils/opportunities/maintenance/index.py": "d6a081351033fa117fe9a5d20d70c53653e837be125e6a9cde69956620c6e178",
    "core/utils/opportunities/registry_orchestrator/healers.py": "465144de367c25d464201e974845b01db7161d115e0af359beb4e49f35b2a54e",
    "core/utils/opportunities/registry_orchestrator/index.py": "4ff734732f73861e9d2ae1705565ba4e2337134b7883281ceb25ef4c91de6899",
    "core/utils/opportunities/registry_orchestrator/scanners.py": "3d080264c1cc134bdaab55270f3ff980a3a9d6862036f35893e1dd2a08cd9b6e",
    "core/utils/opportunities/registry_orchestrator/send_registry_emails.py": "581004b639c5e74e24137bf65d283cb7483152708a35c4c07a31aee21a0f175b",
    "core/utils/opportunities/registry_orchestrator/updaters.py": "016ee7421dcc14800e29725c7f7f5a8804e2b6f0e5e7cd598b598ce0bcbd4c5e",
    "core/utils/opportunities/response_kits/index.py": "1c355d5bd03bf33adbc0cdb08307817b6b1c9b5ff7d469b0f74309995eb2ae74",
    "core/utils/opportunities/tenders/api/ocds.py": "d313ecdaf113b0ba0afffe783a411ac31f96e7824f675e45872c21a0b21ef6ed",
    "core/utils/opportunities/tenders/enrichment/extract_requirements.py": "bdc4aba8fb54af77bd265c31dd89de6a0cd68ae004a44da0a81a052eb720f092",
    "core/utils/opportunities/tenders/enrichment/pdf_to_md.py": "f68edc030d828119b3286164e3a815dbd6cdaeb965cc78f8b44229318bdcff4a",
    "core/utils/opportunities/tenders/index.py": "78a53084c85e7240cf83cf2eabc1ffe78b573adbf7b763ed35f4ea7f3bfadeec",
    "core/utils/opportunities/tenders/scrapers/musina.py": "08445566ddb1a403430a1600056614e285450cc3abdb1d6f94a5a1b455915795",
    "core/utils/opportunities/tenders/scrapers/test_musina_dates.py": "8623d7fb67d90235675eddb4cddc56ec3ae16fa9b43c44cd9a33621d9d9ca663",
    "core/utils/opportunities/tenders/utils/tender_resolver.py": "693f22e34607966e28f26e1551b2afa0e3d59cc7d696f3e04546c991f5bf6709",
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
