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
PROTOCOL_REF = "15f0befa044853caa915597e6921d7f98d3a4fbb"
BACKEND_PREFIX = "core/utils/opportunities/"
GITHUB_ZIP_URL = f"https://github.com/RokctAI/The-Rokct-Protocol/archive/{PROTOCOL_REF}.zip"
ZIP_PREFIX = f"The-Rokct-Protocol-{PROTOCOL_REF}/{BACKEND_PREFIX}"

# Expected SHA-256 of every backend file at PROTOCOL_REF, keyed by
# repo-relative path. Pinned by tools/gen_protocol_lock.py.
EXPECTED_SHA256 = {
    "core/utils/opportunities/check_links.py": "1b0d76e6b941d658c6a0aaa2c41a8c2e69fd1f031077cb21d00fbbea2940dd9b",
    "core/utils/opportunities/ci/check_links.py": "1b0d76e6b941d658c6a0aaa2c41a8c2e69fd1f031077cb21d00fbbea2940dd9b",
    "core/utils/opportunities/eeip/discover_eeip.py": "7595b0381ac45f8da8dd27dadbd18386eefe158cc6479052ca0b6c4839472a27",
    "core/utils/opportunities/equity/discover_sources.py": "c06d300dc1fbefabe2f2ea038ca85b23abd0057f7624238f06b9e90571190004",
    "core/utils/opportunities/equity/equity_sync.py": "d4f197d0ce8e07cbf2803ecde451f53b41559379e640545dce17a255351bcfea",
    "core/utils/opportunities/equity/funder_finder.py": "09fc84b7c1ed5c42f03521f3b892a60e9b66a3de77358a838e5c0e368d56f255",
    "core/utils/opportunities/equity/funder_manager.py": "aafa02b2ec199ee41c3dfd4d5ffc04599c796ea1f21f5c097d152cdeaacfef26",
    "core/utils/opportunities/equity/verify_sources.py": "7164b93a224e155a813aab8692154188ef4dcd1f06d6de367bfdb1ce10b2094b",
    "core/utils/opportunities/grants/scrapers/f4c.py": "b5ba059d40a7c19340233c609dd4c7398e58280e3f4c00e378fdde3e215cb35a",
    "core/utils/opportunities/maintenance/index.py": "22f787cf90c217588a5afb2a918c9b37460967ea37f76d49a1e84bcb9d6b20eb",
    "core/utils/opportunities/registry_orchestrator/healers.py": "27b2de5ff74f15dfd10e4c74e0eed7436cc67e4074fa7e2de56ee4304bbcceef",
    "core/utils/opportunities/registry_orchestrator/index.py": "2a92bb7c80eed6909bb37a9ee677475230c3bf158d9a213313f61a9f585c7eec",
    "core/utils/opportunities/registry_orchestrator/scanners.py": "64668b032cd37d455f8163dd403e344355a7e5bd36a7299bcade8a2719d95fa3",
    "core/utils/opportunities/registry_orchestrator/send_registry_emails.py": "0404643bacb5432cd30f7ab698b054adf18d1d02ad4b159e399512f3ae3c284b",
    "core/utils/opportunities/registry_orchestrator/updaters.py": "628e80f7705e74c2287db9446352ec8c179d8e3181d546b60d6f3e5aa82a7d60",
    "core/utils/opportunities/response_kits/index.py": "8b84544b24e17f3329693be8781f66b0b27c6bdaf0ec978dd904782aae4f6471",
    "core/utils/opportunities/tenders/api/ocds.py": "917f8ba8a15e446e7e5aaf2b4eecf19a1d31cbd8cd6932de55d4f10e89ffea7c",
    "core/utils/opportunities/tenders/enrichment/extract_requirements.py": "f279acced887ce9880a86672fa11a3ac32ad13b982dddd50dd2f0487d963c48e",
    "core/utils/opportunities/tenders/enrichment/pdf_to_md.py": "c6d2f32dea08ae1052f9332bacd0b5d99d6d55710ca29c6e5849139816afc9e6",
    "core/utils/opportunities/tenders/index.py": "e46e11fe6978b0a3be4a2032ba32970c4f9d7d0eaa3ba50531da326727c55929",
    "core/utils/opportunities/tenders/scrapers/musina.py": "8d6a5cb5d287cff965267540efbc4c47dd9ebfcc7d3360003bc1654f0ca7564d",
    "core/utils/opportunities/tenders/scrapers/test_musina_dates.py": "be9a5d166bb7edba42106c0aa73daf0636e6af3d466f15f49a90d52e8881ec8c",
    "core/utils/opportunities/tenders/utils/tender_resolver.py": "d69e4b983028aab7719f687b649c9029772ae86981e8b004f5dc6ab7d385ce90",
}


