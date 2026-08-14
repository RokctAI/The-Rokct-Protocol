# compliance-silent
"""Shared bootstrap for the StartupOS skill wrappers.

Replaces four copies of the same 45 lines, each of which carried the same two
fatal bugs:

1.  The template archive URL was
    `https://raw.githubusercontent.com/.../main/archive/refs/heads/main.zip`.
    `GITHUB_RAW_BASE` already ends in `/main`, and raw.githubusercontent does
    not serve archives at all — that URL returns 404. Verified.
2.  The zip filter looked for `core/skills/startup_os/templates/`, but the
    templates moved to `core/skills/.rok/startup_os/templates/`. Zero matches.

Between them, `sync_templates()` printed `[Success] synced 0 templates` and
`compile_instance` then died with "Missing template folder". The skill could
not run on a clean machine.

Templates no longer come over the network at all: they ship inside this skill
directory, which the protocol installer refreshes on every init, so copying
them locally is both faster and always consistent with the code being run.
"""

import hashlib
import io
import json
import os
import shutil
import sys
import urllib.request
import zipfile

PROTOCOL_REPO = "RokctAI/The-Rokct-Protocol"
# Pinned by tools/gen_protocol_lock.py - do not edit these constants by hand.
PROTOCOL_REF = "42c7e71a78aa6eb6350ada15987ed53cc001ca1f"
# STARTUPOS_PROTOCOL_REF overrides the pin for development only; the embedded
# hashes cannot vouch for other refs, so overriding also requires
# STARTUPOS_ALLOW_UNPINNED=1 and loudly disables integrity verification.
_RUNTIME_REF = os.environ.get("STARTUPOS_PROTOCOL_REF", PROTOCOL_REF)
UNPINNED = _RUNTIME_REF != PROTOCOL_REF
GITHUB_RAW_BASE = f"https://raw.githubusercontent.com/{PROTOCOL_REPO}/{_RUNTIME_REF}"
ENGINE_PATH = "core/utils/startup_os"

# Every module the engine needs. Adding a module here is what makes it
# available to a remote install — the old list named three files and would
# silently ship a broken engine the moment a fourth was introduced.
ENGINE_MODULES = (
    "__init__.py",
    "errors.py",
    "paths.py",
    "parser.py",
    "jurisdictions.py",
    "compliance.py",
    "template_engine.py",
    "documents.py",
    "safe_io.py",
    "schemas.py",
    "compiler.py",
    "agent_bridge.py",
)

# Expected SHA-256 of every engine module at PROTOCOL_REF, keyed by
# repo-relative path. Pinned by tools/gen_protocol_lock.py.
EXPECTED_SHA256 = {
    "core/utils/startup_os/__init__.py": "eacdae45be5b18a599c4f84cf456158f01b654213b6a7579ac78eeff18dfdfb3",
    "core/utils/startup_os/errors.py": "5c7c935c73207f90cfb3312737030ad9bc0334af395691691f5c03fbc50029a9",
    "core/utils/startup_os/paths.py": "aca9b98fba636d172e9ee0ae192d0ae2946bdcba5b16c049c89845bcbd51cacd",
    "core/utils/startup_os/parser.py": "8df98fb9a1da1315fb03433692f253be00d866979b848298c29dde4c4f7cccf8",
    "core/utils/startup_os/jurisdictions.py": "d45daa8f2160d25f2329f2b4be3ceb12e35301b0fde5a8cca32b24c6b0ca97d0",
    "core/utils/startup_os/compliance.py": "840dfd58c6320eaecffb3fae7d9f1010786fbc1a1b3c5d74ef426be0d218e53d",
    "core/utils/startup_os/template_engine.py": "1237417a8ccdaf27c810c077dd4d7d6c3a6261c2c0b1a88f9204599b9c5fd94d",
    "core/utils/startup_os/documents.py": "3641941d499fe8be0e7059e911ba5f5dabc0e562562d6e7687736e75a94cb2c8",
    "core/utils/startup_os/safe_io.py": "4c9386424374e7bfe4bc7d8461ed11370dbb3c352674227ed8b614163d69435d",
    "core/utils/startup_os/schemas.py": "a29e64cde6ba5cbcb985a1f5148a8c8e634b459b7e916129d57d5ac13287b59d",
    "core/utils/startup_os/compiler.py": "33537b99d5a220ca0da78e31483a89958de2e1e85e67e5e05dbb906ae8dbbd58",
    "core/utils/startup_os/agent_bridge.py": "c1ad9f9dd8f8a16aa147603bb9ac3a3d4774cbac8aa0f23856e228654249679d",
}

