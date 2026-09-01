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

import os
import json
import shutil
import hashlib
import re
import subprocess
import sys

# Strict compose mode: every compose_warning() below (a wiring step that could
# not fully apply — missing target file, absent @marker, malformed manifest
# entry, unreadable state) escalates from a printed warning to a hard
# RuntimeError, so CI can refuse a compose whose wiring is silently missing.
# Same env-flag convention as sdk_composer.py's ROKCT_ALLOW_UNPINNED_SDKS.
# Default (unset) keeps the historical warn-and-continue behavior so
# currently-green composes stay green.
COMPOSE_STRICT_ENV = "ROKCT_COMPOSE_STRICT"


def _compose_strict():
    return os.environ.get(COMPOSE_STRICT_ENV, "").lower() in ("1", "true", "yes")


def compose_warning(message):
    """Loudly surface a compose/wiring step that did not fully apply.

    Prints to BOTH stdout (the installer's existing logging stream, so the
    warning lands in the same transcript as every other "[*]"/"[!]" line) and
    stderr (so wrappers that only surface stderr still show it). With
    ROKCT_COMPOSE_STRICT=1/true/yes the warning is escalated to a hard error
    instead, failing the compose with a non-zero exit.
    """
    line = f"  [!] WARNING: {message}"
    print(line)
    if sys.stderr is not sys.stdout:
        print(line, file=sys.stderr)
    if _compose_strict():
        raise RuntimeError(
            f"{COMPOSE_STRICT_ENV} is set: escalating compose warning to error: {message}"
        )


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# install_state.json lives inside .rokct/cache/ (an end_protocol.py
# keep-whitelisted directory) so recorded install/cache hashes survive
# session cleanup and travel with the cached content they describe. The
# legacy root location (.rokct/install_state.json) is migrated on first read.
STATE_FILE = os.path.join(PROJECT_ROOT, ".rokct", "cache", "install_state.json")
LEGACY_STATE_FILE = os.path.join(PROJECT_ROOT, ".rokct", "install_state.json")


def migrate_legacy_state():
    if os.path.exists(LEGACY_STATE_FILE) and not os.path.exists(STATE_FILE):
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            shutil.move(LEGACY_STATE_FILE, STATE_FILE)
            print(
                "[*] Migrated .rokct/install_state.json -> .rokct/cache/install_state.json"
            )
        except Exception as e:
            print(f"[!] Could not migrate legacy install_state.json: {e}")


ROUTER_FILE = os.path.join(
    PROJECT_ROOT, "lib", "presentation", "routes", "app_router.dart"
)
MAIN_FILE = os.path.join(PROJECT_ROOT, "lib", "main.dart")
DB_FILE = os.path.join(
    PROJECT_ROOT,
    ".rokct",
    "cache",
    "base",
    "lib",
    "src",
    "database",
    "app_database.dart",
)
TRKEYS_FILE = os.path.join(
    PROJECT_ROOT, ".rokct", "cache", "base", "lib", "src", "services", "tr_keys.dart"
)
ASSETKEYS_FILE = os.path.join(
    PROJECT_ROOT, ".rokct", "cache", "base", "lib", "src", "services", "app_assets.dart"
)
CONSTANTS_FILE = os.path.join(
    PROJECT_ROOT,
    ".rokct",
    "cache",
    "base",
    "lib",
    "src",
    "constants",
    "app_constants.dart",
)
INJECTED_DB_DIR = os.path.join(
    PROJECT_ROOT, ".rokct", "cache", "base", "lib", "src", "database", "injected"
)
ONBOARDING_ROUTES_FILE = os.path.join(
    PROJECT_ROOT, "lib", "presentation", "routes", "onboarding_route_pages.dart"
)
REGISTRATION_STEPS_FILE = os.path.join(
    PROJECT_ROOT, "lib", "presentation", "routes", "registration_step_pages.dart"
)
SESSION_POLICY_FILE = os.path.join(
    PROJECT_ROOT, "lib", "presentation", "routes", "auth_session_policy.dart"
)

# File extensions treated as text during template installs: the installer
# reads these, substitutes the literal `${package}` token with the host's
# composer.json package_name, and writes the result (everything else is
# byte-copied). `.rc`/`.cpp`/`.h` are included so native desktop runner
# scaffolding (windows/runner/Runner.rc, main.cpp) can carry the app name as
# `${package}` in shared templates instead of per-app pre-named copies. The
# substitution is an exact-token literal replace — CMake-style `${VAR}`
# expansions in template sources (e.g. `${BINARY_NAME}`, `${plugin}`) are
# untouched, and an org-wide scan of every SDK's templates found no
# .rc/.cpp/.h file containing any other `${...}` sequence.
TEXT_SUBSTITUTION_EXTENSIONS = (
    ".dart",
    ".yaml",
    ".json",
    ".txt",
    ".md",
    ".gradle",
    ".properties",
    ".rc",
    ".cpp",
    ".h",
)


def file_hash(path):
    if not os.path.exists(path):
        return None
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def resolve_app_type():
    """Reads this host app's own flavor marker (e.g. 'customer', 'driver',
    'manager', 'pos') from .rokct/config/app_type - a plain one-line text
    file checked into each host app's own repo (distinct from
    production.env, which is shared across all flavors and lists every
    flavor's package name at once, so it can't self-identify which one a
    given repo is). Lives under .rokct/config/ specifically because
    end_protocol.py's cleanup deletes anything loose at .rokct/'s own root
    that isn't a recognized canonical template - config/ is one of its
    explicitly protected directory names.
    Returns None if the file doesn't exist - manifests with no matching
    app_type block behave exactly as before (nothing filtered)."""
    path = os.path.join(PROJECT_ROOT, ".rokct", "config", "app_type")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            value = f.read().strip().lower()
            return value or None
    return None


def resolve_home_sdk():
    sdk_root = os.path.join(PROJECT_ROOT, "sdk")
    if os.path.isdir(sdk_root):
        for sdk_name in os.listdir(sdk_root):
            manifest_path = os.path.join(sdk_root, sdk_name, "manifest.json")
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8-sig") as f:
                        manifest = json.load(f)
                        if manifest.get("home_sdk") is True:
                            return sdk_name
                except Exception as e:
                    compose_warning(
                        f"unreadable manifest {manifest_path} for SDK {sdk_name} "
                        f"({e}); it cannot be considered as the home SDK"
                    )
    return "core_sdk"


# Set when this run scaffolded the app itself via `flutter create`. Those files
# are OURS, not the host's, even though the installer has no recorded hash for
# them - see the guard in install_sdk_files_and_routes.
FRESH_SCAFFOLD = False


def initialize_flutter_project():
    # If pubspec.yaml exists, we assume the project is already initialized
    pubspec_path = os.path.join(PROJECT_ROOT, "pubspec.yaml")
    if os.path.exists(pubspec_path):
        return

    package_name = get_project_package_name()
    print(f"[*] Project not initialized. Running 'flutter create' as {package_name}...")
    # Validate the package name before it is interpolated into a shell string.
    # Dart package names are lowercase snake_case identifiers, so a strict
    # identifier regex both matches every legitimate name and neutralizes shell
    # metacharacters (the command is run with shell=True below so `flutter` on
    # Windows resolves the flutter.bat shim).
    if not re.match(r"^[a-z][a-z0-9_]*$", package_name):
        print(
            f"[-] Critical Error: invalid package name '{package_name}'. "
            f"Expected a lowercase snake_case Dart package name; refusing to run 'flutter create'."
        )
        return
    try:
        # Run flutter create in the current directory. Pass the command as a
        # STRING with shell=True, not a list: a list argv with shell=True
        # silently drops every argument on POSIX (subprocess runs
        # `sh -c "flutter"`, so `create --project-name ... .` is lost),
        # scaffolding nothing while reporting success. A string command runs
        # correctly on POSIX and Windows alike.
        # --project-name ensures the internal package name is correct
        subprocess.run(
            f"flutter create --project-name {package_name} .", check=True, shell=True
        )
        global FRESH_SCAFFOLD
        FRESH_SCAFFOLD = True
    except subprocess.CalledProcessError as e:
        print(f"[-] Critical Error: 'flutter create' failed: {e}")
    except FileNotFoundError:
        print(
            "[-] Critical Error: 'flutter' command not found. Please ensure Flutter is installed and in your PATH."
        )


def bootstrap_home_sdk_if_missing(state):
    # We bootstrap if the project was just created (default files) or is completely empty
    # We check for a specific marker or just always run it if we are in bootstrap mode.
    # To avoid infinite loops, we'll check if we've already bootstrapped this version.

    home_sdk_name = resolve_home_sdk()
    home_sdk_path = os.path.join(PROJECT_ROOT, "sdk", home_sdk_name)
    manifest_path = os.path.join(home_sdk_path, "manifest.json")

    if not os.path.exists(manifest_path):
        return

    # We use a flag or check if the default flutter create main.dart is still there
    # For simplicity, we'll run bootstrap if we are missing our specialized files.
    # A better way is to check if we've recorded a successful bootstrap in state.
    if state.get("bootstrapped_home_sdk") == home_sdk_name:
        return

    print(f"[*] Bootstrapping baseline files from {home_sdk_name} templates...")
    with open(manifest_path, "r", encoding="utf-8-sig") as f:
        manifest = json.load(f)
    for entry in manifest.get("installs", []):
        from_rel = entry.get("from")
        to_rel = entry.get("to")
        if not from_rel or not to_rel:
            compose_warning(
                f"compose skipped: malformed installs entry in {home_sdk_name}'s "
                f"manifest (from={from_rel!r}, to={to_rel!r}); bootstrap file NOT installed"
            )
            continue
        src_path = os.path.join(home_sdk_path, from_rel)
        dest_path = os.path.join(PROJECT_ROOT, to_rel)
        if not os.path.exists(src_path):
            compose_warning(
                f"compose skipped: bootstrap template source {from_rel} missing "
                f"for SDK {home_sdk_name}; {to_rel} NOT installed"
            )
            continue
        if os.path.exists(src_path):
            if os.path.isdir(src_path):
                if os.path.exists(dest_path):
                    shutil.rmtree(dest_path)
                shutil.copytree(src_path, dest_path)
            else:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                if src_path.endswith(TEXT_SUBSTITUTION_EXTENSIONS):
                    with open(src_path, "r", encoding="utf-8", errors="ignore") as fs:
                        content = fs.read()
                    content = content.replace("${package}", get_project_package_name())
                    with open(dest_path, "w", encoding="utf-8") as fd:
                        fd.write(content)
                else:
                    shutil.copy2(src_path, dest_path)

    # Mark as bootstrapped
    state["bootstrapped_home_sdk"] = home_sdk_name
    save_state(state)


