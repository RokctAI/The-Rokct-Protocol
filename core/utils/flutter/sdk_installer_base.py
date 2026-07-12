import os
import json
import shutil
import hashlib
import re
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(PROJECT_ROOT, ".rokct", "install_state.json")
ROUTER_FILE = os.path.join(PROJECT_ROOT, "lib", "core", "presentation", "routes", "app_router.dart")
MAIN_FILE = os.path.join(PROJECT_ROOT, "lib", "main.dart")
DB_FILE = os.path.join(PROJECT_ROOT, "sdk", "core_sdk", "lib", "src", "infrastructure", "utils", "app_database.dart")

def file_hash(path):
    if not os.path.exists(path):
        return None
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

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
        
    version = manifest.get("version", "1.0.0")
    installs = manifest.get("installs", [])
    routes = manifest.get("routes", [])
    
    state = load_state()
    package_state = state["packages"].get(sdk_name, {"version": "0.0.0", "files": {}, "routes": []})
    package_state["version"] = version
    package_state["routes"] = routes
    
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
                if last_known_hash and current_dest_hash != last_known_hash:
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
            
    # Extract and store database definitions if present
    db_config = manifest.get("database")
    if db_config:
        package_state["database"] = db_config

    # Extract and store layout integrations if present
    integrations_config = manifest.get("integrations")
    if integrations_config:
        package_state["integrations"] = integrations_config

    state["packages"][sdk_name] = package_state
    save_state(state)
    
    # 2. Update Routing, Main DI & Database Registrations
    update_router_table()
    update_main_dependencies()
    update_database_registration()
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
    
    # Generate imports and register statements for all active packages
    for pkg_name in sorted(state.get("packages", {}).keys()):
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

def update_database_registration():
    if not os.path.exists(DB_FILE):
        print(f"[-] app_database.dart file not found: {DB_FILE}")
        return

    state = load_state()
    all_imports = set()
    all_tables = []
    all_datacolumns = []
    migration_steps = []
    max_version = 12

    # Loop through packages and aggregate definitions to avoid overriding
    for pkg_name, pkg_data in state.get("packages", {}).items():
        db_config = pkg_data.get("database")
        if not db_config:
            continue

        tables = db_config.get("tables", [])
        for tbl in tables:
            t_class = tbl.get("class")
            t_imp = tbl.get("import")
            t_entity = tbl.get("entity")
            if t_class:
                all_tables.append(f"    {t_class},")
            if t_imp:
                all_imports.add(f"import '{t_imp}';")
            if t_entity:
                all_datacolumns.append(f"    if (row is {t_entity}) return row.data;")

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
    imports_block = "\n".join(sorted(list(all_imports)))
    imports_replacement = f"// @generated-database-imports-start\n{imports_block}\n// @generated-database-imports-end"
    content = re.sub(
        r"// @generated-database-imports-start.*?// @generated-database-imports-end",
        imports_replacement,
        content,
        flags=re.DOTALL
    )

    # 2. Inject tables
    tables_block = "\n".join(all_tables)
    tables_replacement = f"    // @generated-database-tables-start\n{tables_block}\n    // @generated-database-tables-end"
    content = re.sub(
        r"    // @generated-database-tables-start.*?    // @generated-database-tables-end",
        tables_replacement,
        content,
        flags=re.DOTALL
    )

    # 3. Inject data columns
    datacolumn_block = "\n".join(all_datacolumns)
    datacolumn_replacement = f"    // @generated-database-datacolumn-start\n{datacolumn_block}\n    // @generated-database-datacolumn-end"
    content = re.sub(
        r"    // @generated-database-datacolumn-start.*?    // @generated-database-datacolumn-end",
        datacolumn_replacement,
        content,
        flags=re.DOTALL
    )

    # 4. Inject schemaVersion dynamically
    content = re.sub(
        r"int get schemaVersion => \d+;",
        f"int get schemaVersion => {max_version};",
        content
    )

    # 5. Inject migrations
    migrations_block = "\n".join(migration_steps)
    migrations_replacement = f"        // @generated-database-migrations-start\n{migrations_block}\n        // @generated-database-migrations-end"
    content = re.sub(
        r"        // @generated-database-migrations-start.*?        // @generated-database-migrations-end",
        migrations_replacement,
        content,
        flags=re.DOTALL
    )

    with open(DB_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[*] Successfully updated app_database.dart. Set schemaVersion to {max_version}.")

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

if __name__ == "__main__":
    update_router_table()
    update_main_dependencies()
    update_database_registration()
    update_layout_integrations()