LOCKFILE_NAME = "engine.lock.json"
OFFLINE = os.environ.get("STARTUPOS_OFFLINE", "").lower() in ("1", "true", "yes")
FETCH_TIMEOUT = int(os.environ.get("STARTUPOS_FETCH_TIMEOUT", "15"))


def _skill_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _core_dir():
    return os.path.join(_skill_dir(), "core")


def _fetch(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": "StartupOS-Skill", "X-Trace-Id": "compliance"}
    )
    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:
        return response.read()


def _save_lock(core_dir, hashes):
    path = os.path.join(core_dir, LOCKFILE_NAME)
    payload = {"repo": PROTOCOL_REPO, "ref": _RUNTIME_REF, "modules": hashes}
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
    except OSError:
        pass


def _verify_module(module, payload, origin):
    """Abort unless `payload` matches the embedded pin for `module`.

    Skipped only when STARTUPOS_PROTOCOL_REF overrides the pinned ref, which
    itself requires the explicit STARTUPOS_ALLOW_UNPINNED=1 opt-in.
    """
    if UNPINNED:
        return
    expected = EXPECTED_SHA256[f"{ENGINE_PATH}/{module}"]
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected:
        print(
            f"[Error] Integrity check failed for engine module {module} "
            f"({origin}, ref {PROTOCOL_REF}):",
            file=sys.stderr,
        )
        print(f"[Error]   expected sha256 {expected}", file=sys.stderr)
        print(f"[Error]   actual   sha256 {digest}", file=sys.stderr)
        print("[Error] Refusing to run unverified code.", file=sys.stderr)
        sys.exit(1)


def fetch_engine(verbose=True):
    """Download the engine modules into `<skill>/core/`, or use the cache.

    Integrity: every module carries an expected SHA-256 in `EXPECTED_SHA256`,
    pinned to PROTOCOL_REF by tools/gen_protocol_lock.py. Whether a module
    arrives from the network or from the local cache, a hash mismatch aborts —
    the whole fetch-and-import pattern is remote code execution by design, so
    nothing unverified is ever imported. `engine.lock.json` remains as a local
    record of what was installed, but it is no longer the trust root.

    `STARTUPOS_OFFLINE=1` skips the network entirely and runs from cache
    (still verified against the embedded hashes).
    `STARTUPOS_PROTOCOL_REF=<ref>` overrides the pin for development; that
    bypasses integrity verification, so it also requires
    `STARTUPOS_ALLOW_UNPINNED=1` and warns loudly.
    """
    if UNPINNED:
        print(
            f"[Warning] STARTUPOS_PROTOCOL_REF={_RUNTIME_REF} overrides the pinned "
            f"ref {PROTOCOL_REF}; integrity verification is BYPASSED for this run.",
            file=sys.stderr,
        )
        if os.environ.get("STARTUPOS_ALLOW_UNPINNED", "").lower() not in (
            "1",
            "true",
            "yes",
        ):
            print(
                "[Error] Refusing to run unpinned engine code without "
                "STARTUPOS_ALLOW_UNPINNED=1.",
                file=sys.stderr,
            )
            sys.exit(1)

    core_dir = _core_dir()
    os.makedirs(core_dir, exist_ok=True)

    current = {}

    for module in ENGINE_MODULES:
        destination = os.path.join(core_dir, module)
        url = f"{GITHUB_RAW_BASE}/{ENGINE_PATH}/{module}"

        if OFFLINE:
            if not os.path.exists(destination):
                print(
                    f"[Error] STARTUPOS_OFFLINE is set but {module} is not cached.",
                    file=sys.stderr,
                )
                sys.exit(1)
            with open(destination, "rb") as handle:
                payload = handle.read()
            _verify_module(module, payload, "cache")
            current[module] = hashlib.sha256(payload).hexdigest()
            continue

        try:
            payload = _fetch(url)
        except Exception as exc:
            if os.path.exists(destination):
                with open(destination, "rb") as handle:
                    payload = handle.read()
                _verify_module(module, payload, "cache")
                print(
                    f"[Warning] Using verified cached {module} (fetch failed: {exc})",
                    file=sys.stderr,
                )
                current[module] = hashlib.sha256(payload).hexdigest()
                continue
            print(
                f"[Error] Could not fetch engine module {module}: {exc}",
                file=sys.stderr,
            )
            sys.exit(1)

        _verify_module(module, payload, "github")
        current[module] = hashlib.sha256(payload).hexdigest()

        with open(destination, "wb") as handle:
            handle.write(payload)

    _save_lock(core_dir, current)

    skill_dir = _skill_dir()
    if skill_dir not in sys.path:
        sys.path.insert(0, skill_dir)

    if verbose:
        source = "cache" if OFFLINE else f"{PROTOCOL_REPO}@{_RUNTIME_REF}"
        print(f"[StartupOS] Engine ready ({len(ENGINE_MODULES)} modules from {source})")


