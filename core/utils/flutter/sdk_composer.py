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

import os
import sys
import subprocess
import json
import shutil
import hashlib

PROJECT_ROOT = os.getcwd()
NL = chr(10)

# SDKs that could not be resolved, cached or installed this run. A composer
# that silently omits an SDK and still exits 0 produces a quietly incomplete
# app; main() exits non-zero when this is non-empty.
FAILED_SDKS = []

# Explicit, loud opt-out for running SDK installers cloned from a mutable ref
# without a sha256 pin - mirrors the engine's STARTUPOS_ALLOW_UNPINNED gate.
ALLOW_UNPINNED_ENV = "ROKCT_ALLOW_UNPINNED_SDKS"

# build_runner has no watchdog of its own and inherits this script's stdin, so
# a wedged or prompting build blocks forever - in CI that squats a runner until
# the job's own multi-hour limit (same failure class as clone_ref's network
# stall, capped there at 600s). 30 minutes covers the largest SDK graphs seen
# so far; raise via env for legitimately slower builds.
BUILD_RUNNER_TIMEOUT_ENV = "ROKCT_BUILD_RUNNER_TIMEOUT"
BUILD_RUNNER_TIMEOUT = int(os.environ.get(BUILD_RUNNER_TIMEOUT_ENV, "1800"))


def _is_commit_sha(ref):
    return (
        bool(ref)
        and len(ref) == 40
        and all(c in "0123456789abcdef" for c in ref.lower())
    )


def enforce_sdk_pin(sdk_name, sdk_config, target_dir, ref):
    """A cloned SDK's install.py is later executed by run_installer(), so
    content fetched over the network must be verifiable before it can run.
    Accepts the SDK when any of these hold:
      - the composer.json entry carries "sha256" (SHA-256 of the SDK's
        install.py) and it matches the extracted file;
      - the clone ref is a full 40-hex commit SHA (immutable content);
      - ROKCT_ALLOW_UNPINNED_SDKS=1 explicitly (and loudly) opts out.
    Anything else aborts the compose before any installer can execute."""
    expected = ""
    if isinstance(sdk_config, dict):
        expected = (sdk_config.get("sha256") or "").lower()
    installer = os.path.join(target_dir, "install.py")
    if expected:
        if not os.path.exists(installer):
            print(
                f"[!] {sdk_name}: composer.json pins install.py to sha256 {expected}, "
                f"but the cloned SDK has no install.py. Refusing to continue.",
                file=sys.stderr,
            )
            sys.exit(1)
        with open(installer, "rb") as f:
            data = f.read()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            # composer.json pins are computed from the committed (LF) blob.
            # Git on windows-latest ships core.autocrlf=true, so the clone
            # materializes install.py with CRLF endings - byte-identical
            # content, different on-disk sha256. Re-hash with CRLF->LF
            # normalization before rejecting, so the same pin verifies on
            # every OS; genuinely different content still fails both hashes.
            normalized = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
            if normalized != expected:
                print(
                    f"[!] Integrity check failed for {sdk_name} install.py (ref {ref}):",
                    file=sys.stderr,
                )
                print(f"[!]   expected sha256 {expected}", file=sys.stderr)
                print(f"[!]   actual   sha256 {actual}", file=sys.stderr)
                print(
                    f"[!]   actual   sha256 {normalized} (after CRLF->LF normalization)",
                    file=sys.stderr,
                )
                print(
                    "[!] Refusing to execute unverified SDK installer.", file=sys.stderr
                )
                sys.exit(1)
            print(
                f"[+] Verified {sdk_name} install.py against pinned sha256 "
                "(after CRLF->LF normalization of a CRLF checkout)."
            )
            return
        print(f"[+] Verified {sdk_name} install.py against pinned sha256.")
        return
    if _is_commit_sha(ref):
        return
    if os.environ.get(ALLOW_UNPINNED_ENV, "").lower() in ("1", "true", "yes"):
        print(
            f"[!] WARNING: {sdk_name} was cloned from mutable ref '{ref}' without a sha256 pin; "
            f"proceeding because {ALLOW_UNPINNED_ENV} is set. Its install.py runs UNVERIFIED."
        )
        return
    print(
        f"[!] {sdk_name} was cloned from mutable ref '{ref}' and its install.py is unpinned.",
        file=sys.stderr,
    )
    print(
        '[!] Pin it: set "ref" to a full commit SHA or add "sha256" (of install.py) to its '
        "composer.json entry.",
        file=sys.stderr,
    )
    print(
        f"[!] To run unpinned anyway, set {ALLOW_UNPINNED_ENV}=1 explicitly.",
        file=sys.stderr,
    )
    sys.exit(1)


# Durable composer/installer state. Lives INSIDE .rokct/cache/ deliberately:
# cache/ is on end_protocol.py's keep-whitelist, so the state survives session
# cleanup, and the recorded versions/hashes describe the cached SDK content -
# they should share the cache's fate (and its git-tracking policy: a host that
# tracks its cache for self-containment tracks the state with it; a host that
# gitignores its cache rebuilds both on the next compose, exactly as today).
# The legacy location at .rokct/'s own root sat outside every cleanup
# guarantee and outside the tracked-cache flow; it is migrated on first read.
STATE_FILE = os.path.join(PROJECT_ROOT, ".rokct", "cache", "install_state.json")
LEGACY_STATE_FILE = os.path.join(PROJECT_ROOT, ".rokct", "install_state.json")


def migrate_legacy_state():
    """One-time move of .rokct/install_state.json -> .rokct/cache/. Existing
    machines keep their recorded hash state instead of starting over."""
    if os.path.exists(LEGACY_STATE_FILE) and not os.path.exists(STATE_FILE):
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            shutil.move(LEGACY_STATE_FILE, STATE_FILE)
            print(
                "[*] Migrated .rokct/install_state.json -> .rokct/cache/install_state.json"
            )
        except Exception as e:
            print(f"[!] Could not migrate legacy install_state.json: {e}")


def load_install_state():
    migrate_legacy_state()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"packages": {}}


def save_install_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def clean_sdk_name(name):
    if name.endswith("_sdk"):
        return name[:-4]
    if name.endswith("_sdks"):
        return name[:-5]
    return name


def extract_repo_name(git_url):
    url_path = git_url.rstrip("/")
    if url_path.endswith(".git"):
        url_path = url_path[:-4]
    return os.path.basename(url_path)


def get_subpath_in_repo(local_path, repo_name):
    normalized = local_path.replace("\\", "/").strip("/")
    parts = normalized.split("/")
    for idx, part in enumerate(parts):
        if part.lower() == repo_name.lower():
            return "/".join(parts[idx + 1 :])
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return normalized


def authenticated_git_url(git_url):
    """Inject MONOREPO_PAT for github.com HTTPS clones so private SDK repos
    (all SDKs are now private) resolve without ambient git credentials —
    same token/URL shape universal-flutter-build.yml already uses for its
    own private-repo clone path."""
    token = os.environ.get("MONOREPO_PAT")
    if token and git_url.startswith("https://github.com/"):
        return git_url.replace(
            "https://github.com/", f"https://x-access-token:{token}@github.com/"
        )
    return git_url


