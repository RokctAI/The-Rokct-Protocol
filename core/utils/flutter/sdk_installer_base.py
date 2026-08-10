import os
import json
import shutil
import hashlib
import re
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(PROJECT_ROOT, ".rokct", "install_state.json")
ROUTER_FILE = os.path.join(PROJECT_ROOT, "lib", "presentation", "routes", "app_router.dart")
MAIN_FILE = os.path.join(PROJECT_ROOT, "lib", "main.dart")
DB_FILE = os.path.join(PROJECT_ROOT, ".rokct", "cache", "base", "lib", "src", "database", "app_database.dart")
TRKEYS_FILE = os.path.join(PROJECT_ROOT, ".rokct", "cache", "base", "lib", "src", "services", "tr_keys.dart")
ASSETKEYS_FILE = os.path.join(PROJECT_ROOT, ".rokct", "cache", "base", "lib", "src", "services", "app_assets.dart")
CONSTANTS_FILE = os.path.join(PROJECT_ROOT, ".rokct", "cache", "base", "lib", "src", "constants", "app_constants.dart")
INJECTED_DB_DIR = os.path.join(PROJECT_ROOT, ".rokct", "cache", "base", "lib", "src", "database", "injected")
ONBOARDING_ROUTES_FILE = os.path.join(PROJECT_ROOT, "lib", "presentation", "routes", "onboarding_route_pages.dart")

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
                except Exception:
                    pass
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
    try:
        # Run flutter create in the current directory
        # --project-name ensures the internal package name is correct
        subprocess.run(["flutter", "create", "--project-name", package_name, "."], check=True, shell=True)
        global FRESH_SCAFFOLD
        FRESH_SCAFFOLD = True
    except subprocess.CalledProcessError as e:
        print(f"[-] Critical Error: 'flutter create' failed: {e}")
    except FileNotFoundError:
        print("[-] Critical Error: 'flutter' command not found. Please ensure Flutter is installed and in your PATH.")

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
        src_path = os.path.join(home_sdk_path, from_rel)
        dest_path = os.path.join(PROJECT_ROOT, to_rel)
        if os.path.exists(src_path):
            if os.path.isdir(src_path):
                if os.path.exists(dest_path):
                    shutil.rmtree(dest_path)
                shutil.copytree(src_path, dest_path)
            else:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                if src_path.endswith((".dart", ".yaml", ".json", ".txt", ".md", ".gradle", ".properties")):
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
    state = {"packages": {}}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            pass
    
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
    except Exception:
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
        except Exception:
            pass

    # 2. Fallback to pubspec.yaml
    pubspec_path = os.path.join(PROJECT_ROOT, "pubspec.yaml")
    if os.path.exists(pubspec_path):
        try:
            with open(pubspec_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("name:"):
                        return line.split(":", 1)[1].strip()
        except Exception:
            pass
    return "rokctapp"

def resolve_sdk_path(sdk_name):
    # 1. Try resolving via .dart_tool/package_config.json (for pub-fetched SDKs)
    package_config_path = os.path.join(PROJECT_ROOT, ".dart_tool", "package_config.json")
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
                                return os.path.abspath(os.path.join(PROJECT_ROOT, ".dart_tool", root_uri))
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
        print(f"[-] Could not resolve path for SDK: {sdk_name}")
        return False

    manifest_path = os.path.join(sdk_path, "manifest.json")
    
    if not os.path.exists(manifest_path):
        print(f"[-] No manifest found for {sdk_name}")
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
    flavor_block = manifest.get("app_type", {}).get(current_app_type, {}) if current_app_type else {}

    version = manifest.get("version", "1.0.0")
    installs = manifest.get("installs", []) + flavor_block.get("installs", [])
    routes = manifest.get("routes", []) + flavor_block.get("routes", [])
    app_routes = manifest.get("app_routes", []) + flavor_block.get("app_routes", [])
    onboarding_slides = manifest.get("onboarding_slides", []) + flavor_block.get("onboarding_slides", [])
    embedded_widgets = manifest.get("embedded_widgets", []) + flavor_block.get("embedded_widgets", [])

    state = load_state()
    package_state = state["packages"].get(sdk_name, {"version": "0.0.0", "files": {}, "routes": []})
    package_state["version"] = version
    package_state["routes"] = routes
    package_state["app_routes"] = app_routes
    package_state["onboarding_slides"] = onboarding_slides
    package_state["embedded_widgets"] = embedded_widgets

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
    
    print(f"\n[*] Installing SDK: {sdk_name} (v{version})")
    
    # 1. Sync Files
    for entry in installs:
        from_rel = entry.get("from")
        to_rel = entry.get("to")
        if not from_rel or not to_rel:
            continue
            
        src_path = os.path.join(sdk_path, from_rel)
        dest_path = os.path.join(PROJECT_ROOT, to_rel)
        
        if not os.path.exists(src_path):
            print(f"  [-] Template source not found: {from_rel}")
            continue
            
        files_to_sync = []
        if os.path.isdir(src_path):
            for root, _, filenames in os.walk(src_path):
                for filename in filenames:
                    abs_src = os.path.join(root, filename)
                    rel_to_src = os.path.relpath(abs_src, src_path)
                    abs_dest = os.path.join(dest_path, rel_to_src)
                    rel_dest = os.path.relpath(abs_dest, PROJECT_ROOT).replace("\\", "/")
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
                    print(f"  [!] WARNING: {rel_dest} already exists and was not installed by this SDK. Skipping to avoid overwriting the app's own file - merge manually if you want the template's version.")
                    continue
                if current_dest_hash != last_known_hash:
                    # User modified the template file, skip and warn
                    print(f"  [!] WARNING: {rel_dest} has been modified by a developer. Skipping overwrite to prevent data loss. Please merge changes manually.")
                    continue

            os.makedirs(os.path.dirname(file_dest), exist_ok=True)
            
            # Copy binary files directly, text files with banner prepended
            is_text = file_dest.endswith((".dart", ".yaml", ".json", ".txt", ".md", ".gradle", ".properties"))
            
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
                        if trimmed.startswith("import ") or trimmed.startswith("export ") or trimmed.startswith("part ") or trimmed.startswith("part '") or trimmed.startswith("part \""):
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
            merged_db["tables"] = (db_config or {}).get("tables", []) + flavor_db.get("tables", [])
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

    # Extract and store AppConstants field overrides (home_sdk only, normally)
    constants_config = manifest.get("constants")
    flavor_constants = flavor_block.get("constants")
    if constants_config or flavor_constants:
        merged_constants = dict(constants_config or {})
        if flavor_constants:
            merged_constants["import"] = flavor_constants.get("import", merged_constants.get("import"))
            merged_constants["overrides"] = dict((constants_config or {}).get("overrides", {}))
            merged_constants["overrides"].update(flavor_constants.get("overrides", {}))
        package_state["constants"] = merged_constants

    # Extract and store layout integrations if present
    integrations_config = manifest.get("integrations", []) + flavor_block.get("integrations", [])
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
    update_layout_integrations()
    update_app_routes()
    update_onboarding_slides()
    update_embedded_widgets()
    update_brand_hook()
    update_wiring_imports()
    return True

def update_router_table():
    if not os.path.exists(ROUTER_FILE):
        print(f"[-] router file not found: {ROUTER_FILE}")
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
        
    # Inject imports
    import_block = "\n".join(sorted(list(all_imports)))
    import_replacement = f"// @generated-imports-start\n{import_block}\n// @generated-imports-end"
    content = re.sub(
        r"// @generated-imports-start.*?// @generated-imports-end",
        import_replacement,
        content,
        flags=re.DOTALL
    )
    
    # Inject routes
    routes_block = "\n".join(all_routes)
    routes_replacement = f"// @generated-routes-start\n{routes_block}\n// @generated-routes-end"
    content = re.sub(
        r"// @generated-routes-start.*?// @generated-routes-end",
        routes_replacement,
        content,
        flags=re.DOTALL
    )
    
    with open(ROUTER_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print("[*] Successfully updated app_router.dart with generated routes and imports.")

def update_main_dependencies():
    if not os.path.exists(MAIN_FILE):
        print(f"[-] main.dart file not found: {MAIN_FILE}")
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
        sdk_registrations.append(f"  {class_prefix}Dependencies.register(GetIt.instance);")
        
    with open(MAIN_FILE, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Inject imports
    imports_block = "\n".join(sdk_imports)
    imports_replacement = f"// @generated-sdk-imports-start\n{imports_block}\n// @generated-sdk-imports-end"
    content = re.sub(
        r"// @generated-sdk-imports-start.*?// @generated-sdk-imports-end",
        imports_replacement,
        content,
        flags=re.DOTALL
    )
    
    # Inject DI registrations
    di_block = "\n".join(sdk_registrations)
    di_replacement = f"// @generated-sdk-di-start\n{di_block}\n// @generated-sdk-di-end"
    content = re.sub(
        r"// @generated-sdk-di-start.*?// @generated-sdk-di-end",
        di_replacement,
        content,
        flags=re.DOTALL
    )
    
    with open(MAIN_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print("[*] Successfully updated main.dart with generated SDK imports and DI registrations.")

def _clean_pkg_name(pkg):
    if pkg.endswith("_sdks"):
        return pkg[:-5]
    if pkg.endswith("_sdk"):
        return pkg[:-4]
    return pkg

def update_database_registration():
    if not os.path.exists(DB_FILE):
        print(f"[-] app_database.dart file not found: {DB_FILE}")
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

        tables = db_config.get("tables", [])
        for tbl in tables:
            t_class = tbl.get("class")
            t_imp = tbl.get("import")
            if t_class:
                all_tables.append(f"    {t_class},")
            if t_imp and t_imp not in copied:
                uri = t_imp
                pkg, _, rel = uri[len("package:"):].partition("/")
                clean = _clean_pkg_name(pkg)
                src = os.path.join(PROJECT_ROOT, ".rokct", "cache", clean, "lib", *rel.split("/"))
                if not os.path.exists(src):
                    print(f"  [!] table import source missing, skipping: {uri}")
                    continue
                dest_name = f"{pkg}__{os.path.basename(rel)}"
                dest = os.path.join(INJECTED_DB_DIR, dest_name)
                with open(src, "r", encoding="utf-8-sig") as sf:
                    content = sf.read()
                with open(dest, "w", encoding="utf-8", newline="\n") as df:
                    df.write(
                        f"// Copied at compose time from {uri} by "
                        f"sdk_installer_base.py's update_database_registration() -\n"
                        f"// drift only understands table classes inside its own package.\n" + content
                    )
                copied[uri] = f"injected/{dest_name}"
            if t_imp in copied:
                rel_imports.add(f"import '{copied[t_imp]}';")

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
                pass

    with open(DB_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Inject imports
    imports_block = "\n".join(sorted(rel_imports))
    imports_replacement = f"// @sdk-database-imports-start\n{imports_block}\n// @sdk-database-imports-end"
    content = re.sub(
        r"// @sdk-database-imports-start.*?// @sdk-database-imports-end",
        imports_replacement.replace("\\", "\\\\"),
        content,
        flags=re.DOTALL
    )

    # 2. Inject tables
    tables_block = "\n".join(all_tables)
    tables_replacement = f"    // @sdk-database-tables-start\n{tables_block}\n    // @sdk-database-tables-end"
    content = re.sub(
        r"    // @sdk-database-tables-start.*?    // @sdk-database-tables-end",
        tables_replacement.replace("\\", "\\\\"),
        content,
        flags=re.DOTALL
    )

    # 3. Inject schemaVersion dynamically
    content = re.sub(
        r"int get schemaVersion => \d+;",
        f"int get schemaVersion => {max_version};",
        content
    )

    # 4. Inject migrations
    migrations_block = "\n".join(migration_steps)
    migrations_replacement = f"        // @sdk-database-migrations-start\n{migrations_block}\n        // @sdk-database-migrations-end"
    content = re.sub(
        r"        // @sdk-database-migrations-start.*?        // @sdk-database-migrations-end",
        migrations_replacement.replace("\\", "\\\\"),
        content,
        flags=re.DOTALL
    )

    with open(DB_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[*] Successfully updated app_database.dart. Set schemaVersion to {max_version}.")

def update_tr_keys_registration():
    if not os.path.exists(TRKEYS_FILE):
        print(f"[-] tr_keys.dart file not found: {TRKEYS_FILE}")
        return

    state = load_state()
    key_lines = []
    seen = {}
    for pkg_name, pkg_data in sorted(state.get("packages", {}).items()):
        tr_keys = pkg_data.get("tr_keys")
        if not tr_keys:
            continue
        for field, value in tr_keys.items():
            if field in seen and seen[field] != pkg_name:
                print(f"  [!] tr_keys collision: '{field}' declared by both '{seen[field]}' and '{pkg_name}' - keeping first")
                continue
            seen[field] = pkg_name
            escaped = value.replace("\\", "\\\\").replace("'", "\\'")
            key_lines.append(f"  static const String {field} = '{escaped}';")

    with open(TRKEYS_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    block = "\n".join(key_lines)
    replacement = f"// @sdk-tr-keys-start\n{block}\n  // @sdk-tr-keys-end"
    content = re.sub(
        r"// @sdk-tr-keys-start.*?  // @sdk-tr-keys-end",
        replacement.replace("\\", "\\\\"),
        content,
        flags=re.DOTALL
    )

    with open(TRKEYS_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[*] Successfully updated tr_keys.dart with {len(key_lines)} SDK-owned key(s).")

def update_asset_keys_registration():
    """Inject SDK-declared AppAssets constants into base's app_assets.dart
    (exact mirror of update_tr_keys_registration): each installed SDK's
    manifest may carry `asset_keys` mapping constant name -> asset key
    string; the block between // @sdk-asset-keys-start/end is regenerated
    from all installed SDKs, first declaration wins on collisions."""
    if not os.path.exists(ASSETKEYS_FILE):
        print(f"[-] app_assets.dart file not found: {ASSETKEYS_FILE}")
        return

    state = load_state()
    key_lines = []
    seen = {}
    for pkg_name, pkg_data in sorted(state.get("packages", {}).items()):
        asset_keys = pkg_data.get("asset_keys")
        if not asset_keys:
            continue
        for field, value in asset_keys.items():
            if field in seen and seen[field] != pkg_name:
                print(f"  [!] asset_keys collision: '{field}' declared by both '{seen[field]}' and '{pkg_name}' - keeping first")
                continue
            seen[field] = pkg_name
            escaped = value.replace("\\", "\\\\").replace("'", "\\'")
            key_lines.append(f"  static const String {field} = '{escaped}';")

    with open(ASSETKEYS_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    block = "\n".join(key_lines)
    replacement = f"// @sdk-asset-keys-start\n{block}\n  // @sdk-asset-keys-end"
    content = re.sub(
        r"// @sdk-asset-keys-start.*?  // @sdk-asset-keys-end",
        replacement.replace("\\", "\\\\"),
        content,
        flags=re.DOTALL
    )

    with open(ASSETKEYS_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[*] Successfully updated app_assets.dart with {len(key_lines)} SDK-owned asset key(s).")


APP_ASSETS_BEGIN = "    # BEGIN sdk-app-assets (generated by SDK installer - do not edit by hand)"
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
        print(f"[-] app pubspec.yaml not found: {pubspec_path}")
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
            print("  [!] app pubspec.yaml has no `assets:` line - add one under "
                  "`flutter:` so SDK-declared assets can be injected.")
            return
        new_lines = (
            lines[: assets_idx + 1]
            + [APP_ASSETS_BEGIN]
            + generated
            + [APP_ASSETS_END]
            + lines[assets_idx + 1:]
        )

    new_content = "\n".join(new_lines) + "\n"
    with open(pubspec_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"[*] Successfully updated app pubspec.yaml with {len(entries)} SDK-declared asset entr(y/ies).")


def update_constants_overrides():
    if not os.path.exists(CONSTANTS_FILE):
        print(f"[-] app_constants.dart file not found: {CONSTANTS_FILE}")
        return

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

    with open(CONSTANTS_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    for imp in sorted(imports):
        if imp not in content:
            content = content.replace(
                "import 'package:base_sdk/src/services/enums.dart';",
                f"import 'package:base_sdk/src/services/enums.dart';\n{imp}",
                1,
            )

    applied = 0
    for field, expr in overrides.items():
        pattern = r"(static\s+(?:const\s+)?\w+(?:<[^>]*>)?\s+%s\s*=\s*).*?;" % re.escape(field)
        new_content, n = re.subn(pattern, r"\1%s;" % expr, content, count=1)
        if n:
            content = new_content
            applied += 1
        else:
            print(f"  [!] constants override: field '{field}' not found in AppConstants, skipping")

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
                continue
            
            target_abs = os.path.join(PROJECT_ROOT, target_rel)
            if not os.path.exists(target_abs):
                continue
                
            # Read current file text (either original or accumulated in loop)
            content = file_changes.get(target_abs)
            if content is None:
                with open(target_abs, "r", encoding="utf-8") as f:
                    content = f.read()
            
            # Prevent double injection: Check if replacement is already in file
            if replacement in content:
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
                print(f"  [!] app_routes: {method} already provided by another SDK, skipping {pkg_name}'s")
                continue
            seen_methods.add(method)
            all_methods.append(
                f"  @override\n  Future<Object?> {method}({params}) => {body}\n"
            )

    with open(MAIN_FILE, "r", encoding="utf-8") as f:
        content = f.read()

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
    if not os.path.exists(ONBOARDING_ROUTES_FILE):
        return

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
                print(f"  [!] onboarding_slides: '{slide_id}' already provided by {seen_ids[slide_id]}, skipping {pkg_name}'s")
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
            print(f"  [!] onboarding_slides: order {order} declared by {listing} - keeping all, tie-broken by id; declare distinct orders to control the sequence")

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
        print(f"[*] Injected {len(slides)} onboarding slide(s) into onboarding_route_pages.dart")

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
                print(f"  [!] WARNING: embedded_widgets conflict: '{method}' is declared by both '{seen_methods[method]}' and '{pkg_name}' - keeping '{seen_methods[method]}'s implementation and skipping '{pkg_name}'s. Remove one manifest declaration to resolve this.")
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
        print("  [i] main.dart has no @generated-embeddedwidgets markers (older host template) - skipping embedded-widget injection")
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
        print(f"[*] Injected {len(all_methods)} EmbeddedWidgets method(s) into main.dart")

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
            "a \"brand_hook\" in their manifest, but at most ONE may own the app's brand "
            "- the hook runs exactly once before the first frame. Remove the "
            "\"brand_hook\" key from every manifest except the one true brand owner "
            "(normally the home SDK) and recompose."
        )

    body_lines = []
    for pkg_name, hook in declared.items():
        for line in hook["body"].splitlines():
            body_lines.append(f"  {line}" if line.strip() else "")

    with open(MAIN_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if "// @generated-brandhook-start" not in content:
        print("  [i] main.dart has no @generated-brandhook markers (older host template) - skipping brand-hook injection")
        return

    hook_block = "\n".join(body_lines)
    replacement = f"  // @generated-brandhook-start\n{hook_block}\n  // @generated-brandhook-end"
    new_content = re.sub(
        r"  // @generated-brandhook-start.*?// @generated-brandhook-end",
        lambda _: replacement,
        content,
        flags=re.DOTALL,
    )

    if new_content != content:
        with open(MAIN_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"[*] Injected brand hook from {', '.join(sorted(declared)) or 'no SDK'} into main.dart")

def update_wiring_imports():
    """Regenerates main.dart's @generated-wiring-imports block (directly
    below the @generated-sdk-imports block) from the optional "imports"
    lists of every installed SDK's app_routes, embedded_widgets and
    brand_hook declarations. Each entry ships FULL import lines (e.g.
    "import 'package:${package}/presentation/routes/app_router.dart';",
    ${package} substituted here) so the symbols its injected body references
    resolve in a fully generated main.dart without hand-written imports.
    Collected from full state, deduped and sorted — a removed SDK's imports
    vanish on the next regeneration, same as every other marker block.

    Older host main.dart files predating the marker get a printed notice and
    no changes; this only rewrites the marker block.
    """
    if not os.path.exists(MAIN_FILE):
        return

    state = load_state()
    package_name = get_project_package_name()
    all_imports = set()
    for pkg_name, pkg_data in state.get("packages", {}).items():
        wiring_entries = list(pkg_data.get("app_routes", []))
        wiring_entries += pkg_data.get("embedded_widgets", [])
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
        print("  [i] main.dart has no @generated-wiring-imports markers (older host template) - skipping wiring-import injection")
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
    update_layout_integrations()
    update_app_routes()
    update_onboarding_slides()
    update_embedded_widgets()
    update_brand_hook()
    update_wiring_imports()