def _safe_extract_path(base_dir, member_name):
    """Resolve a zip member path, refusing anything that escapes `base_dir`."""
    target = os.path.realpath(os.path.join(base_dir, member_name))
    base = os.path.realpath(base_dir)
    if os.path.commonpath([base, target]) != base:
        raise ValueError(f"Refusing zip member outside the destination: {member_name}")
    return target


def sync_templates(workspace_root, verbose=True):
    """Install the document templates into the workspace.

    Local copy first — the templates live in this skill directory, which the
    protocol installer refreshes from the repo on every init. The network is a
    fallback for the case where the skill was invoked from a bare script.
    """
    destination = os.path.join(workspace_root, "templates")
    local_source = os.path.join(_skill_dir(), "templates")

    if os.path.isdir(local_source):
        count = _copy_tree(local_source, destination)
        if verbose:
            print(f"[StartupOS] Installed {count} templates from the skill directory")
        if count:
            return count
        print(
            "[Warning] Skill template directory is empty; trying the network.",
            file=sys.stderr,
        )

    if OFFLINE:
        print(
            "[Error] No local templates and STARTUPOS_OFFLINE is set.", file=sys.stderr
        )
        sys.exit(1)

    count = _sync_templates_from_github(destination, verbose)
    if count == 0:
        print(
            "[Error] No templates could be installed. The compiler cannot run "
            "without them.\n"
            f"        Expected them at: {local_source}\n"
            "        Or reachable at: "
            f"https://github.com/{PROTOCOL_REPO}/tree/{_RUNTIME_REF}/"
            "core/skills/.rok/startup_os/templates",
            file=sys.stderr,
        )
        sys.exit(1)
    return count


def _copy_tree(source, destination):
    copied = 0
    for directory, _subdirs, filenames in os.walk(source):
        relative = os.path.relpath(directory, source)
        target_dir = (
            destination if relative == "." else os.path.join(destination, relative)
        )
        os.makedirs(target_dir, exist_ok=True)
        for filename in filenames:
            if not filename.endswith(".md"):
                continue
            shutil.copy2(
                os.path.join(directory, filename), os.path.join(target_dir, filename)
            )
            copied += 1
    return copied


def _sync_templates_from_github(destination, verbose):
    """Fallback: pull templates out of the repository archive.

    Note the host: `github.com`, not `raw.githubusercontent.com`, and the path
    prefix now matches where the templates actually live.
    """
    # `archive/<ref>.zip` resolves for branches, tags and commit SHAs alike
    # (the pinned ref is a commit SHA, which `archive/refs/heads/` cannot serve).
    archive_url = f"https://github.com/{PROTOCOL_REPO}/archive/{_RUNTIME_REF}.zip"
    prefix = "core/skills/.rok/startup_os/templates/"

    if verbose:
        print(f"[StartupOS] Fetching templates from {archive_url}")

    try:
        payload = _fetch(archive_url)
    except Exception as exc:
        print(f"[Warning] Template archive fetch failed: {exc}", file=sys.stderr)
        return 0

    count = 0
    os.makedirs(destination, exist_ok=True)
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            for name in archive.namelist():
                if name.endswith("/") or prefix not in name:
                    continue
                relative = name.split(prefix, 1)[1]
                if not relative.endswith(".md"):
                    continue
                target = _safe_extract_path(destination, relative)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "wb") as handle:
                    handle.write(archive.read(name))
                count += 1
    except (zipfile.BadZipFile, ValueError) as exc:
        print(f"[Warning] Template archive is unusable: {exc}", file=sys.stderr)
        return 0

    if verbose:
        print(f"[StartupOS] Installed {count} templates from the archive")
    return count


def prepare(root=None, sync=True, verbose=True):
    """Fetch the engine, import it, and install templates. Returns the `core` module."""
    fetch_engine(verbose=verbose)

    try:
        import core
    except ImportError as exc:
        print(f"[Error] Engine import failed after fetch: {exc}", file=sys.stderr)
        sys.exit(1)

    core.enable_utf8_console()

    if sync:
        from core.paths import resolve_workspace_root

        workspace_root = resolve_workspace_root(root, verbose=verbose)
        os.makedirs(workspace_root, exist_ok=True)
        sync_templates(workspace_root, verbose=verbose)

    return core