def clone_ref(git_url, ref, dest_dir):
    """Clone git_url at ref into dest_dir. Branch and tag refs take the exact
    shallow path used before (`git clone -b <ref> --depth 1`); when that
    fails - most notably because ref is a commit SHA, which `git clone -b`
    does not accept - fall back to a full clone followed by
    `git checkout <ref>`. Raises on failure (subprocess.CalledProcessError,
    or subprocess.TimeoutExpired when a clone stalls on the network);
    the caller decides how to fail the build. Same helper as the frappe
    composer's clone_ref() (core/utils/frappe/compose_backend.py) - kept as a
    local copy since each composer is fetched and run standalone.

    git has no network-stall timeout of its own, so a dead TCP connection
    mid-clone hangs forever - in CI that squats a runner for hours (see the
    universal lint/build "Compose SDK Modules" steps). The 10-minute cap
    turns a stall into a loud, retryable failure."""
    try:
        subprocess.run(
            ["git", "clone", "-b", ref, "--depth", "1", git_url, dest_dir],
            check=True,
            timeout=600,
        )
        return
    except subprocess.CalledProcessError:
        print(
            f"[*] `git clone -b {ref}` failed (ref is not a branch/tag?). Retrying as full clone + checkout, which also accepts commit SHAs..."
        )
    if os.path.exists(dest_dir):

        def remove_readonly(func, path, excinfo):
            import stat

            os.chmod(path, stat.S_IWRITE)
            func(path)

        shutil.rmtree(dest_dir, onerror=remove_readonly)
    subprocess.run(["git", "clone", git_url, dest_dir], check=True, timeout=600)
    subprocess.run(["git", "-C", dest_dir, "checkout", ref], check=True)


def check_git_availability(git_url):
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--exit-code", "-h", git_url, "HEAD"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def resolve_app_type():
    """This host app's own flavor marker ('driver', 'manager', ...), read from
    .rokct/config/app_type. Mirrors sdk_installer_base.py's resolve_app_type()
    - kept as a local copy here rather than imported, since sdk_composer.py and
    sdk_installer_base.py are fetched and used independently by compose.py."""
    path = os.path.join(PROJECT_ROOT, ".rokct", "config", "app_type")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            value = f.read().strip().lower()
            return value or None
    return None


