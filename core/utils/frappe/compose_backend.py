import os
import sys
import shutil
import json
import re

PROJECT_ROOT = os.getcwd()

COMPILED_DOCTYPES = {}  # maps doctype_name -> module_name


def load_composer_config():
    composer_path = os.path.join(PROJECT_ROOT, "composer.json")
    if not os.path.exists(composer_path):
        print(f"[-] No composer.json found in {PROJECT_ROOT}. Skipping.")
        sys.exit(0)
    with open(composer_path, "r", encoding="utf-8") as f:
        return json.load(f)

def find_target_app_dir(config):
    # Try to resolve app name from configuration or folder name
    app_name = config.get("name", "").replace("_app", "")
    if not app_name:
        app_name = os.path.basename(PROJECT_ROOT)
    
    # Frappe apps are nested as apps/app_name/app_name
    target_path = os.path.join(PROJECT_ROOT, "apps", app_name, app_name)
    if not os.path.exists(target_path):
        # Fallback to local package directory in case of simple workspace
        target_path = os.path.join(PROJECT_ROOT, app_name)
    
    if not os.path.exists(target_path):
        print(f"[!] Target app package directory not found for: {app_name}. Tried: {target_path}")
        sys.exit(1)
        
    return app_name, target_path

def compose_module(module_config, target_app_path, app_name):
    module_name = module_config["name"]
    raw_path = module_config.get("path")
    
    if not raw_path:
        print(f"[-] No path defined for module: {module_name}. Skipping.")
        return None
        
    src_sdk_path = os.path.abspath(os.path.join(PROJECT_ROOT, raw_path))
    manifest_path = os.path.join(src_sdk_path, "manifest.json")
    
    if not os.path.exists(manifest_path):
        print(f"[-] No manifest.json found for module {module_name} at {src_sdk_path}. Skipping.")
        return None
        
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    dest_module_path = os.path.join(target_app_path, module_name)
    if os.path.exists(dest_module_path):
        shutil.rmtree(dest_module_path)
    os.makedirs(dest_module_path, exist_ok=True)
    
    # 1. Copy DocTypes
    src_doctype = os.path.join(src_sdk_path, "doctype")
    dest_doctype = os.path.join(dest_module_path, "doctype")
    if os.path.isdir(src_doctype):
        os.makedirs(dest_doctype, exist_ok=True)
        for dt in os.listdir(src_doctype):
            src_dt_path = os.path.join(src_doctype, dt)
            dest_dt_path = os.path.join(dest_doctype, dt)
            if os.path.isdir(src_dt_path):
                if dt in COMPILED_DOCTYPES:
                    raise ValueError(f"CRITICAL ERROR: Duplicate DocType '{dt}' detected! Already compiled by module '{COMPILED_DOCTYPES[dt]}'. Failing build.")
                COMPILED_DOCTYPES[dt] = module_name
                
                if os.path.exists(dest_dt_path):
                    shutil.rmtree(dest_dt_path)
                shutil.copytree(src_dt_path, dest_dt_path)
                # Overwrite the DocType module property to match composition target
                json_file = os.path.join(dest_dt_path, f"{dt}.json")
                if os.path.exists(json_file):
                    try:
                        with open(json_file, "r", encoding="utf-8") as jf:
                            data = json.load(jf)
                        data["module"] = manifest.get("name", module_name)
                        with open(json_file, "w", encoding="utf-8") as jf:
                            json.dump(data, jf, indent=2)
                        print(f"[+] Compiled DocType: {dt} -> {manifest.get('name', module_name)} (Module injected from manifest)")
                    except Exception as je:
                        print(f"[!] Warning: Failed to inject module into {dt}.json: {je}")
                else:
                    print(f"[+] Copied DocType: {dt} -> {module_name}")
                
    # 2. Copy Source Code Files (api.py, tasks.py, etc.)
    src_code = os.path.join(src_sdk_path, "src")
    if os.path.isdir(src_code):
        for f in os.listdir(src_code):
            src_file_path = os.path.join(src_code, f)
            
            # Special redirects for global folders
            if f == "www":
                dest_www = os.path.join(target_app_path, "www")
                os.makedirs(dest_www, exist_ok=True)
                for item in os.listdir(src_file_path):
                    s_file = os.path.join(src_file_path, item)
                    d_file = os.path.join(dest_www, item)
                    if os.path.exists(d_file):
                        raise ValueError(f"CRITICAL ERROR: Duplicate global www file '{item}' detected! (Attempted by: '{module_name}'). Failing build.")
                    if item.endswith((".py", ".js", ".html", ".json")):
                        with open(s_file, "r", encoding="utf-8") as sf:
                            content = sf.read()
                        content = content.replace("{app_name}", app_name)
                        with open(d_file, "w", encoding="utf-8") as df:
                            df.write(content)
                    else:
                        shutil.copy2(s_file, d_file)
                print(f"[+] Merged global www files from: {module_name}")
                continue
                
            if f == "patches":
                dest_patches = os.path.join(target_app_path, "patches")
                os.makedirs(dest_patches, exist_ok=True)
                # Ensure __init__.py exists in patches
                with open(os.path.join(dest_patches, "__init__.py"), "w", encoding="utf-8") as init_f:
                    init_f.write("")
                for item in os.listdir(src_file_path):
                    if item.endswith(".py") and item != "__init__.py":
                        s_file = os.path.join(src_file_path, item)
                        d_file = os.path.join(dest_patches, item)
                        if os.path.exists(d_file):
                            raise ValueError(f"CRITICAL ERROR: Duplicate global patch file '{item}' detected! (Attempted by: '{module_name}'). Failing build.")
                        with open(s_file, "r", encoding="utf-8") as sf:
                            content = sf.read()
                        content = content.replace("{app_name}", app_name)
                        with open(d_file, "w", encoding="utf-8") as df:
                            df.write(content)
                        patch_name = item[:-3]
                        # Register in patches.txt
                        patches_txt_path = os.path.join(target_app_path, "patches.txt")
                        existing_patches = []
                        if os.path.exists(patches_txt_path):
                            with open(patches_txt_path, "r", encoding="utf-8") as pf:
                                existing_patches = [line.strip() for line in pf.readlines() if line.strip()]
                        full_patch_path = f"{app_name}.patches.{patch_name}"
                        if full_patch_path not in existing_patches:
                            with open(patches_txt_path, "a", encoding="utf-8") as pf:
                                pf.write(f"{full_patch_path}\n")
                            print(f"[+] Registered patch: '{full_patch_path}' -> patches.txt")
                print(f"[+] Merged global patches from: {module_name}")
                continue

            dest_file_path = os.path.join(dest_module_path, f)
            if os.path.exists(dest_file_path):
                raise ValueError(f"CRITICAL ERROR: Duplicate source file/folder '{f}' in module '{module_name}'! Failing build.")
            if os.path.isfile(src_file_path):
                # Copy file and replace {app_name} placeholders dynamically
                if src_file_path.endswith((".py", ".js", ".html", ".json")):
                    with open(src_file_path, "r", encoding="utf-8") as sf:
                        content = sf.read()
                    content = content.replace("{app_name}", app_name)
                    with open(dest_file_path, "w", encoding="utf-8") as df:
                        df.write(content)
                else:
                    shutil.copy2(src_file_path, dest_file_path)
                print(f"[+] Copied Source File: {f} -> {module_name}")
            elif os.path.isdir(src_file_path):
                if os.path.exists(dest_file_path):
                    shutil.rmtree(dest_file_path)
                # Copy tree and compile placeholders for text files
                def copy_and_resolve(src, dst):
                    os.makedirs(dst, exist_ok=True)
                    for item in os.listdir(src):
                        s = os.path.join(src, item)
                        d = os.path.join(dst, item)
                        if os.path.isdir(s):
                            copy_and_resolve(s, d)
                        else:
                            if s.endswith((".py", ".js", ".html", ".json")):
                                with open(s, "r", encoding="utf-8") as sf:
                                    content = sf.read()
                                content = content.replace("{app_name}", app_name)
                                with open(d, "w", encoding="utf-8") as df:
                                    df.write(content)
                            else:
                                shutil.copy2(s, d)
                copy_and_resolve(src_file_path, dest_file_path)
                print(f"[+] Copied Source Directory: {f} -> {module_name}")

    # 3. Create Frappe Module Package registration markers
    with open(os.path.join(dest_module_path, "__init__.py"), "w", encoding="utf-8") as f:
        f.write("# Generated by Rokct Backend Composer\n")
        
    # Append to root modules.txt of the app shell if not present
    root_modules_path = os.path.join(target_app_path, "modules.txt")
    existing_modules = []
    if os.path.exists(root_modules_path):
        with open(root_modules_path, "r", encoding="utf-8") as f:
            existing_modules = [line.strip() for line in f.readlines() if line.strip()]
            
    if module_name not in existing_modules:
        with open(root_modules_path, "a", encoding="utf-8") as f:
            f.write(f"{module_name}\n")
        print(f"[+] Injected module registration: '{module_name}' -> root modules.txt")
        
    print(f"[+] Module {module_name} registration files written.")
    return manifest

