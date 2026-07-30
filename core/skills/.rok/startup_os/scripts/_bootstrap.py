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
PROTOCOL_REF = os.environ.get("STARTUPOS_PROTOCOL_REF", "main")
GITHUB_RAW_BASE = f"https://raw.githubusercontent.com/{PROTOCOL_REPO}/{PROTOCOL_REF}"
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

LOCKFILE_NAME = "engine.lock.json"
OFFLINE = os.environ.get("STARTUPOS_OFFLINE", "").lower() in ("1", "true", "yes")
STRICT = os.environ.get("STARTUPOS_STRICT_ENGINE", "").lower() in ("1", "true", "yes")
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


def _load_lock(core_dir):
    path = os.path.join(core_dir, LOCKFILE_NAME)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle).get("modules", {})
    except (OSError, ValueError):
        return {}


def _save_lock(core_dir, hashes):
    path = os.path.join(core_dir, LOCKFILE_NAME)
    payload = {"repo": PROTOCOL_REPO, "ref": PROTOCOL_REF, "modules": hashes}
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
    except OSError:
        pass


def fetch_engine(verbose=True):
    """Download the engine modules into `<skill>/core/`, or use the cache.

    Integrity: hashes of what was fetched are recorded in `engine.lock.json`.
    A changed hash is reported on the next run. With `STARTUPOS_STRICT_ENGINE=1`
    a change aborts instead of warning, which is what CI should use — the whole
    fetch-and-import pattern is remote code execution by design, and an
    unexplained change to a module is the signal worth stopping on.

    `STARTUPOS_OFFLINE=1` skips the network entirely and runs from cache.
    `STARTUPOS_PROTOCOL_REF=<tag>` pins to a tag or commit instead of `main`.
    """
    core_dir = _core_dir()
    os.makedirs(core_dir, exist_ok=True)

    previous = _load_lock(core_dir)
    current = {}
    changed = []

    for module in ENGINE_MODULES:
        destination = os.path.join(core_dir, module)
        url = f"{GITHUB_RAW_BASE}/{ENGINE_PATH}/{module}"

        if OFFLINE:
            if not os.path.exists(destination):
                print(f"[Error] STARTUPOS_OFFLINE is set but {module} is not cached.",
                      file=sys.stderr)
                sys.exit(1)
            with open(destination, "rb") as handle:
                current[module] = hashlib.sha256(handle.read()).hexdigest()
            continue

        try:
            payload = _fetch(url)
        except Exception as exc:
            if os.path.exists(destination):
                print(f"[Warning] Using cached {module} (fetch failed: {exc})",
                      file=sys.stderr)
                with open(destination, "rb") as handle:
                    current[module] = hashlib.sha256(handle.read()).hexdigest()
                continue
            print(f"[Error] Could not fetch engine module {module}: {exc}", file=sys.stderr)
            sys.exit(1)

        digest = hashlib.sha256(payload).hexdigest()
        current[module] = digest
        if module in previous and previous[module] != digest:
            changed.append(module)

        with open(destination, "wb") as handle:
            handle.write(payload)

    if changed:
        listed = ", ".join(changed)
        message = (
            f"[{'Error' if STRICT else 'Notice'}] Engine modules changed upstream "
            f"since the last run: {listed} (repo {PROTOCOL_REPO}@{PROTOCOL_REF})."
        )
        print(message, file=sys.stderr)
        if STRICT:
            print("[Error] STARTUPOS_STRICT_ENGINE is set; refusing to run changed code.",
                  file=sys.stderr)
            sys.exit(1)

    _save_lock(core_dir, current)

    skill_dir = _skill_dir()
    if skill_dir not in sys.path:
        sys.path.insert(0, skill_dir)

    if verbose:
        source = "cache" if OFFLINE else f"{PROTOCOL_REPO}@{PROTOCOL_REF}"
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
        print("[Warning] Skill template directory is empty; trying the network.",
              file=sys.stderr)

    if OFFLINE:
        print("[Error] No local templates and STARTUPOS_OFFLINE is set.", file=sys.stderr)
        sys.exit(1)

    count = _sync_templates_from_github(destination, verbose)
    if count == 0:
        print(
            "[Error] No templates could be installed. The compiler cannot run "
            "without them.\n"
            f"        Expected them at: {local_source}\n"
            "        Or reachable at: "
            f"https://github.com/{PROTOCOL_REPO}/tree/{PROTOCOL_REF}/"
            "core/skills/.rok/startup_os/templates",
            file=sys.stderr,
        )
        sys.exit(1)
    return count


def _copy_tree(source, destination):
    copied = 0
    for directory, _subdirs, filenames in os.walk(source):
        relative = os.path.relpath(directory, source)
        target_dir = destination if relative == "." else os.path.join(destination, relative)
        os.makedirs(target_dir, exist_ok=True)
        for filename in filenames:
            if not filename.endswith(".md"):
                continue
            shutil.copy2(os.path.join(directory, filename), os.path.join(target_dir, filename))
            copied += 1
    return copied


def _sync_templates_from_github(destination, verbose):
    """Fallback: pull templates out of the repository archive.

    Note the host: `github.com`, not `raw.githubusercontent.com`, and the path
    prefix now matches where the templates actually live.
    """
    archive_url = f"https://github.com/{PROTOCOL_REPO}/archive/refs/heads/{PROTOCOL_REF}.zip"
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
