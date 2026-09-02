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
PROTOCOL_REF = "6d7269eee93078c4a0b6e9d7ce304f488519d717"
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
    "polish.py",
    "branding.py",
    "render_pptx.py",
    "render_xlsx.py",
)

# Expected SHA-256 of every engine module at PROTOCOL_REF, keyed by
# repo-relative path. Pinned by tools/gen_protocol_lock.py.
EXPECTED_SHA256 = {
    "core/utils/startup_os/__init__.py": "d43db69d7accd71a58aedaf92ef1613cc8bd66404fd4becbf92a7884f3eb36ad",
    "core/utils/startup_os/errors.py": "ef6952348921a51c90f78c379b927611a808802f6b4b818d7b25a83ab54a53f5",
    "core/utils/startup_os/paths.py": "98767ccdbf10afb1ed3f330b6aea5ed2bcb6c1769124a80f86dc7819adf61cc5",
    "core/utils/startup_os/parser.py": "af881a5a03cf2d0b7bb3251f5a06b5d7ac17772af28b413b7d40b5eaa471ee31",
    "core/utils/startup_os/jurisdictions.py": "5a1632cf877363ce961d8b4d8f7810e35c67a0d0a3c0170e62aef30fe34f9875",
    "core/utils/startup_os/compliance.py": "a62b80ae186075365e0f9507873f792d8a062207b442bb8bf65d4e22569c3050",
    "core/utils/startup_os/template_engine.py": "c665050a1149b7ebc6eb0ad91a2d33a955eaa0edcdba198427419447f958f14f",
    "core/utils/startup_os/documents.py": "ca094c13323b405ca39bbb0768feab546590116e954438468cd6232b56a0fda6",
    "core/utils/startup_os/safe_io.py": "b3afd716283abc9faa2783469a833a0beb8fb5587c0c7dad373c2492efa20368",
    "core/utils/startup_os/schemas.py": "2a9088ae02a07452b428d149dce035fb5c3ef15a9f4047974ddbd4d319de815b",
    "core/utils/startup_os/compiler.py": "8031c6b8dad90334dfdd0d09ed4965c14ab858417bf199fd796c58e8689d5997",
    "core/utils/startup_os/agent_bridge.py": "0e36549068e0361ef62f1bd71ba50dd74666553cf514ce453d5d1101aac5f070",
    "core/utils/startup_os/polish.py": "55c130b9158e709574424939473364d4af2172d90bdd2de57c669d863b191ef5",
    "core/utils/startup_os/branding.py": "c1765bf5f785e097f30253f31b2595c33377bfd5ca00c38e17d502abde3f0836",
    "core/utils/startup_os/render_pptx.py": "aeae1363941415cbef997debf3608628025b5da2abf5f8aaf665aa4125f184bc",
    "core/utils/startup_os/render_xlsx.py": "b7d1283fe1087c04dff09e6b05c75613984eeec2ea9de8c6483b395563287dff",
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