def strip_unused_role_folders(target_dir, sdk_name):
    """After vendoring an SDK's full source into .rokct/cache/, remove role
    folders under lib/src/ that don't apply to this host app - keep common/
    and this app's own role only, matching the sibling-folder convention
    (lib/src/common/, lib/src/driver/, lib/src/manager/, ...).

    Why: the cache is intentionally tracked (not gitignored) so developers
    can actually read the code their app is built against, since CI composes
    fresh and never leaves a browsable copy anywhere else. Vendoring every
    role's code in unstripped defeats that purpose for the roles that don't
    apply - a driver app's cache showing manager's business logic is exactly
    the clutter this exists to avoid, and once cache is committed, an
    unstripped copy would carry other-role code into that app's own repo
    history, not just a local developer's working copy.

    Only strips a role folder that's a genuine sibling of common/ under
    lib/src/ AND is declared as an app_type persona in this SDK's own
    manifest.json (see sdk_validator.py's parse_manifests() for the same
    read). Safe no-op if the app's own role can't be resolved, or this SDK
    doesn't declare that role at all - stripping without that confirmation
    risks deleting something the app actually needs.
    """
    current_role = resolve_app_type()
    if not current_role:
        return

    manifest_path = os.path.join(target_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        return
    try:
        with open(manifest_path, "r", encoding="utf-8-sig") as f:
            manifest = json.load(f)
    except Exception:
        return

    declared_personas = list((manifest.get("app_type") or {}).keys())
    if current_role not in declared_personas:
        # This SDK doesn't declare the app's role as a persona - nothing to
        # strip; stripping blind here could remove code the app actually uses.
        return

    lib_src = os.path.join(target_dir, "lib", "src")
    if not os.path.isdir(lib_src):
        return

    for persona in declared_personas:
        if persona == current_role:
            continue
        persona_dir = os.path.join(lib_src, persona)
        if os.path.isdir(persona_dir):
            shutil.rmtree(persona_dir)
            print(
                f"[*] Stripped unused role folder lib/src/{persona}/ from {sdk_name} (app role: {current_role})"
            )


# --- Version-aware cache reconciliation -------------------------------------
# Hosts are sold with .rokct/cache/ tracked, so a compose run must not blindly
# re-extract (and thereby clobber) cached SDK source. Per SDK, the recorded
# manifest version + content hash in install_state.json decide:
#   newer incoming version  -> delete the old cache dir, re-extract fresh
#   same version, unmodified -> leave the cached copy (faster, keeps the
#                               sold-repo self-contained property)
#   same version, MODIFIED   -> leave it, with a loud warning - manual
#                               modifications are never silently clobbered.
#                               Exception: a mismatched cache with NO lib/ is
#                               structurally corrupt (stripped by the old
#                               unanchored lib/ gitignore), not modified - it
#                               is deleted and re-extracted.

# Noise excluded from the cache content hash: toolchain outputs that differ
# per machine/run without the SDK's actual content changing.
HASH_EXCLUDED_DIRS = {".git", ".dart_tool", "build", "__pycache__", "node_modules"}
HASH_EXCLUDED_FILES = {
    "pubspec.lock",
    ".DS_Store",
    ".flutter-plugins",
    ".flutter-plugins-dependencies",
}


def cache_dir_hash(d):
    if not os.path.isdir(d):
        return None
    h = hashlib.sha256()
    for root, dirs, files in os.walk(d):
        dirs[:] = sorted(x for x in dirs if x not in HASH_EXCLUDED_DIRS)
        for f in sorted(files):
            if f in HASH_EXCLUDED_FILES or f.endswith(".pyc"):
                continue
            p = os.path.join(root, f)
            h.update(os.path.relpath(p, d).encode())
            with open(p, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()[:16]


def parse_version(v):
    """'1.2.3' -> (1, 2, 3); tolerant of junk (unparseable -> (0,))."""
    try:
        return tuple(int(part) for part in str(v).strip().split("."))
    except Exception:
        return (0,)


def read_manifest_version(sdk_dir):
    manifest_path = os.path.join(sdk_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8-sig") as f:
            return json.load(f).get("version")
    except Exception:
        return None


def should_extract(sdk_name, src_dir, target_dir, state, decisions):
    """Decide whether to (re-)extract this SDK into its cache dir.

    Returns True when the existing rmtree+copytree path should run. Records
    the per-SDK decision in `decisions` so record_sdk_cache_state() knows
    which entries to (not) update.
    """
    clean_name = clean_sdk_name(sdk_name)
    if not os.path.isdir(target_dir):
        decisions[clean_name] = "extracted"
        return True

    incoming_version = read_manifest_version(src_dir)
    entry = state.get("sdk_cache", {}).get(clean_name)
    cached_version = (
        entry.get("version") if entry else read_manifest_version(target_dir)
    )

    if incoming_version and parse_version(incoming_version) > parse_version(
        cached_version
    ):
        print(
            f"[*] {sdk_name}: manifest version {incoming_version} is newer than cached {cached_version} - deleting old cache and re-extracting."
        )
        decisions[clean_name] = "extracted"
        return True

    if (
        incoming_version
        and cached_version
        and parse_version(incoming_version) < parse_version(cached_version)
    ):
        print(
            f"[*] {sdk_name}: cached copy ({cached_version}) is newer than incoming manifest ({incoming_version}) - leaving cached copy in place."
        )
        decisions[clean_name] = "left-newer"
        return False

    # Same version (or no usable version info): keep the cached copy, but
    # check for manual modifications against the recorded hash.
    if entry and entry.get("hash"):
        current_hash = cache_dir_hash(target_dir)
        if current_hash != entry["hash"]:
            # A mismatched cache with no lib/ at all is not a precious local
            # modification - it is a stripped artifact (hosts whose old
            # unanchored `lib/` gitignore rule ate .rokct/cache/<sdk>/lib/)
            # and can never compose. Pinning it just breaks every build, so
            # treat it as corrupt and take the normal fresh-extract path
            # (the caller rmtree's the target before copying).
            if not os.path.isdir(os.path.join(target_dir, "lib")):
                print(
                    f"[!] {sdk_name}: cached copy at {os.path.relpath(target_dir, PROJECT_ROOT)} has no lib/ (content hash mismatch, version {cached_version} unchanged) - treating as corrupt, deleting and re-extracting."
                )
                decisions[clean_name] = "extracted"
                return True
            print(
                f"[!] WARNING: {sdk_name}: cached copy at {os.path.relpath(target_dir, PROJECT_ROOT)} has LOCAL MODIFICATIONS (content hash mismatch, version {cached_version} unchanged) - leaving it in place, NOT refetching. Delete the folder to force a clean re-extract."
            )
            decisions[clean_name] = "left-modified"
            return False
        print(
            f"[*] {sdk_name}: cache is up to date (version {cached_version}, unmodified) - leaving cached copy in place."
        )
        decisions[clean_name] = "left-unmodified"
        return False

    # Cache exists but predates hash tracking: adopt it as the baseline
    # rather than clobbering it - it may carry manual modifications.
    print(
        f"[*] {sdk_name}: existing cache has no recorded state - adopting current copy as baseline (no re-extract)."
    )
    decisions[clean_name] = "adopted"
    return False


def record_sdk_cache_state(decisions):
    """Persist each reconciled SDK's manifest version + content hash.

    Re-read the state fresh before writing: the installers (which run between
    reconciliation and this call) share the same file. An SDK left in place
    because of local modifications keeps its OLD baseline, so the
    modification warning persists on every compose instead of being
    silently absorbed."""
    if not decisions:
        return
    state = load_install_state()
    sdk_cache = state.setdefault("sdk_cache", {})
    updated = 0
    for clean_name, decision in decisions.items():
        if decision == "left-modified":
            continue
        target_dir = os.path.join(PROJECT_ROOT, ".rokct", "cache", clean_name)
        if not os.path.isdir(target_dir):
            continue
        sdk_cache[clean_name] = {
            "version": read_manifest_version(target_dir),
            "hash": cache_dir_hash(target_dir),
        }
        updated += 1
    save_install_state(state)
    print(
        f"[*] Recorded cache state for {updated} SDK(s) in {os.path.relpath(STATE_FILE, PROJECT_ROOT)}"
    )


# --- SDK compliance docs ------------------------------------------------------
# SDK repos generate per-stack compliance docs INSIDE each stack directory:
# <module>/<stack>/docs/api/*.md for stack in {dart,frappe,nextjs} (filenames
# stay flattened-from-repo-root, e.g. fav_dart_lib_src_di_fav_di.md). This is
# the flutter composer, so the host shell's flavor is always the dart stack:
# compose stages ONLY the dart docs into .rokct/cache/_docs/<repo_name>/dart/
# while the clone is still on disk (only the <module>/dart subtree survives
# into the per-SDK cache), then ensure_docs() merges every staged repo's docs
# into <shell_root>/docs/api/ - so app shells carry their own flavor's
# compliance docs without ever running the compliance scanner themselves.
# frappe/nextjs docs are NOT taken: they belong to the shells those stacks'
# own composers produce. (An earlier composer staged every stack and wrote
# them to <shell_root>/<stack>/docs/api/; ensure_docs migrates shells off
# that layout via the ownership manifest.)
# Staged under cache/ deliberately, same rationale as install_state.json: it
# shares the cache's cleanup whitelist and git-tracking policy.

DOCS_STAGE_DIRNAME = "_docs"
DOC_STACKS = ("dart", "frappe", "nextjs")
# The flavor whose docs this composer takes. The flutter composer only ever
# composes flutter shells, so this is a constant - no marker file needed
# (and .rokct/config/app_type is a persona/role marker, NOT a stack name).
HOST_STACK = "dart"
# Manifest lives INSIDE .rokct/cache/ for the same reason as
# install_state.json: cache/ is on end_protocol.py's keep-whitelist, so the
# ownership record survives session cleanup and shares the cache's
# git-tracking policy.
DOCS_MANIFEST_NAME = "composed_docs.json"  # <shell_root>/.rokct/cache/
LEGACY_DOCS_MANIFEST_NAME = ".composed_docs.json"  # old <shell_root>/docs/api/


def stage_repo_docs(repo_source_dir, repo_name, cache_base):
    """Stage one SDK repo's compliance docs into
    .rokct/cache/_docs/<repo_name>/dart/*.md - ONLY the host flavor's
    (HOST_STACK, dart) docs; frappe/nextjs docs belong to those stacks' own
    shells and are left behind with the clone.

    Three source layouts are recognized, newest first:
      1. current: <module>/dart/docs/api/*.md for every top-level module
      2. previous: repo-root docs/api/dart/*.md (unmigrated repos)
      3. legacy:   repo-root FLAT docs/api/*.md, mapped to a stack by
         filename token (see _stack_for_legacy_doc); only files mapping to
         dart are taken - other stacks' files are skipped silently, files
         with no recognizable token are reported and left out
    All three are unioned so mid-migration repos keep working; a within-repo
    duplicate warns and the later layout in the list above wins.

    Called once per unique repo (several composer.json SDK entries can point
    at the same repo). A repo with no docs is skipped silently - and any
    previously staged copy for it is dropped as stale. Docs are a bonus
    artifact of compose: failure here must NEVER fail the compose, so the
    whole body is fenced with a warning instead.
    """
    stage_dir = os.path.join(cache_base, DOCS_STAGE_DIRNAME, repo_name)
    try:
        if os.path.isdir(stage_dir):
            shutil.rmtree(stage_dir)
        found = {}  # "<stack>/<name>.md" -> absolute source path

        def collect(stack, name, path):
            rel = "%s/%s" % (stack, name)
            if rel in found:
                print(
                    f"[!] WARNING: {repo_name} provides {rel} from more than one layout - later layout wins."
                )
            found[rel] = path

        # 1. Current layout: <module>/dart/docs/api/*.md (host flavor only)
        for module in sorted(os.listdir(repo_source_dir)):
            module_dir = os.path.join(repo_source_dir, module)
            if module.startswith(".") or not os.path.isdir(module_dir):
                continue
            api_dir = os.path.join(module_dir, HOST_STACK, "docs", "api")
            if not os.path.isdir(api_dir):
                continue
            for name in sorted(os.listdir(api_dir)):
                path = os.path.join(api_dir, name)
                if name.endswith(".md") and os.path.isfile(path):
                    collect(HOST_STACK, name, path)

        root_api = os.path.join(repo_source_dir, "docs", "api")
        if os.path.isdir(root_api):
            # 2. Previous layout: repo-root docs/api/dart/*.md (host flavor only)
            stack_dir = os.path.join(root_api, HOST_STACK)
            if os.path.isdir(stack_dir):
                for name in sorted(os.listdir(stack_dir)):
                    path = os.path.join(stack_dir, name)
                    if name.endswith(".md") and os.path.isfile(path):
                        collect(HOST_STACK, name, path)
            # 3. Legacy FLAT docs/api/*.md, mapped by filename token. Files
            # mapping to another stack are simply not this shell's docs -
            # skip them without noise; only an unmappable file is reported.
            for name in sorted(os.listdir(root_api)):
                path = os.path.join(root_api, name)
                if not os.path.isfile(path) or not name.endswith(".md"):
                    continue
                stack = _stack_for_legacy_doc(name)
                if not stack:
                    print(
                        f"[*] {repo_name}: legacy doc {name} has no recognizable stack token - leaving it out."
                    )
                    continue
                if stack != HOST_STACK:
                    continue
                collect(stack, name, path)

        if not found:
            return
        for rel, src in found.items():
            dest = os.path.join(stage_dir, *rel.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
        print(
            f"[*] Staged {len(found)} compliance doc(s) from {repo_name} into {os.path.relpath(stage_dir, PROJECT_ROOT)}"
        )
    except Exception as e:
        print(
            f"[!] Could not stage compliance docs from {repo_name}: {e} (compose continues)"
        )


def _stack_for_legacy_doc(filename):
    """Map a pre-restructure FLAT docs/api/*.md filename to its stack dir by
    filename token: dart / frappe(py) / nextjs(ts). The stem is padded with
    underscores so a trailing token (e.g. auth_dart.md) still matches.
    Returns None when no token matches - the caller leaves that file out."""
    stem = os.path.splitext(filename)[0].lower()
    haystack = "_%s_" % stem
    if "_dart_" in haystack:
        return "dart"
    if "_frappe_" in haystack or "_py_" in haystack:
        return "frappe"
    if "_nextjs_" in haystack or "_ts_" in haystack:
        return "nextjs"
    return None


def _prune_empty_dirs_up_to(path, stop_dir):
    """Remove empty directories from `path` upward, stopping (exclusive) at
    stop_dir. Stops at the first non-empty directory."""
    stop_dir = os.path.abspath(stop_dir)
    d = os.path.abspath(path)
    while d != stop_dir and d.startswith(stop_dir + os.sep):
        try:
            os.rmdir(d)
        except OSError:
            break
        d = os.path.dirname(d)


def _cleanup_legacy_composed_docs():
    """One-time migration of shells composed before the per-stack nesting:
    the old layout wrote docs to <shell_root>/docs/api/<stack>/ with the
    manifest at docs/api/.composed_docs.json. Delete exactly the files that
    old manifest owns (never anything else), drop the old manifest, and prune
    the directories it emptied - the new compose then writes the host
    flavor's docs to <shell_root>/docs/api/."""
    old_root = os.path.join(PROJECT_ROOT, "docs", "api")
    old_manifest = os.path.join(old_root, LEGACY_DOCS_MANIFEST_NAME)
    if not os.path.exists(old_manifest):
        return
    try:
        with open(old_manifest, "r", encoding="utf-8") as f:
            owned = json.load(f).get("files", [])
    except Exception:
        owned = []
    removed = 0
    for rel in owned:
        path = os.path.join(old_root, *rel.split("/"))
        if os.path.isfile(path):
            os.remove(path)
            removed += 1
    os.remove(old_manifest)
    for stack in DOC_STACKS:
        _prune_empty_dirs_up_to(os.path.join(old_root, stack), PROJECT_ROOT)
    _prune_empty_dirs_up_to(old_root, PROJECT_ROOT)
    print(
        f"[*] Migrated composed docs off old docs/api/ layout: removed {removed} old composed doc(s)."
    )


def ensure_docs():
    """Merge every staged SDK repo's host-flavor compliance docs (see
    stage_repo_docs) into <shell_root>/docs/api/ - the shell root's own docs
    tree, with no per-stack nesting: a flutter shell carries only dart docs.

    Same ownership idiom as ensure_host_readme()'s marker block, in manifest
    form: <shell_root>/.rokct/cache/composed_docs.json lists exactly the
    files the composer wrote (as paths relative to the shell root), and on
    each run owned files no longer produced are deleted before the new set is
    written - so a doc removed upstream disappears from the shell on the next
    compose. Files the manifest does not list are the host's own and are
    never touched. That same stale-removal migrates shells composed by the
    interim per-stack composer (owned <stack>/docs/api/*.md entries are no
    longer produced, so they are deleted and their emptied dart/, frappe/
    and nextjs/ directories pruned). Older shells still on the original
    docs/api/<stack>/ layout are migrated first (see
    _cleanup_legacy_composed_docs); an interim manifest at
    .rokct/composed_docs.json (same shell-root-relative format, briefly the
    manifest home before landing on cache/) is folded into the owned set and
    deleted. Union across repos; the flattened filenames are module-prefixed
    so collisions are unlikely - on collision, last write wins with a printed
    warning. Idempotent, and a failure here never fails the compose.
    """
    stage_root = os.path.join(PROJECT_ROOT, ".rokct", "cache", DOCS_STAGE_DIRNAME)
    manifest_path = os.path.join(PROJECT_ROOT, ".rokct", "cache", DOCS_MANIFEST_NAME)
    interim_manifest_path = os.path.join(PROJECT_ROOT, ".rokct", DOCS_MANIFEST_NAME)
    try:
        _cleanup_legacy_composed_docs()

        # Collect the incoming doc set: {"docs/api/<file>.md": staged
        # source}. stage_repo_docs stages only HOST_STACK docs (under a
        # <repo>/dart/ stage dir); stage trees written by earlier composer
        # versions may also hold frappe/ and nextjs/ dirs - those are not
        # this shell's flavor and are ignored. The flat fallback below only
        # covers stage trees left behind by the pre-normalization composer.
        incoming = {}
        if os.path.isdir(stage_root):
            for repo_name in sorted(os.listdir(stage_root)):
                repo_dir = os.path.join(stage_root, repo_name)
                if not os.path.isdir(repo_dir):
                    continue
                stack_dir = os.path.join(repo_dir, HOST_STACK)
                if os.path.isdir(stack_dir):
                    for name in sorted(os.listdir(stack_dir)):
                        if not name.endswith(".md"):
                            continue
                        rel = "docs/api/%s" % name
                        if rel in incoming:
                            print(
                                f"[!] WARNING: docs collision on {rel} - {repo_name}'s copy wins (last write)."
                            )
                        incoming[rel] = os.path.join(stack_dir, name)
                # Fallback for stale FLAT stage trees (pre-normalization),
                # mapped to a stack by filename token; only host-flavor
                # files are taken.
                for name in sorted(os.listdir(repo_dir)):
                    path = os.path.join(repo_dir, name)
                    if not os.path.isfile(path) or not name.endswith(".md"):
                        continue
                    stack = _stack_for_legacy_doc(name)
                    if not stack:
                        print(
                            f"[*] {repo_name}: legacy doc {name} has no recognizable stack token - leaving it out."
                        )
                        continue
                    if stack != HOST_STACK:
                        continue
                    rel = "docs/api/%s" % name
                    if rel in incoming:
                        print(
                            f"[!] WARNING: docs collision on {rel} - {repo_name}'s copy wins (last write)."
                        )
                    incoming[rel] = path

        # Owned set: the current manifest, plus (once) the interim
        # .rokct/composed_docs.json - same shell-root-relative format, so its
        # entries fold straight into stale-removal and its file is dropped.
        owned = []
        for path in (manifest_path, interim_manifest_path):
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    owned.extend(json.load(f).get("files", []))
            except Exception:
                pass
        if os.path.exists(interim_manifest_path):
            os.remove(interim_manifest_path)
            print(
                "[*] Migrated interim manifest .rokct/composed_docs.json -> .rokct/cache/composed_docs.json"
            )

        # Delete owned files no longer produced. Never touch unowned files.
        removed = 0
        for rel in owned:
            if rel in incoming:
                continue
            path = os.path.join(PROJECT_ROOT, *rel.split("/"))
            if os.path.isfile(path):
                os.remove(path)
                removed += 1
                _prune_empty_dirs_up_to(os.path.dirname(path), PROJECT_ROOT)

        if not incoming:
            if owned:
                if os.path.exists(manifest_path):
                    os.remove(manifest_path)
                print(
                    f"[*] composed docs: removed {removed} stale composed doc(s); no SDK docs staged."
                )
            return

        written = 0
        for rel in sorted(incoming):
            dest = os.path.join(PROJECT_ROOT, *rel.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(incoming[rel], dest)
            written += 1

        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({"files": sorted(incoming.keys())}, f, indent=2)
            f.write(NL)
        summary = f"[*] Composed {written} SDK compliance doc(s) into docs/api/"
        if removed:
            summary += f", removed {removed} stale"
        print(summary)
    except Exception as e:
        print(f"[!] Could not compose SDK docs: {e} (compose continues)")


def resolve_and_cache_sdks(sdks):
    cache_base = os.path.join(PROJECT_ROOT, ".rokct", "cache")
    os.makedirs(cache_base, exist_ok=True)

    state = load_install_state()
    decisions = {}

    git_groups = {}
    local_sdks = []

    for sdk in sdks:
        if not isinstance(sdk, dict):
            local_sdks.append(
                {"name": sdk, "path": f"../SDKs/{clean_sdk_name(sdk)}/dart"}
            )
            continue

        source = sdk.get("source", "local")
        if source == "git" and sdk.get("git"):
            git_url = sdk["git"]
            if git_url not in git_groups:
                git_groups[git_url] = []
            git_groups[git_url].append(sdk)
        else:
            local_sdks.append(sdk)

    # Process Git Groups
    for git_url, group_sdks in git_groups.items():
        repo_name = extract_repo_name(git_url)
        temp_repo_dir = os.path.join(cache_base, f"{repo_name}_sdk")

        # Check if repo exists locally in the parent folder of PROJECT_ROOT
        workspace_parent = os.path.dirname(PROJECT_ROOT)
        local_repo_path = os.path.join(workspace_parent, repo_name)

        is_local_available = os.path.exists(local_repo_path)

        if is_local_available:
            print(
                f"[*] Found local repository for {repo_name} at {local_repo_path}. Using local copy."
            )
            repo_source_dir = local_repo_path
        else:
            ref = group_sdks[0].get("ref", "main")
            print(f"[*] Fetching repository {git_url} into {temp_repo_dir}...")
            try:

                def remove_readonly(func, path, excinfo):
                    import stat

                    os.chmod(path, stat.S_IWRITE)
                    func(path)

                if os.path.exists(temp_repo_dir):
                    shutil.rmtree(temp_repo_dir, onerror=remove_readonly)
                clone_ref(authenticated_git_url(git_url), ref, temp_repo_dir)
                repo_source_dir = temp_repo_dir
            except Exception as e:
                print(f"[!] Failed to clone {git_url}: {e}")
                sys.exit(1)

        # Stage this repo's host-flavor compliance docs (<module>/dart/docs/
        # api/, plus legacy layouts) while the repo is on disk - once per
        # unique repo, never fatal on failure.
        stage_repo_docs(repo_source_dir, repo_name, cache_base)

        # Extract each SDK
        for sdk in group_sdks:
            sdk_name = sdk["name"]
            clean_name = clean_sdk_name(sdk_name)
            target_dir = os.path.join(cache_base, clean_name)

            local_path = sdk.get("path", "")
            subpath = get_subpath_in_repo(local_path, repo_name)
            src_dir = os.path.join(repo_source_dir, *subpath.split("/"))

            if os.path.exists(src_dir):
                if not should_extract(sdk_name, src_dir, target_dir, state, decisions):
                    continue
                print(f"[+] Extracting {sdk_name} from {subpath} to {target_dir}...")
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir)
                shutil.copytree(src_dir, target_dir)
                strip_unused_role_folders(target_dir, sdk_name)
                if not is_local_available:
                    # Content came from a network clone - enforce the pin
                    # before its install.py can ever be executed.
                    enforce_sdk_pin(
                        sdk_name, sdk, target_dir, group_sdks[0].get("ref", "main")
                    )
            else:
                print(
                    f"[!] Error: Path {subpath} not found in repository {repo_source_dir}"
                )
                FAILED_SDKS.append(sdk_name)

        # Clean up temp repo folder if it was cloned
        if not is_local_available and os.path.exists(temp_repo_dir):

            def remove_readonly(func, path, excinfo):
                import stat

                os.chmod(path, stat.S_IWRITE)
                func(path)

            shutil.rmtree(temp_repo_dir, onerror=remove_readonly)

    # Process Local SDKs
    for sdk in local_sdks:
        sdk_name = sdk["name"]
        clean_name = clean_sdk_name(sdk_name)
        target_dir = os.path.join(cache_base, clean_name)

        local_path = sdk.get("path")
        if local_path:
            src_dir = os.path.abspath(os.path.join(PROJECT_ROOT, local_path))
            if os.path.exists(src_dir):
                if not should_extract(sdk_name, src_dir, target_dir, state, decisions):
                    continue
                print(
                    f"[+] Copying local {sdk_name} from {local_path} to {target_dir}..."
                )
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir)
                shutil.copytree(src_dir, target_dir)
                strip_unused_role_folders(target_dir, sdk_name)
            else:
                print(
                    f"[-] Local path {local_path} for {sdk_name} does not exist. Skipping."
                )
                FAILED_SDKS.append(sdk_name)

    return decisions


def resolve_active_path(sdk_config):
    sdk_name = sdk_config["name"] if isinstance(sdk_config, dict) else sdk_config
    clean_name = clean_sdk_name(sdk_name)
    return os.path.abspath(os.path.join(PROJECT_ROOT, ".rokct", "cache", clean_name))


def run_installer(sdk_config):
    sdk_name = sdk_config["name"] if isinstance(sdk_config, dict) else sdk_config
    sdk_path = resolve_active_path(sdk_config)

    installer_script = os.path.join(sdk_path, "install.py")

    if not os.path.exists(installer_script):
        print(f"[-] No install.py found for SDK: {sdk_name} at {sdk_path}. Skipping.")
        FAILED_SDKS.append(sdk_name)
        return

    print(f"\n[*] Executing Installer for {sdk_name}...")
    try:
        result = subprocess.run(
            [sys.executable, installer_script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        print(f"[+] Installer for {sdk_name} completed successfully.")
    except subprocess.CalledProcessError as e:
        log_dir = os.path.join(PROJECT_ROOT, ".rokct", "agent", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"{sdk_name}_install_error.log")
        with open(log_file, "w", encoding="utf-8") as lf:
            lf.write(f"Command: {' '.join(e.cmd)}\n")
            lf.write(f"Exit Code: {e.returncode}\n")
            lf.write(f"Stdout:\n{e.stdout}\n")
            lf.write(f"Stderr:\n{e.stderr}\n")
        print(
            f"[!] Installer for {sdk_name} failed. Error log written to: .rokct/agent/logs/{sdk_name}_install_error.log"
        )
        sys.exit(1)


def update_pubspec_name(package_name):
    pubspec_path = os.path.join(PROJECT_ROOT, "pubspec.yaml")
    if not os.path.exists(pubspec_path):
        return

    try:
        with open(pubspec_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        updated = False
        with open(pubspec_path, "w", encoding="utf-8") as f:
            for line in lines:
                if line.startswith("name:"):
                    f.write(f"name: {package_name}\n")
                    updated = True
                else:
                    f.write(line)
        if updated:
            print(f"[*] Updated pubspec.yaml name to: {package_name}")
    except Exception as e:
        print(f"[!] Error updating pubspec.yaml name: {e}")


def update_pubspec_dependencies(sdks):
    pubspec_path = os.path.join(PROJECT_ROOT, "pubspec.yaml")
    if not os.path.exists(pubspec_path):
        return

    try:
        with open(pubspec_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        dependencies_start = -1
        for i, line in enumerate(lines):
            if line.strip() == "dependencies:":
                dependencies_start = i
                break

        if dependencies_start == -1:
            print("[!] Could not find 'dependencies:' section in pubspec.yaml")
            return

        new_lines = lines[: dependencies_start + 1]

        i = dependencies_start + 1
        while i < len(lines):
            line = lines[i]
            if line.startswith(" "):
                stripped = line.strip()
                if stripped and stripped.endswith("_sdk:"):
                    # Only skip this entry's OWN sub-lines (e.g. its "path:"
                    # line), not every indented line after it - a prior
                    # version kept skipping past subsequent _sdk: entries
                    # and the app's real dependencies (flutter:,
                    # cupertino_icons:, etc.) that follow them in the file,
                    # silently dropping them on every compose after the
                    # first _sdk: entry existed to trigger this branch.
                    entry_indent = len(line) - len(line.lstrip(" "))
                    i += 1
                    while i < len(lines):
                        next_line = lines[i]
                        if next_line.strip() == "":
                            i += 1
                            continue
                        next_indent = len(next_line) - len(next_line.lstrip(" "))
                        if next_indent > entry_indent:
                            i += 1
                            continue
                        break
                    continue
                else:
                    new_lines.append(line)
            elif line.strip() == "":
                new_lines.append(line)
            else:
                new_lines.extend(lines[i:])
                i = len(lines)
                break
            i += 1

        sdk_deps = []
        for sdk in sdks:
            sdk_name = sdk["name"] if isinstance(sdk, dict) else sdk
            resolved_path = resolve_active_path(sdk)

            pubspec_path_val = resolved_path
            try:
                pubspec_path_val = os.path.relpath(resolved_path, PROJECT_ROOT).replace(
                    "\\", "/"
                )
            except ValueError:
                pass

            if os.path.exists(os.path.join(resolved_path, "pubspec.yaml")):
                sdk_deps.append(f"  {sdk_name}:\n    path: {pubspec_path_val}\n")
            else:
                print(
                    f"  [-] Skipping {sdk_name} as pubspec.yaml is missing at {resolved_path}."
                )

        if sdk_deps:
            new_lines.insert(dependencies_start + 1, "".join(sdk_deps))

        with open(pubspec_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"[*] Updated SDK dependencies in pubspec.yaml")
    except Exception as e:
        print(f"[!] Error updating pubspec.yaml dependencies: {e}")


# Dependency overrides every composed app needs, regardless of which SDKs it
# installs. Asserted idempotently on every compose run (added if missing,
# left alone if already present) rather than relying on a one-off manual
# pubspec.yaml edit, which does not survive later reruns.
#
# sqlite3 >=3.x ships a package-root hook/build.dart (native asset build
# hook). Combined with Dart 3.10+'s native-assets support being on by
# default, build_runner's internal build-script precompile step hard-fails
# with "'dart compile' does not support build hooks, use 'dart build'
# instead." Pinning below the version that introduced the root-level hook
# avoids it; 2.9.4 only has a hook inside its example/ folder, which is not
# part of the real dependency graph.
REQUIRED_DEPENDENCY_OVERRIDES = {
    "sqlite3": "2.9.4",
}


# `flutter create` scaffolds a boilerplate counter-app smoke test at
# test/widget_test.dart referencing a `MyApp` widget that never exists in a
# composed app (the real entry widget comes from whichever SDK is home_sdk).
# Left in place, it fails `flutter analyze` with "The name 'MyApp' isn't a
# class" on every composed app. Only delete it if it still looks like the
# untouched scaffold — never clobber a real test someone wrote at that path.
STALE_WIDGET_TEST_SIGNATURE = "Counter increments smoke test"


def remove_stale_widget_test():
    test_path = os.path.join(PROJECT_ROOT, "test", "widget_test.dart")
    if not os.path.exists(test_path):
        return
    try:
        with open(test_path, "r", encoding="utf-8") as f:
            content = f.read()
        if STALE_WIDGET_TEST_SIGNATURE in content:
            os.remove(test_path)
            print(f"[*] Removed stale flutter-create scaffold test: {test_path}")
    except Exception as e:
        print(f"[!] Error checking/removing stale widget_test.dart: {e}")


def ensure_lib_gitignore():
    """Ensure the app ignores its generated lib/ - all of it, main.dart included.

    Owner decision (2026-08-02): "run compose fresh at build time, don't
    special-case main.dart as a tracked exception."

    Everything under lib/ is produced by compose, so none of it is tracked and
    a fresh checkout regenerates it. main.dart is NOT an exception: it is
    generated from base_sdk's template, and anything app-specific belongs in a
    manifest - `app_routes` for navigation, `host_routes` in composer.json for
    host-composed pages - all of which ARE tracked and are the real source of
    truth.

    An earlier version of this wrote `lib/*` plus `!lib/main.dart` to keep
    main.dart tracked. That was wrong, and the evidence is what treating
    main.dart as hand-authored actually cost: minilauncher, paas_manager and
    paas_pos each kept a main.dart with no @generated markers, so compose
    injected no SDK wiring and reported success while producing an app that
    registered nothing. Protecting one file does not stop hand-edits being lost
    in generated locations - it institutionalises the exception and hides the
    breakage.

    NOT retroactive by design. An app that already carries the `lib/*` +
    `!lib/main.dart` pair keeps it, because supacharge's main.dart still
    hand-authors an EmbeddedWidgets implementation (`introPage`) that has
    nowhere declarative to live yet. Rewriting its rule here would not delete
    that code, but it would stop tracking the only copy of it. Once
    EmbeddedWidgets has a declarative home and supacharge's is migrated, drop
    the pair from that app and this function will keep it plain thereafter.

    The written rule is anchored (`/lib/`, not `lib/`): an unanchored `lib/`
    matches EVERY lib directory in the repo, including each tracked
    `.rokct/cache/<sdk>/lib/` - which is exactly how hosts ended up committing
    caches with their lib/ stripped (see `.rokct/cache/.gitignore`'s `!**`
    note). Only the app's own root lib/ is generated by compose; the cache
    copies are sold content. A pre-existing anchored `/lib/` (or legacy
    unanchored `lib/`) already satisfies the requirement - nothing is
    re-appended.

    Also ensures `.rokct/__pycache__/` is ignored: compose.py writes
    sdk_installer_base.py into .rokct/ and every cached SDK's install.py
    imports it, so running compose leaves Python bytecode there that hosts
    were accidentally committing (supacharge tracked a .pyc). Checked
    independently of the lib/ rule so legacy lib/* apps still gain it.
    """
    path = os.path.join(PROJECT_ROOT, ".gitignore")
    try:
        lines = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                lines = f.read().split(NL)

        has_plain = any(l.strip() in ("lib/", "lib", "/lib/", "/lib") for l in lines)
        has_star = any(l.strip() == "lib/*" for l in lines)
        has_pycache = any(
            l.strip() in (".rokct/__pycache__/", ".rokct/__pycache__") for l in lines
        )

        # Leave a legacy lib/* + !lib/main.dart app alone - see docstring.
        needs_lib = not (has_star or has_plain)
        if not needs_lib and has_pycache:
            return

        while lines and lines[-1].strip() == "":
            lines.pop()
        if needs_lib:
            lines += [
                "",
                "# /lib/ is generated by compose on every build - main.dart included -",
                "# so none of it is tracked. Anything app-specific belongs in a manifest",
                "# (app_routes, or host_routes in composer.json), which IS tracked.",
                "# Anchored to the repo root on purpose: an unanchored lib/ would also",
                "# ignore every .rokct/cache/<sdk>/lib/, stripping the tracked caches.",
                "/lib/",
            ]
            print("[*] .gitignore: ensured /lib/ is ignored")
        if not has_pycache:
            lines += [
                "",
                "# Python bytecode from running the .rokct compose/install scripts.",
                ".rokct/__pycache__/",
            ]
            print("[*] .gitignore: ensured .rokct/__pycache__/ is ignored")
        lines.append("")

        with open(path, "w", encoding="utf-8", newline=NL) as f:
            f.write(NL.join(lines))
    except Exception as e:
        print("[!] Could not update .gitignore: %s" % e)


README_RECOMPOSE_START = "<!-- @generated-recompose-start -->"
README_RECOMPOSE_END = "<!-- @generated-recompose-end -->"


def ensure_host_readme():
    """Maintain a marker-delimited 'Recomposing this app' section in the host
    README.md, so anyone opening the repo learns that lib/ is disposable and
    how to regenerate it.

    Same idiom as sdk_installer_base.py's @generated-*-start/-end blocks, in
    Markdown-comment form: the composer owns everything between the markers
    and regenerates it on every run; prose outside the markers is the host's
    own and is never touched. Creates README.md if the host has none.
    Idempotent - when the block already matches, the file is not rewritten.
    """
    section = NL.join(
        [
            README_RECOMPOSE_START,
            "## Recomposing this app",
            "",
            "`lib/` is fully installer-generated and disposable - it is safe to delete",
            "and is gitignored. Anything app-specific lives in tracked manifests",
            "(`app_routes`, or `host_routes` in `composer.json`), never in `lib/` itself.",
            "",
            "To regenerate it:",
            "",
            "```sh",
            "python3 .rokct/initiate.py   # provisions the composer under .rokct/skills/",
            "python3 .rokct/skills/.rok/flutter/scripts/compose.py",
            "```",
            "",
            "Session cleanup (`python3 .rokct/end_protocol.py`) wipes the provisioned",
            "tools again.",
            README_RECOMPOSE_END,
        ]
    )
    path = os.path.join(PROJECT_ROOT, "README.md")
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = "# %s%s" % (os.path.basename(PROJECT_ROOT) or "App", NL)

        start = content.find(README_RECOMPOSE_START)
        end = content.find(README_RECOMPOSE_END)
        if start != -1 and end != -1 and end >= start:
            end += len(README_RECOMPOSE_END)
            updated = content[:start] + section + content[end:]
        else:
            updated = content.rstrip(NL) + NL + NL + section + NL

        if updated != content:
            with open(path, "w", encoding="utf-8", newline=NL) as f:
                f.write(updated)
            print("[*] README.md: refreshed 'Recomposing this app' section")
    except Exception as e:
        print("[!] Could not update README.md: %s" % e)


def ensure_pubspec_overrides():
    pubspec_path = os.path.join(PROJECT_ROOT, "pubspec.yaml")
    if not os.path.exists(pubspec_path):
        return

    try:
        with open(pubspec_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        overrides_start = -1
        for i, line in enumerate(lines):
            if line.strip() == "dependency_overrides:":
                overrides_start = i
                break

        existing_keys = set()
        if overrides_start != -1:
            i = overrides_start + 1
            while i < len(lines) and (
                lines[i].startswith(" ") or lines[i].strip() == ""
            ):
                stripped = lines[i].strip()
                if stripped and not stripped.startswith("#") and ":" in stripped:
                    existing_keys.add(stripped.split(":", 1)[0].strip())
                i += 1

        missing = {
            k: v
            for k, v in REQUIRED_DEPENDENCY_OVERRIDES.items()
            if k not in existing_keys
        }
        if not missing:
            return

        new_override_lines = [f"  {k}: {v}\n" for k, v in missing.items()]

        if overrides_start == -1:
            # No dependency_overrides section at all yet: append one.
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append("dependency_overrides:\n")
            lines.extend(new_override_lines)
        else:
            lines[overrides_start + 1 : overrides_start + 1] = new_override_lines

        with open(pubspec_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(
            f"[*] Ensured required dependency_overrides in pubspec.yaml: {list(missing.keys())}"
        )
    except Exception as e:
        print(f"[!] Error ensuring pubspec.yaml dependency_overrides: {e}")


def _build_runner_subprocess(args, cwd, label, **kwargs):
    """subprocess.run for a build_runner invocation: stdin closed (an inherited
    tty lets a prompting build block forever) and a hard timeout. On expiry
    subprocess.run kills the process before raising TimeoutExpired; fail the
    compose loudly instead of squatting the runner."""
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            shell=(os.name == "nt"),
            stdin=subprocess.DEVNULL,
            timeout=BUILD_RUNNER_TIMEOUT,
            **kwargs,
        )
    except subprocess.TimeoutExpired:
        print(
            f"[!] build_runner for {label} exceeded {BUILD_RUNNER_TIMEOUT}s and "
            f"was killed. If this build legitimately needs longer, raise "
            f"{BUILD_RUNNER_TIMEOUT_ENV}.",
            file=sys.stderr,
        )
        sys.exit(1)


def _run_build_runner(cwd, label):
    """build_runner in `cwd`, with the same --force-jit/fallback dance as the
    host run. Returns True on success."""
    build = _build_runner_subprocess(
        ["dart", "run", "build_runner", "build", "--force-jit"],
        cwd,
        label,
        capture_output=True,
        text=True,
    )
    if build.returncode != 0 and "Could not find an option named" in (
        build.stdout + build.stderr
    ):
        build = _build_runner_subprocess(
            ["dart", "run", "build_runner", "build", "--delete-conflicting-outputs"],
            cwd,
            label,
            capture_output=True,
            text=True,
        )
    if build.returncode == 0:
        print(f"[+] Regenerated code for {label}.")
        return True
    print(f"[!] Code generation failed for {label} (exit {build.returncode}).")
    print((build.stdout or "")[-2000:], end="")
    print((build.stderr or "")[-2000:], end="")
    return False


import re


def _fix_cache_dependency_override_paths(sdk_dir, pubspec):
    """Rewrite dependency_overrides path: entries that still point at an
    SDK's OWN repo location (e.g. `../../../core/base/dart`) so they match
    the already-correct `dependencies:` path for the same package once
    copied into `.rokct/cache/<sdk>` (e.g. `../base`).

    Source pubspec.yaml files declare both a `dependencies.<pkg>.path`
    (correct relative to the cache layout, where every SDK cache sits as a
    sibling under `.rokct/cache/`) and a `dependency_overrides.<pkg>.path`
    (correct only relative to the SDK's own standalone repo, for local dev
    codegen there). The installer copies the file verbatim, so the override
    silently breaks `pub get` inside the cache even though the matching
    dependency entry is fine — previously misread as "this SDK can't
    resolve standalone" and skipped rather than fixed.
    """
    try:
        with open(pubspec, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return
    if "dependency_overrides:" not in content:
        return
    deps_part, _, overrides_part = content.partition("dependency_overrides:")
    changed = False
    for pkg, dep_path in re.findall(
        r"^  (\w+):\n    path:\s*(\S+)\s*$", deps_part, re.MULTILINE
    ):
        new_overrides_part, n = re.subn(
            rf"(^  {pkg}:\n    path:\s*)\S+\s*$",
            rf"\g<1>{dep_path}",
            overrides_part,
            flags=re.MULTILINE,
        )
        if n and new_overrides_part != overrides_part:
            overrides_part = new_overrides_part
            changed = True
    if changed:
        try:
            with open(pubspec, "w", encoding="utf-8") as f:
                f.write(deps_part + "dependency_overrides:" + overrides_part)
            print(
                f"[*] Fixed dependency_overrides path(s) in {os.path.basename(sdk_dir)}/pubspec.yaml to match cache layout"
            )
        except Exception as e:
            print(f"[!] Could not fix dependency_overrides in {pubspec}: {e}")


def run_sdk_code_generation():
    """Regenerate codegen INSIDE each composed SDK cache that needs it.

    Table/TrKeys injection rewrites sources in `.rokct/cache/<sdk>` — most
    consequentially the drift `AppDatabase` in base_sdk, whose companion
    `.g.dart` then no longer matches (missing table getters, entity types
    that "aren't defined"). The host's own build_runner run does NOT fix
    this: build_runner only generates for the package it runs in, and each
    cache is a separate path-dependency package.

    Without this step a from-scratch compose (CI, or any clean checkout)
    produces a tree that cannot compile, and the only recovery is running
    build_runner by hand in each cache — which is exactly the kind of
    undocumented manual step composing is supposed to remove.

    Only caches that actually declare build_runner are touched, so SDKs with
    no generated code cost nothing.
    """
    cache_root = os.path.join(PROJECT_ROOT, ".rokct", "cache")
    if not os.path.isdir(cache_root):
        return
    print("\n[*] Regenerating code inside composed SDK caches...")
    for name in sorted(os.listdir(cache_root)):
        sdk_dir = os.path.join(cache_root, name)
        pubspec = os.path.join(sdk_dir, "pubspec.yaml")
        if not os.path.isfile(pubspec):
            continue
        try:
            with open(pubspec, "r", encoding="utf-8") as f:
                needs_codegen = "build_runner" in f.read()
        except Exception:
            continue
        if not needs_codegen:
            continue
        # Some caches carry a dependency_overrides path that's broken
        # relative to the cache layout (see _fix_cache_dependency_override_paths)
        # even though the matching dependencies path is fine; fix it before
        # attempting pub get so those SDKs resolve standalone instead of
        # being (wrongly) treated as unable to.
        _fix_cache_dependency_override_paths(sdk_dir, pubspec)
        try:
            pub = subprocess.run(
                ["flutter", "pub", "get"],
                cwd=sdk_dir,
                shell=(os.name == "nt"),
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            # No Flutter toolchain on PATH (e.g. a CI job that composes
            # before installing Flutter). Codegen is a post-install phase:
            # warn and skip it so composition itself still completes and
            # cache state still gets recorded; rerun the composer with
            # Flutter installed to regenerate cache sources.
            print("[!] `flutter` not found on PATH; skipping SDK cache codegen.")
            return
        if pub.returncode != 0:
            print(
                f"[*] {name}_sdk does not resolve standalone; skipping "
                f"its codegen (it ships generated sources)."
            )
            continue
        _run_build_runner(sdk_dir, f"{name}_sdk")


def run_code_generation():
    """Runs `flutter pub get` then `build_runner build`.

    --force-jit avoids a real failure mode: AOT builder compilation invokes
    `dart compile`, which refuses to run when any resolved package (e.g.
    objective_c, pulled in transitively by path_provider_foundation) ships a
    native-asset build hook, failing with "'dart compile' does not support
    build hooks, use 'dart build' instead." JIT mode uses `dart run` instead,
    which has no such restriction. This is slower than AOT but is the only
    mode that works while any dependency in the graph has a hook/build.dart.

    --force-jit is not universally available, though: it's a newer
    build_runner flag, and some dependency graphs resolve an older
    build_runner (observed: 2.5.4) that doesn't recognize it at all
    ("Could not find an option named --force-jit") and exits non-zero before
    running anything. So: try --force-jit first; if it fails specifically
    because the flag itself is unrecognized, retry with
    --delete-conflicting-outputs instead (supported by older versions,
    fine as long as no native-asset-hook package is actually in the graph
    for that project — e.g. sqlite3 pinned below the version that added its
    package-root hook, as this project already does).

    Generation failures are reported but do not abort the script — SDK
    installation already completed successfully at this point, and a
    codegen problem is a separate, visible-in-output concern the caller
    should look at, not a reason to make the whole compose run look failed.
    """
    print("\n[*] Running flutter pub get...")
    try:
        pub_get = subprocess.run(
            ["flutter", "pub", "get"], cwd=PROJECT_ROOT, shell=(os.name == "nt")
        )
    except FileNotFoundError:
        # Same warn-skip as run_sdk_code_generation: without Flutter on
        # PATH the crash would otherwise just move here and still sink an
        # otherwise-complete composition.
        print("[!] `flutter` not found on PATH; skipping host code generation.")
        return
    if pub_get.returncode != 0:
        print("[!] flutter pub get failed; skipping code generation.")
        return

    print(
        "[*] Running build_runner (--force-jit, required for packages with native-asset build hooks)..."
    )
    build = _build_runner_subprocess(
        ["dart", "run", "build_runner", "build", "--force-jit"],
        PROJECT_ROOT,
        "host",
        capture_output=True,
        text=True,
    )
    if build.returncode != 0 and "Could not find an option named" in (
        build.stdout + build.stderr
    ):
        print(
            "[*] This build_runner version doesn't support --force-jit; retrying with --delete-conflicting-outputs..."
        )
        build = _build_runner_subprocess(
            ["dart", "run", "build_runner", "build", "--delete-conflicting-outputs"],
            PROJECT_ROOT,
            "host",
        )
    else:
        # Either it succeeded or failed for a real reason - show the output either way.
        print(build.stdout, end="")
        print(build.stderr, end="")

    if build.returncode == 0:
        print("[+] Code generation completed successfully.")
    else:
        print(
            f"[!] Code generation failed (exit {build.returncode}). Check output above for the specific error."
        )


def main():
    composer_path = os.path.join(PROJECT_ROOT, "composer.json")
    package_name = None
    sdks_to_install = []

    if os.path.exists(composer_path):
        try:
            with open(composer_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            sdks_to_install = [
                s
                for s in config.get("sdks", [])
                if isinstance(s, dict) and s.get("enabled", True)
            ]
            package_name = config.get("package_name")
            print(f"[*] Reading active SDK list from composer.json: {sdks_to_install}")
        except Exception as e:
            print(f"[!] Error reading composer.json: {e}.")
            sys.exit(1)

    # The FULL enabled set from composer.json — pubspec.yaml must always
    # reflect every enabled SDK, never just whichever subset this run is
    # scoped to refresh. A scoped run (e.g. `compose.py auth_sdk`) used to
    # filter sdks_to_install BEFORE it reached update_pubspec_dependencies(),
    # silently dropping every other SDK's pubspec entry and breaking the
    # whole app until a full unscoped recompose restored it.
    all_enabled_sdks = list(sdks_to_install)

    if len(sys.argv) < 2:
        if not sdks_to_install:
            print("[-] No SDKs found to install.")
            sys.exit(1)
    else:
        requested_names = sys.argv[1:]
        sdks_to_install = [s for s in sdks_to_install if s["name"] in requested_names]

    if "core_sdk" in [s["name"] if isinstance(s, dict) else s for s in sdks_to_install]:
        core_idx = -1
        for i, s in enumerate(sdks_to_install):
            if (isinstance(s, dict) and s["name"] == "core_sdk") or s == "core_sdk":
                core_idx = i
                break
        if core_idx != -1:
            core_sdk = sdks_to_install.pop(core_idx)
            sdks_to_install.insert(0, core_sdk)

    # Cache all SDKs in one consolidated fetch pass (version-aware: an SDK
    # whose cached copy is current is left in place, see should_extract).
    cache_decisions = resolve_and_cache_sdks(sdks_to_install)

    # Run the installers. An SDK entry can set "skip_install": true in
    # composer.json to stay fully composed - cached (with role-stripping),
    # listed as a pubspec path dependency, and covered by per-SDK codegen -
    # while its install.py never runs, so none of its manifest installs/
    # routes enter the host app. For apps that consume an SDK's library
    # code but deliberately keep that SDK's pages/routes host-owned
    # (e.g. the host's own page already generates the same route name).
    for sdk in sdks_to_install:
        if isinstance(sdk, dict) and sdk.get("skip_install"):
            print(
                f"\n[*] Skipping installer for {sdk['name']} (skip_install in composer.json); its cache, pubspec dependency and codegen still apply."
            )
            continue
        run_installer(sdk)

    if package_name:
        update_pubspec_name(package_name)

    if all_enabled_sdks:
        update_pubspec_dependencies(all_enabled_sdks)

    ensure_pubspec_overrides()
    ensure_lib_gitignore()
    ensure_host_readme()
    ensure_docs()
    remove_stale_widget_test()
    # Record versions/hashes in a finally block: codegen mutates the caches
    # (generated sources, override-path fixes), so the recorded hash must be
    # taken after it - but recording must still happen in environments where
    # the Flutter toolchain is absent and codegen dies early.
    try:
        run_sdk_code_generation()
        run_code_generation()
    finally:
        record_sdk_cache_state(cache_decisions)

    if FAILED_SDKS:
        failed = ", ".join(sorted(set(FAILED_SDKS)))
        print(
            f"\n[!] Compose FAILED: the following SDK(s) were not installed: {failed}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