def _refuse(origin):
    print(f"[wrapper] Refusing to execute unverified code ({origin}, ref {PROTOCOL_REF}).",
          file=sys.stderr)
    sys.exit(1)


def _verify(rel, payload, origin):
    """Abort unless `payload` matches the embedded pin for the backend file."""
    repo_path = BACKEND_PREFIX + rel
    expected = EXPECTED_SHA256.get(repo_path)
    if expected is None:
        print(f"[wrapper] Unpinned file in {origin}: {repo_path} has no embedded hash.",
              file=sys.stderr)
        _refuse(origin)
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected:
        print(f"[wrapper] Integrity check failed for {repo_path} ({origin}, ref {PROTOCOL_REF}):",
              file=sys.stderr)
        print(f"[wrapper]   expected sha256 {expected}", file=sys.stderr)
        print(f"[wrapper]   actual   sha256 {digest}", file=sys.stderr)
        _refuse(origin)


def _safe_path(base_dir, rel):
    """Resolve a relative path under `base_dir`, refusing anything that escapes it."""
    target = os.path.realpath(os.path.join(base_dir, rel))
    base = os.path.realpath(base_dir)
    if os.path.commonpath([base, target]) != base:
        print(f"[wrapper] Refusing path outside the cache directory: {rel}", file=sys.stderr)
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
            GITHUB_ZIP_URL, headers={"User-Agent": "Mozilla/5.0", "X-Trace-Id": "agent-http"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            z = zipfile.ZipFile(io.BytesIO(resp.read()))
    except Exception as e:
        print(f"Error downloading opportunities script archive: {e}", file=sys.stderr)
        sys.exit(1)
    files = {}
    for name in z.namelist():
        if name.startswith(ZIP_PREFIX) and not name.endswith("/"):
            rel = name[len(ZIP_PREFIX):]
            data = z.read(name)
            _verify(rel, data, "github")
            files[rel] = data
    missing = sorted(set(EXPECTED_SHA256) - {BACKEND_PREFIX + rel for rel in files})
    if missing:
        print(f"Error: archive at ref {PROTOCOL_REF} is missing pinned files: "
              + ", ".join(missing), file=sys.stderr)
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
        rel = repo_path[len(BACKEND_PREFIX):]
        path = _safe_path(cache_dir, rel)
        if not os.path.exists(path):
            print(f"Error: cached file missing: {path}", file=sys.stderr)
            print("[wrapper] Delete the cache directory to force a re-fetch.", file=sys.stderr)
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

    skills_scripts_dir = os.path.join(repo_root, ".rokct", "skills", ".rok", "opportunities_registry", "scripts")
    rel_path = os.path.relpath(os.path.abspath(__file__), skills_scripts_dir)
    target_script = os.path.join(cache_dir, rel_path)

    if not os.path.exists(target_script):
        print(f"Error: Target script not found in cache: {target_script}", file=sys.stderr)
        sys.exit(1)

    res = subprocess.run([sys.executable, target_script] + sys.argv[1:])
    sys.exit(res.returncode)

if __name__ == "__main__":
    main()