def merge_hooks(target_app_path, app_name, compiled_manifests):
    hooks_file = os.path.join(target_app_path, "hooks.py")
    if not os.path.exists(hooks_file):
        print(f"[-] No hooks.py found in {target_app_path}. Creating a default one.")
        with open(hooks_file, "w", encoding="utf-8") as hf:
            hf.write(f"app_name = '{app_name}'\n")

    # Read original content
    with open(hooks_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Strip any previously appended blocks to ensure idempotent builds
    split_marker = "# --- BEG OF DYNAMIC SDK HOOKS ---"
    if split_marker in content:
        content = content.split(split_marker)[0].strip()

    append_blocks = []
    
    for module_name, manifest in compiled_manifests.items():
        hooks = manifest.get("hooks", {})
        # Dynamically inject the app_name into placeholders
        hooks_str = json.dumps(hooks)
        hooks_str = hooks_str.replace("{app_name}", app_name)
        hooks = json.loads(hooks_str)
        if not hooks:
            continue
            
        append_blocks.append(f"\n# --- Module: {module_name} ---")
        
        # 1. Merge scheduler events
        scheduler_events = hooks.get("scheduler_events", {})
        for event_type, tasks in scheduler_events.items():
            tasks_str = ", ".join([f"'{t}'" for t in tasks])
            append_blocks.append(f"scheduler_events = globals().get('scheduler_events', {{}})")
            append_blocks.append(f"scheduler_events.setdefault('{event_type}', []).extend([{tasks_str}])")
            
        # 2. Merge override doctype class
        overrides = hooks.get("override_doctype_class", {})
        for doc_type, class_path in overrides.items():
            append_blocks.append(f"override_doctype_class = globals().get('override_doctype_class', {{}})")
            append_blocks.append(f"override_doctype_class['{doc_type}'] = '{class_path}'")

        # 3. Merge whitelisted methods
        whitelisted = hooks.get("whitelisted_methods", {})
        if whitelisted:
            append_blocks.append(f"whitelisted_methods = globals().get('whitelisted_methods', {{}})")
            for api_key, api_val in whitelisted.items():
                append_blocks.append(f"whitelisted_methods['{api_key}'] = '{api_val}'")
                
        # 4. Merge doc events
        events = hooks.get("doc_events", {})
        if events:
            append_blocks.append(f"doc_events = globals().get('doc_events', {{}})")
            for doc_type, evt_dict in events.items():
                append_blocks.append(f"doc_events.setdefault('{doc_type}', {{}})")
                for evt, handler in evt_dict.items():
                    append_blocks.append(f"doc_events['{doc_type}']['{evt}'] = '{handler}'")
                    
        # 5. Merge fixtures
        fixs = hooks.get("fixtures", [])
        if fixs:
            append_blocks.append(f"fixtures = globals().get('fixtures', [])")
            for f in fixs:
                append_blocks.append(f"fixtures.append({repr(f)})")
                
        # 6. Merge auth hooks
        auths = hooks.get("auth_hooks", [])
        if auths:
            append_blocks.append(f"auth_hooks = globals().get('auth_hooks', [])")
            for a in auths:
                append_blocks.append(f"if '{a}' not in auth_hooks: auth_hooks.append('{a}')")
                
        # 7. Merge before_uninstall hooks
        before_uninstalls = hooks.get("before_uninstall", [])
        if before_uninstalls:
            append_blocks.append(f"before_uninstall = globals().get('before_uninstall', [])")
            for bu in before_uninstalls:
                append_blocks.append(f"if '{bu}' not in before_uninstall: before_uninstall.append('{bu}')")

    if append_blocks:
        new_content = content + "\n\n" + split_marker + "\n" + "\n".join(append_blocks) + "\n# --- END OF DYNAMIC SDK HOOKS ---\n"
        with open(hooks_file, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("[+] Merged dynamic Hooks successfully into hooks.py")


def merge_dependencies(project_root, compiled_manifests):
    # Collect all dependencies from manifests
    all_deps = set()
    for manifest in compiled_manifests.values():
        deps = manifest.get("dependencies", [])
        for d in deps:
            all_deps.add(d.strip())
            
    if not all_deps:
        return
        
    # 1. Update requirements.txt
    req_file = os.path.join(project_root, "requirements.txt")
    existing_reqs = set()
    if os.path.exists(req_file):
        with open(req_file, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    existing_reqs.add(stripped.split("=")[0].split(">")[0].split("<")[0].strip())
                    
    new_reqs_to_add = [d for d in all_deps if d.split("=")[0].split(">")[0].split("<")[0].strip() not in existing_reqs]
    if new_reqs_to_add:
        with open(req_file, "a", encoding="utf-8") as f:
            # Add a newline if file doesn't end with one
            f.write("\n# Composed SDK Dependencies\n")
            for req in new_reqs_to_add:
                f.write(f"{req}\n")
        print(f"[+] Injected Python requirements into requirements.txt: {new_reqs_to_add}")
        
    # 2. Update pyproject.toml
    toml_file = os.path.join(project_root, "pyproject.toml")
    if os.path.exists(toml_file):
        with open(toml_file, "r", encoding="utf-8") as f:
            toml_content = f.read()
            
        # Locate the dependencies array block
        match = re.search(r"dependencies\s*=\s*\[([^\]]*)\]", toml_content)
        if match:
            deps_block = match.group(1)
            # Parse existing TOML dependency strings
            existing_toml_deps = [d.replace('"', '').replace("'", "").strip() for d in deps_block.split(",") if d.strip()]
            
            new_toml_deps_to_add = [d for d in all_deps if d not in existing_toml_deps]
            if new_toml_deps_to_add:
                updated_deps_list = existing_toml_deps + new_toml_deps_to_add
                toml_deps_str = ",\n    ".join([f'"{d}"' for d in updated_deps_list])
                new_dependencies_field = f"dependencies = [\n    {toml_deps_str}\n]"
                toml_content = toml_content.replace(match.group(0), new_dependencies_field)
                with open(toml_file, "w", encoding="utf-8") as f:
                    f.write(toml_content)
                print(f"[+] Injected dependencies into pyproject.toml: {new_toml_deps_to_add}")

def main():
    print("[*] Starting Frappe App Backend Composition...")
    
    # Clean and restore target app shell workspace using Git
    import subprocess
    print("[*] Cleaning and restoring target app shell workspace using Git...")
    try:
        subprocess.run(["git", "restore", "."], check=True, capture_output=True)
        subprocess.run(["git", "clean", "-fd"], check=True, capture_output=True)
        print("[+] Workspace cleaned successfully.")
    except Exception as e:
        print(f"[!] Warning: Git clean/restore failed (perhaps not a git repo or git not in PATH): {e}")

    config = load_composer_config()
    app_name, target_app_path = find_target_app_dir(config)
    
    modules = config.get("modules", [])
    compiled_manifests = {}
    
    for m in modules:
        if m.get("enabled", False):
            print(f"\n[*] Pouring module: {m['name']}...")
            manifest = compose_module(m, target_app_path, app_name)
            if manifest:
                compiled_manifests[m['name']] = manifest
                
    if compiled_manifests:
        merge_hooks(target_app_path, app_name, compiled_manifests)
        merge_dependencies(PROJECT_ROOT, compiled_manifests)
        
    print("\n[+] Frappe backend composition complete.")

if __name__ == "__main__":
    main()