def load_state():
    # 1. Initialize basic flutter structure if missing
    initialize_flutter_project()

    # 2. Overlay Home SDK templates
    migrate_legacy_state()
    state = {"packages": {}}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception as e:
            compose_warning(
                f"unreadable install state {STATE_FILE} ({e}); compose is "
                f"proceeding from an EMPTY state - previously recorded SDK "
                f"wiring and file hashes are being ignored"
            )

    bootstrap_home_sdk_if_missing(state)

    return state


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def get_host_routes():
    """Host-composition routes (ADR-005): pages that live in the host's own
    composition files (lib/presentation/routes/*_route_pages.dart)
    rather than inside any SDK's lib/ — typically because they import
    another SDK directly (cross-SDK composition), which ADR-005 forbids
    inside a single SDK's own lib/. No SDK manifest can declare these, and
    update_router_table() owns the whole @generated-routes block, so any
    host route not declared somewhere is silently dropped on every recompose
    (this repeatedly broke apps whose onboarding entry is host-composed —
    the app hangs on splash with no route for AppRoutes.replaceLoginRoute to
    reach).

    Declared as DATA in the consuming app's own composer.json
    ("host_routes"), not hardcoded in this shared script — this file is
    canonical/fetched by every app; only each app's own composer.json
    should differ. An app with no host-composed routes just omits the key.
    """
    composer_json_path = os.path.join(PROJECT_ROOT, "composer.json")
    if not os.path.exists(composer_json_path):
        return []
    try:
        with open(composer_json_path, "r", encoding="utf-8-sig") as f:
            config = json.load(f)
        return config.get("host_routes", [])
    except Exception as e:
        compose_warning(
            f"unreadable composer.json {composer_json_path} ({e}); "
            f"host_routes NOT applied"
        )
        return []


def get_project_package_name():
    # 1. Try to get package name from the root composer.json
    composer_json_path = os.path.join(PROJECT_ROOT, "composer.json")
    if os.path.exists(composer_json_path):
        try:
            with open(composer_json_path, "r", encoding="utf-8-sig") as f:
                composer_data = json.load(f)
            if "package_name" in composer_data:
                return composer_data["package_name"]
        except Exception as e:
            print(
                f"  [!] unreadable composer.json {composer_json_path} ({e}); "
                f"falling back to pubspec.yaml for the package name"
            )

    # 2. Fallback to pubspec.yaml
    pubspec_path = os.path.join(PROJECT_ROOT, "pubspec.yaml")
    if os.path.exists(pubspec_path):
        try:
            with open(pubspec_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("name:"):
                        return line.split(":", 1)[1].strip()
        except Exception as e:
            print(
                f"  [!] unreadable pubspec.yaml {pubspec_path} ({e}); "
                f"falling back to the default package name"
            )
    return "rokctapp"


def resolve_sdk_path(sdk_name):
    # 1. Try resolving via .dart_tool/package_config.json (for pub-fetched SDKs)
    package_config_path = os.path.join(
        PROJECT_ROOT, ".dart_tool", "package_config.json"
    )
    if os.path.exists(package_config_path):
        try:
            with open(package_config_path, "r", encoding="utf-8-sig") as f:
                config = json.load(f)
            # In package_config.json v2, "packages" is a list of packages
            packages = config.get("packages", [])
            for pkg in packages:
                if pkg.get("name") == sdk_name:
                    root_uri = pkg.get("rootUri")
                    if root_uri:
                        if root_uri.startswith("file:///"):
                            return root_uri.replace("file:///", "").replace("/", os.sep)
                        elif root_uri.startswith(".."):
                            return os.path.abspath(
                                os.path.join(PROJECT_ROOT, ".dart_tool", root_uri)
                            )
                        return root_uri
        except Exception as e:
            print(f"  [!] Error reading package_config.json: {e}")

    # 2. Fallback to local sdk/ directory (for monorepo development)
    local_path = os.path.join(PROJECT_ROOT, "sdk", sdk_name)
    if os.path.exists(local_path):
        return local_path

    # 3. Fallback to .rokct/cache/<clean_name> (populated by sdk_composer.py's
    # git-based compose flow). sdk_composer.py strips a trailing "_sdk"/"_sdks"
    # suffix when naming the cache folder (see clean_sdk_name there), so mirror
    # that here rather than looking up the raw sdk_name.
    clean_name = sdk_name
    if clean_name.endswith("_sdks"):
        clean_name = clean_name[:-5]
    elif clean_name.endswith("_sdk"):
        clean_name = clean_name[:-4]
    cache_path = os.path.join(PROJECT_ROOT, ".rokct", "cache", clean_name)
    if os.path.exists(cache_path):
        return cache_path

    return None


def install_sdk_files_and_routes(sdk_name):
    sdk_path = resolve_sdk_path(sdk_name)
    if not sdk_path:
        compose_warning(
            f"compose skipped: could not resolve path for SDK {sdk_name}; "
            f"NOTHING from this SDK was installed"
        )
        return False

    manifest_path = os.path.join(sdk_path, "manifest.json")

    if not os.path.exists(manifest_path):
        compose_warning(
            f"compose skipped: manifest.json missing at {manifest_path} for SDK "
            f"{sdk_name}; NOTHING from this SDK was installed"
        )
        return False

    with open(manifest_path, "r", encoding="utf-8-sig") as f:
        manifest = json.load(f)

    # Everything at the manifest's top level always installs regardless of
    # flavor ("common get installed regardless"). A manifest can additionally
    # declare an "app_type" block keyed by flavor name (customer/driver/
    # manager/pos/...) whose own installs/routes/app_routes/database/
    # tr_keys/constants get merged in ONLY when they match this host app's
    # own .rokct/app_type marker - same file-selection idea as the
    # tenant/control split on the Frappe composer side, applied here via
    # manifest content instead of separate on-disk folders.
    current_app_type = resolve_app_type()
    flavor_block = (
        (manifest.get("app_type") or {}).get(current_app_type, {})
        if current_app_type
        else {}
    )

    version = manifest.get("version", "1.0.0")
    installs = manifest.get("installs", []) + flavor_block.get("installs", [])
    routes = manifest.get("routes", []) + flavor_block.get("routes", [])
    app_routes = manifest.get("app_routes", []) + flavor_block.get("app_routes", [])
    onboarding_slides = manifest.get("onboarding_slides", []) + flavor_block.get(
        "onboarding_slides", []
    )
    registration_steps = manifest.get("registration_steps", []) + flavor_block.get(
        "registration_steps", []
    )
    embedded_widgets = manifest.get("embedded_widgets", []) + flavor_block.get(
        "embedded_widgets", []
    )
    di_hooks = manifest.get("di_hooks", []) + flavor_block.get("di_hooks", [])
    boot_hooks = manifest.get("boot_hooks", []) + flavor_block.get("boot_hooks", [])

    state = load_state()
    package_state = state["packages"].get(
        sdk_name, {"version": "0.0.0", "files": {}, "routes": []}
    )
    package_state["version"] = version
    package_state["routes"] = routes
    package_state["app_routes"] = app_routes
    package_state["onboarding_slides"] = onboarding_slides
    package_state["registration_steps"] = registration_steps
    package_state["embedded_widgets"] = embedded_widgets
    package_state["di_hooks"] = di_hooks
    package_state["boot_hooks"] = boot_hooks

    # Extract and store this SDK's brand hook: the one pre-frame call that
    # injects the app's brand palette into the shared AppStyle tokens (the
    # kernel ships neutral defaults only). At most ONE installed SDK may
    # declare it - normally the home SDK - and update_brand_hook() hard-errors
    # if two do. The flavor block wins over the manifest top level, matching
    # database's migration precedence.
    brand_hook = flavor_block.get("brand_hook") or manifest.get("brand_hook")
    if brand_hook:
        package_state["brand_hook"] = brand_hook
    else:
        package_state.pop("brand_hook", None)

    # Extract and store this SDK's session policy: which account roles this
    # composed app admits at login and where each lands (auth_sdk's
    # AuthSessionPolicy seam). At most ONE installed SDK may declare it -
    # normally the home SDK, typically inside its app_type flavor block so
    # e.g. merchants_sdk scopes the seller gate to manager builds - and
    # update_session_policy() hard-errors if two do, exactly like
    # brand_hook. The flavor block wins over the manifest top level.
    session_policy = flavor_block.get("session_policy") or manifest.get(
        "session_policy"
    )
    if session_policy:
        package_state["session_policy"] = session_policy
    else:
        package_state.pop("session_policy", None)

    print(f"\n[*] Installing SDK: {sdk_name} (v{version})")

    # 1. Sync Files
    for entry in installs:
        from_rel = entry.get("from")
        to_rel = entry.get("to")
        if not from_rel or not to_rel:
            compose_warning(
                f"compose skipped: malformed installs entry in SDK {sdk_name}'s "
                f"manifest (from={from_rel!r}, to={to_rel!r}); file NOT installed"
            )
            continue

        src_path = os.path.join(sdk_path, from_rel)
        dest_path = os.path.join(PROJECT_ROOT, to_rel)

        if not os.path.exists(src_path):
            compose_warning(
                f"compose skipped: template source {from_rel} missing for SDK "
                f"{sdk_name}; {to_rel} NOT installed"
            )
            continue

        files_to_sync = []
        if os.path.isdir(src_path):
            for root, _, filenames in os.walk(src_path):
                for filename in filenames:
                    abs_src = os.path.join(root, filename)
                    rel_to_src = os.path.relpath(abs_src, src_path)
                    abs_dest = os.path.join(dest_path, rel_to_src)
                    rel_dest = os.path.relpath(abs_dest, PROJECT_ROOT).replace(
                        "\\", "/"
                    )
                    files_to_sync.append((abs_src, abs_dest, rel_dest))
        else:
            rel_dest = to_rel.replace("\\", "/")
            files_to_sync.append((src_path, dest_path, rel_dest))

        for file_src, file_dest, rel_dest in files_to_sync:
            upstream_hash = file_hash(file_src)

            # Check if file already exists in host and check for modifications
            if os.path.exists(file_dest):
                current_dest_hash = file_hash(file_dest)
                last_known_hash = package_state.get("files", {}).get(rel_dest)
                if last_known_hash is None and not FRESH_SCAFFOLD:
                    # The file is already here but this installer has never
                    # written it, so it is the host app's own - not a stale
                    # copy of ours. Overwriting it destroys work nobody asked
                    # us to touch, and on a first-ever compose that is exactly
                    # what used to happen: paas_driver's pubspec.yaml was
                    # replaced wholesale by base_sdk's template, silently
                    # dropping six dependencies its code still used
                    # (charts_flutter, map_launcher, auto_size_text,
                    # calendar_date_picker2, workmanager, percent_indicator).
                    # The old guard could not catch it because it required a
                    # previously-stored hash, which by definition no first
                    # compose has.
                    #
                    # FRESH_SCAFFOLD is the exception, and it matters: when
                    # this same run created the app with `flutter create`
                    # (initialize_flutter_project, called ~110 lines before the
                    # installs), every file it emitted - main.dart,
                    # pubspec.yaml, android/ - also has no recorded hash. Those
                    # are our own scaffolding, not host work, so protecting
                    # them meant a brand-new app kept Flutter's counter-app
                    # main.dart: no @generated markers, no SDK DI injected, and
                    # a compose that reports success while wiring up nothing.
                    # A host file still has no hash AND no fresh scaffold, so
                    # the paas_driver protection is untouched.
                    print(
                        f"  [!] WARNING: {rel_dest} already exists and was not installed by this SDK. Skipping to avoid overwriting the app's own file - merge manually if you want the template's version."
                    )
                    continue
                if current_dest_hash != last_known_hash:
                    # User modified the template file, skip and warn
                    print(
                        f"  [!] WARNING: {rel_dest} has been modified by a developer. Skipping overwrite to prevent data loss. Please merge changes manually."
                    )
                    continue

            os.makedirs(os.path.dirname(file_dest), exist_ok=True)

            # Copy binary files directly, text files with banner prepended
            is_text = file_dest.endswith(TEXT_SUBSTITUTION_EXTENSIONS)

            if is_text:
                with open(file_src, "r", encoding="utf-8", errors="ignore") as fs:
                    content = fs.read()
                    content = content.replace("${package}", get_project_package_name())

                # Prepend developer warning banner for dart files above first import/export/part
                if file_dest.endswith(".dart"):
                    banner = f"""// ==========================================
// [GENERATED TEMPLATE FILE]
// This file was installed from: {sdk_name}
// Feel free to modify and customize this code.
// Note: If you edit this file, the SDK installer will detect your changes
// and automatically skip overwriting it during future upgrades.
// ==========================================

"""
                    lines = content.splitlines(keepends=True)
                    insert_idx = 0
                    for idx, line in enumerate(lines):
                        trimmed = line.strip()
                        if (
                            trimmed.startswith("import ")
                            or trimmed.startswith("export ")
                            or trimmed.startswith("part ")
                            or trimmed.startswith("part '")
                            or trimmed.startswith('part "')
                        ):
                            insert_idx = idx
                            break
                    lines.insert(insert_idx, banner)
                    content = "".join(lines)

                with open(file_dest, "w", encoding="utf-8") as fd:
                    fd.write(content)
            else:
                shutil.copy2(file_src, file_dest)

            # Store the resulting file's hash in state
            package_state["files"][rel_dest] = file_hash(file_dest)
            print(f"  [+] COPY: {rel_dest}")

    # Extract and store database definitions if present (tables from both
    # common and the matching flavor block; flavor's migration step wins if
    # both declare one, since a manifest normally only needs one)
    db_config = manifest.get("database")
    flavor_db = flavor_block.get("database")
    if db_config or flavor_db:
        merged_db = dict(db_config or {})
        if flavor_db:
            merged_db["tables"] = (db_config or {}).get("tables", []) + flavor_db.get(
                "tables", []
            )
            if flavor_db.get("migration"):
                merged_db["migration"] = flavor_db["migration"]
        package_state["database"] = merged_db

    # Extract and store tr_keys (translation keys owned by this SDK alone -
    # keys used by 2+ SDKs belong hand-written in base_sdk's TrKeys instead)
    tr_keys_config = dict(manifest.get("tr_keys") or {})
    tr_keys_config.update(flavor_block.get("tr_keys") or {})
    if tr_keys_config:
        package_state["tr_keys"] = tr_keys_config

    # Extract and store asset_keys (AppAssets constants owned by this SDK
    # alone - constants used by 2+ SDKs belong hand-written in base_sdk's
    # AppAssets instead). Injected into app_assets.dart like tr_keys.
    asset_keys_config = dict(manifest.get("asset_keys") or {})
    asset_keys_config.update(flavor_block.get("asset_keys") or {})
    if asset_keys_config:
        package_state["asset_keys"] = asset_keys_config
    else:
        package_state.pop("asset_keys", None)

    # Extract and store app_assets: asset DIRECTORY entries this SDK needs
    # declared in the HOST app's pubspec (the files themselves arrive via
    # ordinary manifest `installs` entries, e.g. templates/assets/team ->
    # assets/team). Same ownership model as tr_keys: the SDK declares, the
    # installer injects into a marker-owned block, a removed SDK's entries
    # disappear on the next regeneration.
    app_assets_config = list(manifest.get("app_assets") or [])
    app_assets_config += list(flavor_block.get("app_assets") or [])
    if app_assets_config:
        package_state["app_assets"] = app_assets_config
    else:
        package_state.pop("app_assets", None)

    # Extract and store platform permission needs: Android <uses-permission>
    # names plus iOS Info.plist usage-string keys that this SDK's plugins
    # require in the HOST app's own platform config (e.g. delivery_sdk's
    # driver flavor needs ACCESS_BACKGROUND_LOCATION for its WorkManager
    # courier tracking; comms_sdk needs POST_NOTIFICATIONS for push). Same
    # ownership model as tr_keys: the SDK declares, the installer injects
    # into marker-owned blocks (see update_platform_permissions), a removed
    # SDK's entries disappear on the next regeneration, and anything the host
    # already declares outside the block is never duplicated (host wins).
    pp_config = dict(manifest.get("platform_permissions") or {})
    flavor_pp = flavor_block.get("platform_permissions") or {}
    android_perms = list(pp_config.get("android") or []) + list(
        flavor_pp.get("android") or []
    )
    ios_usage_keys = dict(pp_config.get("ios") or {})
    ios_usage_keys.update(flavor_pp.get("ios") or {})
    if android_perms or ios_usage_keys:
        package_state["platform_permissions"] = {
            "android": android_perms,
            "ios": ios_usage_keys,
        }
    else:
        package_state.pop("platform_permissions", None)

    # Extract and store AppConstants field overrides (home_sdk only, normally)
    constants_config = manifest.get("constants")
    flavor_constants = flavor_block.get("constants")
    if constants_config or flavor_constants:
        merged_constants = dict(constants_config or {})
        if flavor_constants:
            merged_constants["import"] = flavor_constants.get(
                "import", merged_constants.get("import")
            )
            merged_constants["overrides"] = dict(
                (constants_config or {}).get("overrides", {})
            )
            merged_constants["overrides"].update(flavor_constants.get("overrides", {}))
        package_state["constants"] = merged_constants

    # Extract and store layout integrations if present
    integrations_config = manifest.get("integrations", []) + flavor_block.get(
        "integrations", []
    )
    if integrations_config:
        package_state["integrations"] = integrations_config

    state["packages"][sdk_name] = package_state
    save_state(state)

    # 2. Update Routing, Main DI & Database Registrations
    update_router_table()
    update_main_dependencies()
    update_database_registration()
    update_tr_keys_registration()
    update_constants_overrides()
    update_asset_keys_registration()
    update_app_assets_registration()
    update_platform_permissions()
    update_layout_integrations()
    update_app_routes()
    update_onboarding_slides()
    update_registration_steps()
    update_session_policy()
    update_embedded_widgets()
    update_brand_hook()
    update_di_hooks()
    update_boot_hooks()
    update_wiring_imports()
    return True


def update_router_table():
    if not os.path.exists(ROUTER_FILE):
        compose_warning(
            f"compose skipped: router file {ROUTER_FILE} missing; "
            f"generated routes/imports NOT applied"
        )
        return

    state = load_state()

    all_imports = set()
    all_routes = []

    for pkg_name, pkg_data in state.get("packages", {}).items():
        pkg_routes = pkg_data.get("routes", [])
        for r in pkg_routes:
            path = r.get("path")
            page = r.get("page")
            rtype = r.get("type", "MaterialRoute")
            imp = r.get("import")

            if imp:
                imp = imp.replace("${package}", get_project_package_name())
                all_imports.add(f"import '{imp}';")

            all_routes.append(f"    {rtype}(path: '{path}', page: {page}),")

    # Host-composition routes (see get_host_routes(), sourced from the
    # consuming app's own composer.json): merged in alongside the
    # SDK-manifest routes so they are regenerated into the @generated block
    # every time, instead of being hand-patched back after each compose.
    for r in get_host_routes():
        path = r.get("path")
        page = r.get("page")
        rtype = r.get("type", "MaterialRoute")
        imp = r.get("import")
        if imp:
            imp = imp.replace("${package}", get_project_package_name())
            all_imports.add(f"import '{imp}';")
        all_routes.append(f"    {rtype}(path: '{path}', page: {page}),")

    with open(ROUTER_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    for marker in ("// @generated-imports-start", "// @generated-routes-start"):
        if marker not in content:
            compose_warning(
                f"marker {marker} not found in {ROUTER_FILE}; "
                f"generated routes/imports NOT applied"
            )
            return

    # Inject imports
    import_block = "\n".join(sorted(list(all_imports)))
    import_replacement = (
        f"// @generated-imports-start\n{import_block}\n// @generated-imports-end"
    )
    content = re.sub(
        r"// @generated-imports-start.*?// @generated-imports-end",
        import_replacement,
        content,
        flags=re.DOTALL,
    )

    # Inject routes
    routes_block = "\n".join(all_routes)
    routes_replacement = (
        f"// @generated-routes-start\n{routes_block}\n// @generated-routes-end"
    )
    content = re.sub(
        r"// @generated-routes-start.*?// @generated-routes-end",
        routes_replacement,
        content,
        flags=re.DOTALL,
    )

    with open(ROUTER_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print("[*] Successfully updated app_router.dart with generated routes and imports.")


def update_main_dependencies():
    if not os.path.exists(MAIN_FILE):
        compose_warning(
            f"compose skipped: main.dart file {MAIN_FILE} missing; "
            f"SDK imports/DI registrations NOT applied"
        )
        return

    state = load_state()

    sdk_imports = []
    sdk_registrations = []

    # Generate imports and register statements for all active packages.
    # base_sdk must register first - base_di.dart documents this precondition
    # ("BEFORE any feature SDK's *SdkDependencies.register") because other
    # SDKs' DI can resolve base_sdk singletons. Plain alphabetical sort put
    # auth_sdk ahead of base_sdk and violated that silently (found via
    # paas_driver's hand-written pre-block workaround, which masked it).
    package_names = sorted(state.get("packages", {}).keys())
    if "base_sdk" in package_names:
        package_names.remove("base_sdk")
        package_names.insert(0, "base_sdk")
    for pkg_name in package_names:
        if pkg_name == "core_sdk":
            continue
        # Shared SDK import and dependency call
        sdk_imports.append(f"import 'package:{pkg_name}/{pkg_name}.dart';")
        # Format className as CamelCase (e.g. auth_sdk -> AuthSdkDependencies)
        class_prefix = "".join(part.capitalize() for part in pkg_name.split("_"))
        sdk_registrations.append(
            f"  {class_prefix}Dependencies.register(GetIt.instance);"
        )

    with open(MAIN_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    for marker in ("// @generated-sdk-imports-start", "// @generated-sdk-di-start"):
        if marker not in content:
            compose_warning(
                f"marker {marker} not found in {MAIN_FILE}; "
                f"SDK imports/DI registrations NOT applied"
            )
            return

    # Inject imports
    imports_block = "\n".join(sdk_imports)
    imports_replacement = f"// @generated-sdk-imports-start\n{imports_block}\n// @generated-sdk-imports-end"
    content = re.sub(
        r"// @generated-sdk-imports-start.*?// @generated-sdk-imports-end",
        imports_replacement,
        content,
        flags=re.DOTALL,
    )

    # Inject DI registrations
    di_block = "\n".join(sdk_registrations)
    di_replacement = f"// @generated-sdk-di-start\n{di_block}\n// @generated-sdk-di-end"
    content = re.sub(
        r"// @generated-sdk-di-start.*?// @generated-sdk-di-end",
        di_replacement,
        content,
        flags=re.DOTALL,
    )

    with open(MAIN_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(
        "[*] Successfully updated main.dart with generated SDK imports and DI registrations."
    )


def _clean_pkg_name(pkg):
    if pkg.endswith("_sdks"):
        return pkg[:-5]
    if pkg.endswith("_sdk"):
        return pkg[:-4]
    return pkg


def update_database_registration():
    if not os.path.exists(DB_FILE):
        compose_warning(
            f"compose skipped: app_database.dart file {DB_FILE} missing; "
            f"SDK database registrations NOT applied"
        )
        return

    state = load_state()
    all_tables = []
    migration_steps = []
    max_version = 1

    # Drift 2.x modular analysis only understands table classes defined
    # inside the package being generated - a raw cross-package import (what
    # this function used to emit) yields "The referenced element ... is not
    # understood by drift" and a silently EMPTY database. So each table's
    # source file gets copied into base_sdk's own package here (the
    # .rokct/cache copy is fully editable by design) and imported relatively,
    # same technique Supacharge's inject_sdk_tables.py proved out before this
    # was folded back into the canonical installer.
    os.makedirs(INJECTED_DB_DIR, exist_ok=True)
    copied = {}
    rel_imports = set()

    # Loop through packages and aggregate definitions to avoid overriding
    for pkg_name, pkg_data in sorted(state.get("packages", {}).items()):
        db_config = pkg_data.get("database")
        if not db_config:
            continue

        # Staged per SDK and committed only if EVERY table source copies: a
        # half-registered SDK (class names and migrations referencing tables
        # whose source drift can't see) regenerates as a broken/empty
        # database, so an SDK with any missing source contributes nothing at
        # all - no classes, no migration steps, no schemaVersion bump.
        pkg_tables = []
        pkg_imports = set()
        broken = False
        tables = db_config.get("tables", [])
        for tbl in tables:
            t_class = tbl.get("class")
            t_imp = tbl.get("import")
            if t_imp and t_imp not in copied:
                uri = t_imp
                pkg, _, rel = uri[len("package:") :].partition("/")
                clean = _clean_pkg_name(pkg)
                src = os.path.join(
                    PROJECT_ROOT, ".rokct", "cache", clean, "lib", *rel.split("/")
                )
                if not os.path.exists(src):
                    compose_warning(
                        f"{pkg_name}: table source missing ({uri}) - its cache has no lib/ "
                        f"(stripped or pinned?); DROPPING ALL of {pkg_name}'s database registration "
                        f"so the composed AppDatabase still compiles. "
                        f"Delete .rokct/cache/{clean} to force a clean re-extract."
                    )
                    broken = True
                    break
                dest_name = f"{pkg}__{os.path.basename(rel)}"
                dest = os.path.join(INJECTED_DB_DIR, dest_name)
                with open(src, "r", encoding="utf-8-sig") as sf:
                    content = sf.read()
                with open(dest, "w", encoding="utf-8", newline="\n") as df:
                    df.write(
                        f"// Copied at compose time from {uri} by "
                        f"sdk_installer_base.py's update_database_registration() -\n"
                        f"// drift only understands table classes inside its own package.\n"
                        + content
                    )
                copied[uri] = f"injected/{dest_name}"
            if t_class:
                pkg_tables.append(f"    {t_class},")
            if t_imp in copied:
                pkg_imports.add(f"import '{copied[t_imp]}';")
        if broken:
            continue
        all_tables.extend(pkg_tables)
        rel_imports.update(pkg_imports)

        migration = db_config.get("migration", {})
        version = migration.get("version")
        step = migration.get("step")
        if version and step:
            try:
                ver_int = int(version)
                if ver_int > max_version:
                    max_version = ver_int
                migration_steps.append(f"        {step}")
            except Exception:
                compose_warning(
                    f"{pkg_name}: database migration version {version!r} is not an "
                    f"integer; its migration step was NOT applied"
                )
        elif version or step:
            compose_warning(
                f"{pkg_name}: database migration declares only "
                f"{'version' if version else 'step'} (needs both 'version' and "
                f"'step'); its migration step was NOT applied"
            )

    with open(DB_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    db_markers = (
        "// @sdk-database-imports-start",
        "// @sdk-database-tables-start",
        "// @sdk-database-migrations-start",
    )
    missing_markers = [m for m in db_markers if m not in content]
    if not re.search(r"int get schemaVersion => \d+;", content):
        missing_markers.append("int get schemaVersion => <n>;")
    if missing_markers:
        compose_warning(
            f"marker(s) {', '.join(missing_markers)} not found in {DB_FILE}; "
            f"SDK database registrations NOT applied"
        )
        return

    # 1. Inject imports
    imports_block = "\n".join(sorted(rel_imports))
    imports_replacement = (
        f"// @sdk-database-imports-start\n{imports_block}\n// @sdk-database-imports-end"
    )
    content = re.sub(
        r"// @sdk-database-imports-start.*?// @sdk-database-imports-end",
        imports_replacement.replace("\\", "\\\\"),
        content,
        flags=re.DOTALL,
    )

    # 2. Inject tables
    tables_block = "\n".join(all_tables)
    tables_replacement = f"    // @sdk-database-tables-start\n{tables_block}\n    // @sdk-database-tables-end"
    content = re.sub(
        r"    // @sdk-database-tables-start.*?    // @sdk-database-tables-end",
        tables_replacement.replace("\\", "\\\\"),
        content,
        flags=re.DOTALL,
    )

    # 3. Inject schemaVersion dynamically
    content = re.sub(
        r"int get schemaVersion => \d+;",
        f"int get schemaVersion => {max_version};",
        content,
    )

    # 4. Inject migrations
    migrations_block = "\n".join(migration_steps)
    migrations_replacement = f"        // @sdk-database-migrations-start\n{migrations_block}\n        // @sdk-database-migrations-end"
    content = re.sub(
        r"        // @sdk-database-migrations-start.*?        // @sdk-database-migrations-end",
        migrations_replacement.replace("\\", "\\\\"),
        content,
        flags=re.DOTALL,
    )

    with open(DB_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(
        f"[*] Successfully updated app_database.dart. Set schemaVersion to {max_version}."
    )


def update_tr_keys_registration():
    if not os.path.exists(TRKEYS_FILE):
        compose_warning(
            f"compose skipped: tr_keys.dart file {TRKEYS_FILE} missing; "
            f"SDK translation keys NOT applied"
        )
        return

    with open(TRKEYS_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if "// @sdk-tr-keys-start" not in content:
        compose_warning(
            f"marker // @sdk-tr-keys-start not found in {TRKEYS_FILE}; "
            f"SDK translation keys NOT applied"
        )
        return

    # Constants base itself declares OUTSIDE the @sdk-tr-keys block. An SDK
    # key injected under one of these names would make the composed class
    # declare it twice ("already declared in this scope"), so those keys are
    # skipped below - base's declaration wins. The block's current contents
    # are excluded from the scan so keys injected by a previous run don't
    # mask themselves on re-compose.
    body_without_block = re.sub(
        r"// @sdk-tr-keys-start.*?  // @sdk-tr-keys-end", "", content, flags=re.DOTALL
    )
    base_owned = set(re.findall(r"static const String (\w+)\s*=", body_without_block))

    state = load_state()
    key_lines = []
    seen = {}
    for pkg_name, pkg_data in sorted(state.get("packages", {}).items()):
        tr_keys = pkg_data.get("tr_keys")
        if not tr_keys:
            continue
        for field, value in tr_keys.items():
            if field in base_owned:
                print(
                    f"  [!] tr_keys collision: '{field}' declared by '{pkg_name}' already exists in base tr_keys.dart - keeping base's declaration"
                )
                continue
            if field in seen and seen[field] != pkg_name:
                print(
                    f"  [!] tr_keys collision: '{field}' declared by both '{seen[field]}' and '{pkg_name}' - keeping first"
                )
                continue
            seen[field] = pkg_name
            escaped = value.replace("\\", "\\\\").replace("'", "\\'")
            key_lines.append(f"  static const String {field} = '{escaped}';")

    block = "\n".join(key_lines)
    replacement = f"// @sdk-tr-keys-start\n{block}\n  // @sdk-tr-keys-end"
    content = re.sub(
        r"// @sdk-tr-keys-start.*?  // @sdk-tr-keys-end",
        replacement.replace("\\", "\\\\"),
        content,
        flags=re.DOTALL,
    )

    with open(TRKEYS_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(
        f"[*] Successfully updated tr_keys.dart with {len(key_lines)} SDK-owned key(s)."
    )


def update_asset_keys_registration():
    """Inject SDK-declared AppAssets constants into base's app_assets.dart
    (exact mirror of update_tr_keys_registration): each installed SDK's
    manifest may carry `asset_keys` mapping constant name -> asset key
    string; the block between // @sdk-asset-keys-start/end is regenerated
    from all installed SDKs, first declaration wins on collisions."""
    if not os.path.exists(ASSETKEYS_FILE):
        compose_warning(
            f"compose skipped: app_assets.dart file {ASSETKEYS_FILE} missing; "
            f"SDK asset keys NOT applied"
        )
        return

    with open(ASSETKEYS_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if "// @sdk-asset-keys-start" not in content:
        compose_warning(
            f"marker // @sdk-asset-keys-start not found in {ASSETKEYS_FILE}; "
            f"SDK asset keys NOT applied"
        )
        return

    # Constants base itself declares OUTSIDE the @sdk-asset-keys block - an
    # SDK key under one of these names would be declared twice in the
    # composed class, so it is skipped and base's declaration wins (same
    # scan as update_tr_keys_registration).
    body_without_block = re.sub(
        r"// @sdk-asset-keys-start.*?  // @sdk-asset-keys-end",
        "",
        content,
        flags=re.DOTALL,
    )
    base_owned = set(re.findall(r"static const String (\w+)\s*=", body_without_block))

    state = load_state()
    key_lines = []
    seen = {}
    for pkg_name, pkg_data in sorted(state.get("packages", {}).items()):
        asset_keys = pkg_data.get("asset_keys")
        if not asset_keys:
            continue
        for field, value in asset_keys.items():
            if field in base_owned:
                print(
                    f"  [!] asset_keys collision: '{field}' declared by '{pkg_name}' already exists in base app_assets.dart - keeping base's declaration"
                )
                continue
            if field in seen and seen[field] != pkg_name:
                print(
                    f"  [!] asset_keys collision: '{field}' declared by both '{seen[field]}' and '{pkg_name}' - keeping first"
                )
                continue
            seen[field] = pkg_name
            escaped = value.replace("\\", "\\\\").replace("'", "\\'")
            key_lines.append(f"  static const String {field} = '{escaped}';")

    block = "\n".join(key_lines)
    replacement = f"// @sdk-asset-keys-start\n{block}\n  // @sdk-asset-keys-end"
    content = re.sub(
        r"// @sdk-asset-keys-start.*?  // @sdk-asset-keys-end",
        replacement.replace("\\", "\\\\"),
        content,
        flags=re.DOTALL,
    )

    with open(ASSETKEYS_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(
        f"[*] Successfully updated app_assets.dart with {len(key_lines)} SDK-owned asset key(s)."
    )


APP_ASSETS_BEGIN = (
    "    # BEGIN sdk-app-assets (generated by SDK installer - do not edit by hand)"
)
APP_ASSETS_END = "    # END sdk-app-assets"


def update_app_assets_registration():
    """Regenerate the marker-owned block of SDK-declared asset entries in the
    HOST app's pubspec.yaml (mirror of update_tr_keys_registration).

    Every installed SDK may declare `app_assets` in its manifest: a list of
    asset directory entries (e.g. "assets/team/tutors/CAPS/tutor_001/appearance/renders/")
    that must appear under `flutter: assets:` in the app so the files its
    `installs` entries placed there actually get bundled. The block between
    the markers is regenerated from ALL installed SDKs each run, so entries
    are pruned when an SDK stops declaring them. If the markers are missing
    they are created directly under the app's `assets:` line; a pubspec with
    no `assets:` line at all is left untouched (with a warning) rather than
    restructured blindly.
    """
    pubspec_path = os.path.join(PROJECT_ROOT, "pubspec.yaml")
    if not os.path.exists(pubspec_path):
        compose_warning(
            f"compose skipped: app pubspec.yaml {pubspec_path} missing; "
            f"SDK-declared asset entries NOT applied"
        )
        return

    state = load_state()
    entries = []
    seen = set()
    for pkg_name, pkg_data in sorted(state.get("packages", {}).items()):
        for entry in pkg_data.get("app_assets") or []:
            entry = str(entry).strip()
            if not entry or entry in seen:
                continue
            seen.add(entry)
            entries.append(entry)
    entries.sort()

    with open(pubspec_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    begin = end = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("# BEGIN sdk-app-assets"):
            begin = i
        elif line.strip().startswith("# END sdk-app-assets"):
            end = i

    generated = [f"    - {e}" for e in entries]

    if begin >= 0 and end > begin:
        new_lines = lines[: begin + 1] + generated + lines[end:]
    else:
        if not entries:
            return  # nothing to declare and no block to prune
        # Create the block under the first `assets:` line in the pubspec.
        assets_idx = -1
        for i, line in enumerate(lines):
            if line.strip() == "assets:":
                assets_idx = i
                break
        if assets_idx < 0:
            compose_warning(
                "app pubspec.yaml has no `assets:` line - add one under "
                "`flutter:` so SDK-declared assets can be injected; "
                "SDK-declared asset entries NOT applied"
            )
            return
        new_lines = (
            lines[: assets_idx + 1]
            + [APP_ASSETS_BEGIN]
            + generated
            + [APP_ASSETS_END]
            + lines[assets_idx + 1 :]
        )

    new_content = "\n".join(new_lines) + "\n"
    with open(pubspec_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(
        f"[*] Successfully updated app pubspec.yaml with {len(entries)} SDK-declared asset entr(y/ies)."
    )


ANDROID_MANIFEST_FILE = os.path.join(
    PROJECT_ROOT, "android", "app", "src", "main", "AndroidManifest.xml"
)
IOS_PLIST_FILE = os.path.join(PROJECT_ROOT, "ios", "Runner", "Info.plist")
ANDROID_PERMS_START = "<!-- @sdk-android-permissions-start -->"
ANDROID_PERMS_END = "<!-- @sdk-android-permissions-end -->"
IOS_USAGE_START = "<!-- @sdk-ios-usage-keys-start -->"
IOS_USAGE_END = "<!-- @sdk-ios-usage-keys-end -->"


def _xml_escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _replace_or_insert_marker_block(content, start, end, replacement, insert_at):
    """Swap the start..end marker block for `replacement`; when the file has
    no markers yet, insert `replacement` at character offset `insert_at`
    (host platform files predate the markers, and unlike main.dart their
    insertion anchor is structurally unambiguous — same self-seeding idiom
    as update_app_assets_registration's pubspec block)."""
    if start in content and end in content:
        return re.sub(
            re.escape(start) + r".*?" + re.escape(end),
            lambda _: replacement,
            content,
            flags=re.DOTALL,
        )
    return content[:insert_at] + replacement + content[insert_at:]


def update_platform_permissions():
    """Inject SDK-declared platform permission needs into the HOST app's
    android/app/src/main/AndroidManifest.xml and ios/Runner/Info.plist
    (same ownership model as update_tr_keys_registration): each installed
    SDK's manifest may carry a `platform_permissions` block —

        "platform_permissions": {
          "android": ["android.permission.POST_NOTIFICATIONS", ...],
          "ios": {"NSCalendarsUsageDescription": "<usage string>", ...}
        }

    — top-level and/or inside an app_type flavor block (flavor entries merge
    in only for the matching host, e.g. delivery_sdk's driver-only
    ACCESS_BACKGROUND_LOCATION). The marker-owned blocks are regenerated
    from full state on every run, so a removed SDK's entries vanish; a
    permission or plist key the host already declares OUTSIDE the block is
    skipped (host wins, never duplicated). Hosts whose platform files lack
    the markers get them seeded at a fixed structural anchor: right after
    the opening <manifest> tag, and right before the plist's closing
    </dict>. Declaring a permission an app does not yet request at runtime
    is harmless — Android runtime permissions are inert until requested —
    so SDKs may declare needs ahead of the feature shipping."""
    _update_android_permissions()
    _update_ios_usage_keys()


def _update_android_permissions():
    state = load_state()
    wanted = {}
    for pkg_name, pkg_data in sorted(state.get("packages", {}).items()):
        for perm in (pkg_data.get("platform_permissions") or {}).get("android", []):
            perm = str(perm).strip()
            if perm and perm not in wanted:
                wanted[perm] = pkg_name

    if not os.path.exists(ANDROID_MANIFEST_FILE):
        if wanted:
            compose_warning(
                f"compose skipped: {ANDROID_MANIFEST_FILE} missing; "
                f"{len(wanted)} SDK-declared Android permission(s) NOT applied"
            )
        return

    with open(ANDROID_MANIFEST_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Permissions the host declares outside the marker block own their name:
    # injecting them again would duplicate the <uses-permission> element.
    body_without_block = re.sub(
        re.escape(ANDROID_PERMS_START) + r".*?" + re.escape(ANDROID_PERMS_END),
        "",
        content,
        flags=re.DOTALL,
    )
    host_owned = set(
        re.findall(r'<uses-permission[^>]*android:name="([^"]+)"', body_without_block)
    )

    lines = [
        f'    <uses-permission android:name="{_xml_escape(perm)}"/>'
        for perm in sorted(wanted)
        if perm not in host_owned
    ]
    inner = ("\n" + "\n".join(lines) + "\n    ") if lines else "\n    "
    replacement = f"{ANDROID_PERMS_START}{inner}{ANDROID_PERMS_END}"

    if ANDROID_PERMS_START not in content:
        opening = re.search(r"<manifest\b[^>]*>", content, flags=re.DOTALL)
        if not opening:
            compose_warning(
                f"no <manifest> tag found in {ANDROID_MANIFEST_FILE}; "
                f"SDK-declared Android permissions NOT applied"
            )
            return
        new_content = _replace_or_insert_marker_block(
            content,
            ANDROID_PERMS_START,
            ANDROID_PERMS_END,
            "\n    " + replacement,
            opening.end(),
        )
    else:
        new_content = _replace_or_insert_marker_block(
            content, ANDROID_PERMS_START, ANDROID_PERMS_END, replacement, 0
        )

    if new_content != content:
        with open(ANDROID_MANIFEST_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
    print(
        f"[*] Successfully updated AndroidManifest.xml with {len(lines)} SDK-declared permission(s)."
    )


def _update_ios_usage_keys():
    state = load_state()
    entries = {}
    seen = {}
    for pkg_name, pkg_data in sorted(state.get("packages", {}).items()):
        ios_keys = (pkg_data.get("platform_permissions") or {}).get("ios") or {}
        for key, value in ios_keys.items():
            key = str(key).strip()
            if not key:
                continue
            if key in seen and entries.get(key) != value:
                print(
                    f"  [!] ios usage-key collision: '{key}' declared by both '{seen[key]}' and '{pkg_name}' - keeping first"
                )
                continue
            seen.setdefault(key, pkg_name)
            entries[key] = value

    if not os.path.exists(IOS_PLIST_FILE):
        if entries:
            compose_warning(
                f"compose skipped: {IOS_PLIST_FILE} missing; "
                f"{len(entries)} SDK-declared iOS usage key(s) NOT applied"
            )
        return

    with open(IOS_PLIST_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Keys the host declares outside the marker block own their name — a
    # plist with the same <key> twice is undefined behavior in practice.
    body_without_block = re.sub(
        re.escape(IOS_USAGE_START) + r".*?" + re.escape(IOS_USAGE_END),
        "",
        content,
        flags=re.DOTALL,
    )
    host_owned = set(re.findall(r"<key>([^<]+)</key>", body_without_block))

    lines = []
    for key in sorted(entries):
        if key in host_owned:
            continue
        lines.append(f"\t<key>{_xml_escape(key)}</key>")
        lines.append(f"\t<string>{_xml_escape(entries[key])}</string>")
    inner = ("\n" + "\n".join(lines) + "\n\t") if lines else "\n\t"
    replacement = f"{IOS_USAGE_START}{inner}{IOS_USAGE_END}"

    if IOS_USAGE_START not in content:
        closing = re.search(r"[ \t]*</dict>\s*</plist>", content)
        if not closing:
            compose_warning(
                f"no closing </dict></plist> found in {IOS_PLIST_FILE}; "
                f"SDK-declared iOS usage keys NOT applied"
            )
            return
        new_content = _replace_or_insert_marker_block(
            content,
            IOS_USAGE_START,
            IOS_USAGE_END,
            "\t" + replacement + "\n",
            closing.start(),
        )
    else:
        new_content = _replace_or_insert_marker_block(
            content, IOS_USAGE_START, IOS_USAGE_END, replacement, 0
        )

    if new_content != content:
        with open(IOS_PLIST_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
    print(
        f"[*] Successfully updated Info.plist with {len(lines) // 2} SDK-declared usage key(s)."
    )


def update_constants_overrides():
    state = load_state()
    imports = set()
    overrides = {}
    for pkg_name, pkg_data in sorted(state.get("packages", {}).items()):
        cfg = pkg_data.get("constants")
        if not cfg:
            continue
        if cfg.get("import"):
            imports.add(f"import '{cfg['import']}';")
        for field, expr in cfg.get("overrides", {}).items():
            overrides[field] = expr

    if not overrides:
        return

    if not os.path.exists(CONSTANTS_FILE):
        compose_warning(
            f"compose skipped: app_constants.dart file {CONSTANTS_FILE} missing; "
            f"AppConstants overrides NOT applied"
        )
        return

    with open(CONSTANTS_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    import_anchor = "import 'package:base_sdk/src/services/enums.dart';"
    for imp in sorted(imports):
        if imp not in content:
            if import_anchor not in content:
                compose_warning(
                    f"import anchor {import_anchor} not found in {CONSTANTS_FILE}; "
                    f"constants import {imp} NOT applied"
                )
                continue
            content = content.replace(
                import_anchor,
                f"{import_anchor}\n{imp}",
                1,
            )

    applied = 0
    for field, expr in overrides.items():
        pattern = (
            r"(static\s+(?:const\s+)?\w+(?:<[^>]*>)?\s+%s\s*=\s*).*?;"
            % re.escape(field)
        )
        new_content, n = re.subn(pattern, r"\1%s;" % expr, content, count=1)
        if n:
            content = new_content
            applied += 1
        else:
            compose_warning(
                f"constants override: field '{field}' not found in AppConstants; "
                f"override NOT applied"
            )

    if applied:
        with open(CONSTANTS_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[*] overrode {applied} AppConstants field(s) from home SDK manifest")


def update_layout_integrations():
    state = load_state()
    # Track layout file adjustments to rewrite them exactly once
    file_changes = {}

    for pkg_name, pkg_data in state.get("packages", {}).items():
        integrations = pkg_data.get("integrations", [])
        for integration in integrations:
            target_rel = integration.get("target")
            placeholder = integration.get("placeholder")
            replacement = integration.get("replacement")

            if not target_rel or not placeholder or not replacement:
                compose_warning(
                    f"compose skipped: malformed integrations entry for SDK {pkg_name} "
                    f"(target={target_rel!r}, placeholder={placeholder!r}) - it needs "
                    f"non-empty 'target', 'placeholder' and 'replacement'; wiring NOT applied"
                )
                continue

            target_abs = os.path.join(PROJECT_ROOT, target_rel)
            if not os.path.exists(target_abs):
                compose_warning(
                    f"compose skipped: target file {target_rel} missing for SDK "
                    f"{pkg_name} (placeholder {placeholder}); wiring NOT applied"
                )
                continue

            # Read current file text (either original or accumulated in loop)
            content = file_changes.get(target_abs)
            if content is None:
                with open(target_abs, "r", encoding="utf-8") as f:
                    content = f.read()

            # Prevent double injection: Check if replacement is already in file
            if replacement in content:
                continue

            if placeholder not in content:
                compose_warning(
                    f"marker {placeholder} not found in {target_rel} for SDK "
                    f"{pkg_name}; wiring NOT applied"
                )
                continue

            # Replace placeholder while preserving it for future updates
            replacement_block = f"{placeholder}\n{replacement}"
            content = content.replace(placeholder, replacement_block)
            file_changes[target_abs] = content

    # Write changes back
    for path, content in file_changes.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        rel_path = os.path.relpath(path, PROJECT_ROOT).replace("\\", "/")
        print(f"[*] Applied widget layout integration in: {rel_path}")


def update_app_routes():
    """Injects AppRoutes.I method implementations into main.dart's
    _HostAppRoutes scaffold (see the base_sdk template) from each installed
    SDK's manifest.json "app_routes" list — e.g. auth_sdk declares
    replaceLoginRoute so every app that installs it gets real login
    navigation without hand-wiring it. A method is only injected if some
    installed SDK actually needs it; anything else keeps throwing via
    _HostAppRoutes' noSuchMethod. Apps that hand-edit main.dart (main.dart
    detects host edits and stops being overwritten by ensure_file/copy_dir)
    keep whatever they wrote instead — this only touches the marker block.

    An entry may additionally carry an optional "imports" list (FULL import
    lines, ${package} substituted) so the route classes its body references
    (LoginRoute, ScheduleRoute, ...) resolve in a fully generated main.dart —
    those lines land in the @generated-wiring-imports block via
    update_wiring_imports(), not here. Entries without "imports" keep working
    exactly as before.
    """
    if not os.path.exists(MAIN_FILE):
        compose_warning(
            f"compose skipped: main.dart file {MAIN_FILE} missing; "
            f"AppRoutes methods NOT applied"
        )
        return

    state = load_state()
    all_methods = []
    seen_methods = set()
    for pkg_name, pkg_data in state.get("packages", {}).items():
        for r in pkg_data.get("app_routes", []):
            method = r.get("method")
            params = r.get("params", "BuildContext context")
            body = r.get("body")
            if not method or not body:
                continue
            if method in seen_methods:
                print(
                    f"  [!] app_routes: {method} already provided by another SDK, skipping {pkg_name}'s"
                )
                continue
            seen_methods.add(method)
            all_methods.append(
                f"  @override\n  Future<Object?> {method}({params}) => {body}\n"
            )

    with open(MAIN_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if "// @generated-approutes-start" not in content:
        if all_methods:
            compose_warning(
                f"marker // @generated-approutes-start not found in {MAIN_FILE}; "
                f"{len(all_methods)} AppRoutes method(s) NOT applied"
            )
        return

    methods_block = "\n".join(all_methods)
    replacement = f"  // @generated-approutes-start\n{methods_block}\n  // @generated-approutes-end"
    new_content = re.sub(
        r"  // @generated-approutes-start.*?// @generated-approutes-end",
        replacement,
        content,
        flags=re.DOTALL,
    )

    if new_content != content:
        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"[*] Injected {len(all_methods)} AppRoutes method(s) into main.dart")


def update_onboarding_slides():
    """Injects OnboardingSlide entries into the onboarding shell's slide list
    (onboarding_sdk's templates/routes/onboarding_route_pages.dart, installed
    to lib/presentation/routes/onboarding_route_pages.dart) from each
    installed SDK's manifest.json "onboarding_slides" list — the exact same
    pattern update_app_routes() uses for main.dart's _HostAppRoutes block.
    e.g. lms_sdk declares its grade-capture slide so every app that installs
    lms_sdk + onboarding_sdk gets that step without hand-wiring it.

    Each entry is keyed by "id" (unique across SDKs — a duplicate id is
    skipped with a warning, like app_routes' duplicate methods) and sequenced
    by its integer "order" field. Two slides declaring the SAME order is
    surfaced with a warning, then both are kept and tie-broken
    deterministically by id — sequencing must be stable across recomposes,
    and dropping a slide silently would be worse than a suboptimal order.
    An entry's "body" is the OnboardingSlide(...) Dart expression injected
    verbatim (no trailing comma — added here); its optional "imports" list
    (package URIs, ${package} substituted) lands in the shell's
    @generated-onboarding-imports block so bodies can reference host
    composition symbols (e.g. an adapter living in lms_route_pages.dart).

    Apps without onboarding_sdk have no shell file — nothing to do. Apps
    that hand-edit the installed shell keep their edits (the file sync skips
    drifted files); this only rewrites the marker blocks.
    """
    state = load_state()
    slides = []
    all_imports = set()
    seen_ids = {}
    for pkg_name, pkg_data in state.get("packages", {}).items():
        for s in pkg_data.get("onboarding_slides", []):
            slide_id = s.get("id")
            body = s.get("body")
            if not slide_id or not body:
                continue
            if slide_id in seen_ids:
                print(
                    f"  [!] onboarding_slides: '{slide_id}' already provided by {seen_ids[slide_id]}, skipping {pkg_name}'s"
                )
                continue
            seen_ids[slide_id] = pkg_name
            try:
                order = int(s.get("order", 0))
            except (TypeError, ValueError):
                order = 0
            for imp in s.get("imports", []):
                imp = imp.replace("${package}", get_project_package_name())
                all_imports.add(f"import '{imp}';")
            slides.append((order, slide_id, pkg_name, body))

    # Surface order collisions instead of silently picking: keep every slide,
    # warn, and tie-break deterministically by id (already the sort key).
    orders_seen = {}
    for order, slide_id, pkg_name, _ in slides:
        orders_seen.setdefault(order, []).append((slide_id, pkg_name))
    for order, entries in sorted(orders_seen.items()):
        if len(entries) > 1:
            listing = ", ".join(f"'{sid}' ({pkg})" for sid, pkg in sorted(entries))
            print(
                f"  [!] onboarding_slides: order {order} declared by {listing} - keeping all, tie-broken by id; declare distinct orders to control the sequence"
            )

    if not os.path.exists(ONBOARDING_ROUTES_FILE):
        # No onboarding shell installed is normal for apps without
        # onboarding_sdk - but if some SDK DID declare slides, they are
        # being dropped, and that must not be silent.
        if slides:
            compose_warning(
                f"compose skipped: onboarding shell {ONBOARDING_ROUTES_FILE} missing "
                f"while SDK(s) {', '.join(sorted(set(s[2] for s in slides)))} declare "
                f"onboarding_slides; wiring NOT applied"
            )
        return

    slides.sort(key=lambda t: (t[0], t[1]))

    slide_blocks = []
    for order, slide_id, pkg_name, body in slides:
        lines = [f"      // {slide_id} (order {order}, from {pkg_name})"]
        for line in body.splitlines():
            lines.append(f"      {line}" if line.strip() else "")
        slide_blocks.append("\n".join(lines) + ",")
    slides_block = "\n".join(slide_blocks)

    with open(ONBOARDING_ROUTES_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if "// @generated-onboarding-slides-start" not in content:
        if slides:
            compose_warning(
                f"marker // @generated-onboarding-slides-start not found in "
                f"{ONBOARDING_ROUTES_FILE}; {len(slides)} onboarding slide(s) NOT applied"
            )
        return

    imports_block = "\n".join(sorted(all_imports))
    imports_replacement = f"// @generated-onboarding-imports-start\n{imports_block}\n// @generated-onboarding-imports-end"
    new_content = re.sub(
        r"// @generated-onboarding-imports-start.*?// @generated-onboarding-imports-end",
        imports_replacement.replace("\\", "\\\\"),
        content,
        flags=re.DOTALL,
    )

    slides_replacement = f"      // @generated-onboarding-slides-start\n{slides_block}\n      // @generated-onboarding-slides-end"
    new_content = re.sub(
        r"      // @generated-onboarding-slides-start.*?// @generated-onboarding-slides-end",
        slides_replacement.replace("\\", "\\\\"),
        new_content,
        flags=re.DOTALL,
    )

    if new_content != content:
        with open(ONBOARDING_ROUTES_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(
            f"[*] Injected {len(slides)} onboarding slide(s) into onboarding_route_pages.dart"
        )


def update_registration_steps():
    """Injects RegistrationStep entries into auth_sdk's registration-steps
    shell (auth_sdk's templates/routes/registration_step_pages.dart, installed
    to lib/presentation/routes/registration_step_pages.dart) from each
    installed SDK's manifest.json "registration_steps" list — the exact same
    composition pattern update_onboarding_slides() uses for the onboarding
    shell, applied to auth_sdk's register flow ("auth can do what we do with
    onboarding"). e.g. lms_sdk declares its school + grade capture steps so a
    student who registers directly (skipping onboarding) is still asked for
    school and grade, without auth_sdk ever learning what a school is.

    Each entry is keyed by "id" (unique across SDKs — a duplicate id is
    skipped with a warning, like app_routes' duplicate methods) and sequenced
    by its integer "order" field. Two steps declaring the SAME order is
    surfaced with a warning, then both are kept and tie-broken
    deterministically by id — sequencing must be stable across recomposes,
    and dropping a step silently would be worse than a suboptimal order.
    An entry's "body" is the RegistrationStep(...) Dart expression injected
    verbatim (no trailing comma — added here); per-step metadata such as
    skippable lives INSIDE that expression (RegistrationStep(skippable:
    ...)), not in the manifest, so the installer stays a dumb pipe. The
    optional "imports" list (package URIs, ${package} substituted) lands in
    the shell's @generated-registration-imports block so bodies can reference
    host composition symbols (e.g. the capture adapters living in
    lms_route_pages.dart).

    Apps without auth_sdk have no shell file — nothing to do. Apps that
    hand-edit the installed shell keep their edits (the file sync skips
    drifted files); this only rewrites the marker blocks.
    """
    state = load_state()
    steps = []
    all_imports = set()
    seen_ids = {}
    for pkg_name, pkg_data in state.get("packages", {}).items():
        for s in pkg_data.get("registration_steps", []):
            step_id = s.get("id")
            body = s.get("body")
            if not step_id or not body:
                continue
            if step_id in seen_ids:
                print(
                    f"  [!] registration_steps: '{step_id}' already provided by {seen_ids[step_id]}, skipping {pkg_name}'s"
                )
                continue
            seen_ids[step_id] = pkg_name
            try:
                order = int(s.get("order", 0))
            except (TypeError, ValueError):
                order = 0
            for imp in s.get("imports", []):
                imp = imp.replace("${package}", get_project_package_name())
                all_imports.add(f"import '{imp}';")
            steps.append((order, step_id, pkg_name, body))

    # Surface order collisions instead of silently picking: keep every step,
    # warn, and tie-break deterministically by id (already the sort key).
    orders_seen = {}
    for order, step_id, pkg_name, _ in steps:
        orders_seen.setdefault(order, []).append((step_id, pkg_name))
    for order, entries in sorted(orders_seen.items()):
        if len(entries) > 1:
            listing = ", ".join(f"'{sid}' ({pkg})" for sid, pkg in sorted(entries))
            print(
                f"  [!] registration_steps: order {order} declared by {listing} - keeping all, tie-broken by id; declare distinct orders to control the sequence"
            )

    if not os.path.exists(REGISTRATION_STEPS_FILE):
        # No auth shell installed is normal for apps without auth_sdk - but
        # if some SDK DID declare registration steps, they are being
        # dropped, and that must not be silent.
        if steps:
            compose_warning(
                f"compose skipped: registration shell {REGISTRATION_STEPS_FILE} missing "
                f"while SDK(s) {', '.join(sorted(set(s[2] for s in steps)))} declare "
                f"registration_steps; wiring NOT applied"
            )
        return

    steps.sort(key=lambda t: (t[0], t[1]))

    step_blocks = []
    for order, step_id, pkg_name, body in steps:
        lines = [f"      // {step_id} (order {order}, from {pkg_name})"]
        for line in body.splitlines():
            lines.append(f"      {line}" if line.strip() else "")
        step_blocks.append("\n".join(lines) + ",")
    steps_block = "\n".join(step_blocks)

    with open(REGISTRATION_STEPS_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if "// @generated-registration-steps-start" not in content:
        if steps:
            compose_warning(
                f"marker // @generated-registration-steps-start not found in "
                f"{REGISTRATION_STEPS_FILE}; {len(steps)} registration step(s) NOT applied"
            )
        return

    imports_block = "\n".join(sorted(all_imports))
    imports_replacement = f"// @generated-registration-imports-start\n{imports_block}\n// @generated-registration-imports-end"
    new_content = re.sub(
        r"// @generated-registration-imports-start.*?// @generated-registration-imports-end",
        imports_replacement.replace("\\", "\\\\"),
        content,
        flags=re.DOTALL,
    )

    steps_replacement = f"      // @generated-registration-steps-start\n{steps_block}\n      // @generated-registration-steps-end"
    new_content = re.sub(
        r"      // @generated-registration-steps-start.*?// @generated-registration-steps-end",
        steps_replacement.replace("\\", "\\\\"),
        new_content,
        flags=re.DOTALL,
    )

    if new_content != content:
        with open(REGISTRATION_STEPS_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(
            f"[*] Injected {len(steps)} registration step(s) into registration_step_pages.dart"
        )


def update_session_policy():
    """Injects the app's declared session policy into auth_sdk's installed
    auth_session_policy.dart shell (templates/routes/auth_session_policy.dart
    -> lib/presentation/routes/auth_session_policy.dart) — the seam that
    lets a composition say which account roles may sign in and where each
    lands, instead of the app keeping its own auth pages (manager: sellers
    only -> /main; driver: deliveryman -> /home, everyone else kept
    signed-in on /become-driver).

    Declared as manifest.json "session_policy" (top level or app_type
    flavor block, flavor winning):

        "session_policy": {
          "allowed_roles": [
            {"role": "seller", "landing_route": "/main"}
          ],
          "rejection_message_tr_key": "access.denied",
          "rejection_route": "/login"
        }

    allowed_roles maps each admitted role to the route PATH it lands on
    after sign-in (paths, not route classes — same ADR-005 bridge as
    '/registration-steps'); rejection_* are optional. An entry may use the
    FALLBACK role "*" (auth_sdk >= 1.4.0's DeclaredSessionPolicy.fallbackRole):
    an authenticated account whose role matches no other entry is then
    ADMITTED — token persisted, session KEPT — and lands on the fallback's
    route instead of being rejected. Driver's shape:

        "allowed_roles": [
          {"role": "deliveryman", "landing_route": "/home"},
          {"role": "*", "landing_route": "/become-driver"}
        ]

    Exact roles always win over "*" (auth_sdk resolves the exact landing
    first), and with a "*" entry nothing is ever rejected, so rejection_*
    become inert. A policy WITHOUT "*" keeps the reject behavior unchanged
    (manager's seller-only gate). The installer is a dumb pipe here — "*"
    is just another roleLandings key; the semantics live in auth_sdk — but
    it does reject a duplicated role (including two "*" entries), since the
    Dart map literal would silently keep only the last landing. Values are
    injected into single-quoted Dart string literals, so they must not
    contain quotes or backslashes — the installer stays a dumb pipe and
    rejects them instead of escaping.

    Exactly zero or one installed SDK may declare a policy. Two apps'
    worth of login gates is not a tie to break silently (whichever lost
    would admit the wrong accounts), so like brand_hook this raises a hard
    error naming every declaring SDK.

    Apps without auth_sdk have no shell file — nothing to do. With no
    declaration the marker block is emptied, auth_sdk's built-in default
    policy stays in force, and login behaves exactly as before the seam
    existed (supacharge/minilauncher unchanged).
    """
    state = load_state()
    declared = {}
    for pkg_name, pkg_data in state.get("packages", {}).items():
        policy = pkg_data.get("session_policy")
        if policy and policy.get("allowed_roles"):
            declared[pkg_name] = policy

    if not os.path.exists(SESSION_POLICY_FILE):
        # No auth shell installed is normal for apps without auth_sdk - but
        # if some SDK DID declare a session policy, it is being dropped, and
        # that must not be silent.
        if declared:
            compose_warning(
                f"compose skipped: session-policy shell {SESSION_POLICY_FILE} missing "
                f"while SDK(s) {', '.join(sorted(declared))} declare a session_policy; "
                f"wiring NOT applied"
            )
        return

    if len(declared) > 1:
        names = ", ".join(f"'{n}'" for n in sorted(declared))
        raise RuntimeError(
            f"session_policy conflict: {len(declared)} installed SDKs ({names}) each declare "
            f"a session policy, but a composed app can only admit accounts under one. "
            f"Remove the declaration from every SDK but the app's home SDK."
        )

    def _lit(value, field):
        value = str(value)
        if "'" in value or "\\" in value or "\n" in value:
            raise RuntimeError(
                f"session_policy: {field} value {value!r} may not contain quotes, "
                f"backslashes or newlines — it is injected into a Dart string literal verbatim."
            )
        return f"'{value}'"

    body_lines = []
    if declared:
        pkg_name, policy = next(iter(declared.items()))
        landings = []
        seen_roles = set()
        for entry in policy.get("allowed_roles", []):
            role = entry.get("role")
            landing = entry.get("landing_route")
            if not role or not landing:
                print(
                    f"  [!] session_policy: skipping allowed_roles entry without role/landing_route in {pkg_name}"
                )
                continue
            if role in seen_roles:
                raise RuntimeError(
                    f"session_policy: role {role!r} declared more than once in {pkg_name}'s "
                    f"allowed_roles — the generated Dart map literal would silently keep only "
                    f"the last landing. Keep exactly one entry per role (including the '*' fallback)."
                )
            seen_roles.add(role)
            landings.append(
                f"      {_lit(role, 'role')}: {_lit(landing, 'landing_route')},"
            )
        if landings:
            body_lines.append(f"  // declared by {pkg_name}")
            body_lines.append("  AuthSessionPolicy.I = DeclaredSessionPolicy(")
            body_lines.append("    roleLandings: {")
            body_lines.extend(landings)
            body_lines.append("    },")
            msg = policy.get("rejection_message_tr_key")
            if msg:
                body_lines.append(
                    f"    rejectionMessageTrKey: {_lit(msg, 'rejection_message_tr_key')},"
                )
            route = policy.get("rejection_route")
            if route:
                body_lines.append(
                    f"    rejectionRoute: {_lit(route, 'rejection_route')},"
                )
            body_lines.append("  );")
    policy_block = "\n".join(body_lines)

    with open(SESSION_POLICY_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if "// @generated-session-policy-start" not in content:
        if declared:
            compose_warning(
                f"marker // @generated-session-policy-start not found in "
                f"{SESSION_POLICY_FILE}; session policy from "
                f"{', '.join(sorted(declared))} NOT applied"
            )
        return

    replacement = f"  // @generated-session-policy-start\n{policy_block}\n  // @generated-session-policy-end"
    new_content = re.sub(
        r"  // @generated-session-policy-start.*?// @generated-session-policy-end",
        replacement.replace("\\", "\\\\"),
        content,
        flags=re.DOTALL,
    )

    if new_content != content:
        with open(SESSION_POLICY_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(
            "[*] Injected session policy into auth_session_policy.dart"
            if policy_block
            else "[*] Cleared session policy in auth_session_policy.dart"
        )


def update_embedded_widgets():
    """Injects EmbeddedWidgets.I method implementations into main.dart's
    _HostEmbeddedWidgets scaffold (see the base_sdk template) from each
    installed SDK's manifest.json "embedded_widgets" list — the exact same
    pattern update_app_routes() uses for the _HostAppRoutes block. e.g.
    onboarding_sdk declares introPage so auth_sdk's "Skip" action can render
    the intro carousel without importing onboarding_sdk directly (ADR-005).
    A method is only injected if some installed SDK actually provides it;
    anything else keeps throwing a descriptive StateError via
    _HostEmbeddedWidgets' noSuchMethod rather than silently rendering a
    blank widget.

    Entry shape mirrors app_routes: {"method", "params" (optional, defaults
    to no parameters), "body" (Dart statements, e.g. "return const
    OnboardingIntroRouteView();"), "imports" (optional FULL import lines,
    ${package} substituted, landing in the @generated-wiring-imports block
    via update_wiring_imports())}. The same method declared by two SDKs keeps
    the first SDK's implementation, like app_routes — but loudly: both SDK
    names and the method are printed so the collision is fixed at the
    manifests, not discovered at runtime.

    Older host main.dart files predating the _HostEmbeddedWidgets scaffold
    have no markers — nothing to do there beyond a printed notice; this only
    rewrites the marker block.
    """
    if not os.path.exists(MAIN_FILE):
        compose_warning(
            f"compose skipped: main.dart file {MAIN_FILE} missing; "
            f"EmbeddedWidgets methods NOT applied"
        )
        return

    state = load_state()
    all_methods = []
    seen_methods = {}
    for pkg_name, pkg_data in state.get("packages", {}).items():
        for w in pkg_data.get("embedded_widgets", []):
            method = w.get("method")
            params = w.get("params", "")
            body = w.get("body")
            if not method or not body:
                continue
            if method in seen_methods:
                print(
                    f"  [!] WARNING: embedded_widgets conflict: '{method}' is declared by both '{seen_methods[method]}' and '{pkg_name}' - keeping '{seen_methods[method]}'s implementation and skipping '{pkg_name}'s. Remove one manifest declaration to resolve this."
                )
                continue
            seen_methods[method] = pkg_name
            body_lines = "\n".join(
                f"    {line}" if line.strip() else "" for line in body.splitlines()
            )
            all_methods.append(
                f"  @override\n  Widget {method}({params}) {{\n{body_lines}\n  }}\n"
            )

    with open(MAIN_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if "// @generated-embeddedwidgets-start" not in content:
        if all_methods:
            compose_warning(
                f"marker // @generated-embeddedwidgets-start not found in {MAIN_FILE} "
                f"(older host template); {len(all_methods)} EmbeddedWidgets method(s) NOT applied"
            )
        else:
            print(
                "  [i] main.dart has no @generated-embeddedwidgets markers (older host template) - skipping embedded-widget injection"
            )
        return

    methods_block = "\n".join(all_methods)
    replacement = f"  // @generated-embeddedwidgets-start\n{methods_block}\n  // @generated-embeddedwidgets-end"
    new_content = re.sub(
        r"  // @generated-embeddedwidgets-start.*?// @generated-embeddedwidgets-end",
        lambda _: replacement,
        content,
        flags=re.DOTALL,
    )

    if new_content != content:
        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(
            f"[*] Injected {len(all_methods)} EmbeddedWidgets method(s) into main.dart"
        )


def update_brand_hook():
    """Injects the ONE brand-hook call into main() (the base_sdk template's
    @generated-brandhook block, placed before the SystemChrome setup so the
    palette lands in the shared AppStyle tokens before the first frame — the
    kernel ships neutral defaults only). Declared per-SDK as manifest.json
    "brand_hook": {"body": "applyAppBrandColors();", "imports": [...]} —
    normally by the home SDK, whose installed theme template defines the
    hook function.

    Exactly zero or one installed SDK may declare it. Two SDKs both claiming
    the brand is not a tie to break silently — whichever lost would ship an
    app wearing the wrong brand — so this raises a hard error naming every
    declaring SDK instead of picking one.

    Older host main.dart files predating the marker get a printed notice and
    no changes; this only rewrites the marker block.
    """
    if not os.path.exists(MAIN_FILE):
        compose_warning(
            f"compose skipped: main.dart file {MAIN_FILE} missing; "
            f"brand hook NOT applied"
        )
        return

    state = load_state()
    declared = {}
    for pkg_name, pkg_data in state.get("packages", {}).items():
        hook = pkg_data.get("brand_hook")
        if hook and hook.get("body"):
            declared[pkg_name] = hook

    if len(declared) > 1:
        names = ", ".join(f"'{n}'" for n in sorted(declared))
        raise RuntimeError(
            f"brand_hook conflict: {len(declared)} installed SDKs ({names}) each declare "
            'a "brand_hook" in their manifest, but at most ONE may own the app\'s brand '
            "- the hook runs exactly once before the first frame. Remove the "
            '"brand_hook" key from every manifest except the one true brand owner '
            "(normally the home SDK) and recompose."
        )

    body_lines = []
    for pkg_name, hook in declared.items():
        for line in hook["body"].splitlines():
            body_lines.append(f"  {line}" if line.strip() else "")

    with open(MAIN_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if "// @generated-brandhook-start" not in content:
        if declared:
            compose_warning(
                f"marker // @generated-brandhook-start not found in {MAIN_FILE} "
                f"(older host template); brand hook from "
                f"{', '.join(sorted(declared))} NOT applied"
            )
        else:
            print(
                "  [i] main.dart has no @generated-brandhook markers (older host template) - skipping brand-hook injection"
            )
        return

    hook_block = "\n".join(body_lines)
    replacement = (
        f"  // @generated-brandhook-start\n{hook_block}\n  // @generated-brandhook-end"
    )
    new_content = re.sub(
        r"  // @generated-brandhook-start.*?// @generated-brandhook-end",
        lambda _: replacement,
        content,
        flags=re.DOTALL,
    )

    if new_content != content:
        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(
            f"[*] Injected brand hook from {', '.join(sorted(declared)) or 'no SDK'} into main.dart"
        )


def _update_main_hooks(state_key, marker, label):
    """Shared engine for update_di_hooks()/update_boot_hooks(): regenerates
    ONE marker-owned block in main.dart from every installed SDK's
    manifest.json list named `state_key` — the exact same composition
    pattern update_registration_steps() applies to auth_sdk's shell, aimed
    at main() instead of a route shell.

    Entry schema (identical for both keys, flavor-gatable under an
    "app_type" block like every other manifest list):

        {"id": "<unique across SDKs>",
         "order": <int, optional, default 0>,
         "body": "<Dart statements, injected verbatim>",
         "imports": ["<FULL import lines, ${package} substituted>", ...]}

    Each entry is keyed by "id" (a duplicate id is skipped with a loud
    warning naming both SDKs, like app_routes' duplicate methods) and
    sequenced by its integer "order" field. Two entries declaring the SAME
    order is surfaced with a warning, then both are kept and tie-broken
    deterministically by id — sequencing must be stable across recomposes,
    and dropping a hook silently would be worse than a suboptimal order.
    "body" is injected verbatim (statement lines, not an expression — no
    comma handling); its optional "imports" list ships FULL import lines
    that land in the @generated-wiring-imports block via
    update_wiring_imports(), same as app_routes/embedded_widgets/brand_hook.

    A removed SDK's hooks vanish on the next regeneration — the block is
    rebuilt from full state every run. Older host main.dart files predating
    the markers get a printed notice and no changes; this only rewrites the
    marker block.
    """
    if not os.path.exists(MAIN_FILE):
        compose_warning(
            f"compose skipped: main.dart file {MAIN_FILE} missing; {label}s NOT applied"
        )
        return

    state = load_state()
    hooks = []
    seen_ids = {}
    for pkg_name, pkg_data in state.get("packages", {}).items():
        for h in pkg_data.get(state_key, []):
            hook_id = h.get("id")
            body = h.get("body")
            if not hook_id or not body:
                continue
            if hook_id in seen_ids:
                print(
                    f"  [!] {state_key}: '{hook_id}' already provided by {seen_ids[hook_id]}, skipping {pkg_name}'s"
                )
                continue
            seen_ids[hook_id] = pkg_name
            try:
                order = int(h.get("order", 0))
            except (TypeError, ValueError):
                order = 0
            hooks.append((order, hook_id, pkg_name, body))

    # Surface order collisions instead of silently picking: keep every hook,
    # warn, and tie-break deterministically by id (already the sort key).
    orders_seen = {}
    for order, hook_id, pkg_name, _ in hooks:
        orders_seen.setdefault(order, []).append((hook_id, pkg_name))
    for order, entries in sorted(orders_seen.items()):
        if len(entries) > 1:
            listing = ", ".join(f"'{hid}' ({pkg})" for hid, pkg in sorted(entries))
            print(
                f"  [!] {state_key}: order {order} declared by {listing} - keeping all, tie-broken by id; declare distinct orders to control the sequence"
            )

    hooks.sort(key=lambda t: (t[0], t[1]))

    hook_blocks = []
    for order, hook_id, pkg_name, body in hooks:
        lines = [f"  // {hook_id} (order {order}, from {pkg_name})"]
        for line in body.splitlines():
            lines.append(f"  {line}" if line.strip() else "")
        hook_blocks.append("\n".join(lines))
    hooks_block = "\n".join(hook_blocks)

    with open(MAIN_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if f"// {marker}-start" not in content:
        if hooks:
            compose_warning(
                f"marker // {marker}-start not found in {MAIN_FILE} "
                f"(older host template); {len(hooks)} {label}(s) NOT applied"
            )
        else:
            print(
                f"  [i] main.dart has no @{marker.lstrip('@')} markers (older host template) - skipping {label} injection"
            )
        return

    replacement = f"  // {marker}-start\n{hooks_block}\n  // {marker}-end"
    new_content = re.sub(
        rf"  // {re.escape(marker)}-start.*?// {re.escape(marker)}-end",
        lambda _: replacement,
        content,
        flags=re.DOTALL,
    )

    if new_content != content:
        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"[*] Injected {len(hooks)} {label}(s) into main.dart")


def update_di_hooks():
    """Injects SDK-declared DI statements into main.dart's
    @generated-di-hooks block (directly AFTER the @generated-sdk-di block,
    so hook bodies can resolve anything the *SdkDependencies.register calls
    just registered — base_sdk singletons included). Declared per-SDK as
    manifest.json "di_hooks", normally inside an app_type flavor block:
    e.g. orders_sdk's manager block registers its role DI
    (ManagerOrdersDependencies.register) and the ADR-005 facade adapters
    living in its OWN installed orders_adapters.dart (host-composition code,
    reachable via ${package} imports). See _update_main_hooks for the entry
    schema and conflict semantics."""
    _update_main_hooks("di_hooks", "@generated-di-hooks", "DI hook")


def update_boot_hooks():
    """Injects SDK-declared boot statements into main.dart's
    @generated-boot-hooks block (at the TOP of main(), right after
    WidgetsFlutterBinding.ensureInitialized() and before the brand hook —
    this generalizes brand_hook, which stays as-is for the one brand call).
    Declared per-SDK as manifest.json "boot_hooks": e.g. comms_sdk (push
    owner) declares the Firebase/FCM boot, a splash-holding app declares
    FlutterNativeSplash.preserve. Bodies may await — the template's main()
    is async. See _update_main_hooks for the entry schema and conflict
    semantics."""
    _update_main_hooks("boot_hooks", "@generated-boot-hooks", "boot hook")


def update_wiring_imports():
    """Regenerates main.dart's @generated-wiring-imports block (directly
    below the @generated-sdk-imports block) from the optional "imports"
    lists of every installed SDK's app_routes, embedded_widgets,
    brand_hook, di_hooks and boot_hooks declarations. Each entry ships FULL import lines (e.g.
    "import 'package:${package}/presentation/routes/app_router.dart';",
    ${package} substituted here) so the symbols its injected body references
    resolve in a fully generated main.dart without hand-written imports.
    Collected from full state, deduped and sorted — a removed SDK's imports
    vanish on the next regeneration, same as every other marker block.

    Older host main.dart files predating the marker get a printed notice and
    no changes; this only rewrites the marker block.
    """
    if not os.path.exists(MAIN_FILE):
        compose_warning(
            f"compose skipped: main.dart file {MAIN_FILE} missing; "
            f"wiring imports NOT applied"
        )
        return

    state = load_state()
    package_name = get_project_package_name()
    all_imports = set()
    for pkg_name, pkg_data in state.get("packages", {}).items():
        wiring_entries = list(pkg_data.get("app_routes", []))
        wiring_entries += pkg_data.get("embedded_widgets", [])
        wiring_entries += pkg_data.get("di_hooks", [])
        wiring_entries += pkg_data.get("boot_hooks", [])
        if pkg_data.get("brand_hook"):
            wiring_entries.append(pkg_data["brand_hook"])
        for entry in wiring_entries:
            for imp in entry.get("imports", []) or []:
                imp = imp.replace("${package}", package_name).strip()
                if imp:
                    all_imports.add(imp)

    with open(MAIN_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if "// @generated-wiring-imports-start" not in content:
        if all_imports:
            compose_warning(
                f"marker // @generated-wiring-imports-start not found in {MAIN_FILE} "
                f"(older host template); {len(all_imports)} wiring import(s) NOT applied"
            )
        else:
            print(
                "  [i] main.dart has no @generated-wiring-imports markers (older host template) - skipping wiring-import injection"
            )
        return

    imports_block = "\n".join(sorted(all_imports))
    replacement = f"// @generated-wiring-imports-start\n{imports_block}\n// @generated-wiring-imports-end"
    new_content = re.sub(
        r"// @generated-wiring-imports-start.*?// @generated-wiring-imports-end",
        lambda _: replacement,
        content,
        flags=re.DOTALL,
    )

    if new_content != content:
        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"[*] Injected {len(all_imports)} wiring import(s) into main.dart")


if __name__ == "__main__":
    update_router_table()
    update_main_dependencies()
    update_database_registration()
    update_platform_permissions()
    update_layout_integrations()
    update_app_routes()
    update_onboarding_slides()
    update_registration_steps()
    update_session_policy()
    update_embedded_widgets()
    update_brand_hook()
    update_di_hooks()
    update_boot_hooks()
    update_wiring_imports()
