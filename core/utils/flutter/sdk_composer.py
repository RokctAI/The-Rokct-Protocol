import os
import sys
import subprocess
import json
import shutil

PROJECT_ROOT = os.getcwd()

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
            return "/".join(parts[idx+1:])
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return normalized

def check_git_availability(git_url):
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--exit-code", "-h", git_url, "HEAD"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False

def resolve_and_cache_sdks(sdks):
    cache_base = os.path.join(PROJECT_ROOT, ".rokct", "cache")
    os.makedirs(cache_base, exist_ok=True)
    
    git_groups = {}
    local_sdks = []
    
    for sdk in sdks:
        if not isinstance(sdk, dict):
            local_sdks.append({
                "name": sdk,
                "path": f"../SDKs/{clean_sdk_name(sdk)}/dart"
            })
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
        
        ref = group_sdks[0].get("ref", "main")
        print(f"[*] Fetching repository {git_url} into {temp_repo_dir}...")
        try:
            if os.path.exists(temp_repo_dir):
                shutil.rmtree(temp_repo_dir)
            subprocess.run(["git", "clone", "-b", ref, "--depth", "1", git_url, temp_repo_dir], check=True)
        except Exception as e:
            print(f"[!] Failed to clone {git_url}: {e}")
            sys.exit(1)
            
        # Extract each SDK
        for sdk in group_sdks:
            sdk_name = sdk["name"]
            clean_name = clean_sdk_name(sdk_name)
            target_dir = os.path.join(cache_base, clean_name)
            
            local_path = sdk.get("path", "")
            subpath = get_subpath_in_repo(local_path, repo_name)
            src_dir = os.path.join(temp_repo_dir, *subpath.split("/"))
            
            if os.path.exists(src_dir):
                print(f"[+] Extracting {sdk_name} from {subpath} to {target_dir}...")
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir)
                shutil.copytree(src_dir, target_dir)
            else:
                print(f"[!] Error: Path {subpath} not found in cloned repository {git_url}")
                
        # Clean up temp repo folder
        if os.path.exists(temp_repo_dir):
            shutil.rmtree(temp_repo_dir)
            
    # Process Local SDKs
    for sdk in local_sdks:
        sdk_name = sdk["name"]
        clean_name = clean_sdk_name(sdk_name)
        target_dir = os.path.join(cache_base, clean_name)
        
        local_path = sdk.get("path")
        if local_path:
            src_dir = os.path.abspath(os.path.join(PROJECT_ROOT, local_path))
            if os.path.exists(src_dir):
                print(f"[+] Copying local {sdk_name} from {local_path} to {target_dir}...")
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir)
                shutil.copytree(src_dir, target_dir)
            else:
                print(f"[-] Local path {local_path} for {sdk_name} does not exist. Skipping.")

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
        return
        
    print(f"\n[*] Executing Installer for {sdk_name}...")
    try:
        result = subprocess.run(
            [sys.executable, installer_script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True
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
        print(f"[!] Installer for {sdk_name} failed. Error log written to: .rokct/agent/logs/{sdk_name}_install_error.log")
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
        
        new_lines = lines[:dependencies_start + 1]
        
        i = dependencies_start + 1
        while i < len(lines):
            line = lines[i]
            if line.startswith(" "):
                stripped = line.strip()
                if stripped and stripped.endswith("_sdk:"):
                    i += 1
                    while i < len(lines) and (lines[i].startswith(" ") or lines[i].strip() == ""):
                        i += 1
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
                pubspec_path_val = os.path.relpath(resolved_path, PROJECT_ROOT).replace("\\", "/")
            except ValueError:
                pass
            
            if os.path.exists(os.path.join(resolved_path, "pubspec.yaml")):
                sdk_deps.append(f"  {sdk_name}:\n    path: {pubspec_path_val}\n")
            else:
                print(f"  [-] Skipping {sdk_name} as pubspec.yaml is missing at {resolved_path}.")
        
        if sdk_deps:
            new_lines.insert(dependencies_start + 1, "".join(sdk_deps))
            
        with open(pubspec_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"[*] Updated SDK dependencies in pubspec.yaml")
    except Exception as e:
        print(f"[!] Error updating pubspec.yaml dependencies: {e}")

def main():
    composer_path = os.path.join(PROJECT_ROOT, "composer.json")
    package_name = None
    sdks_to_install = []
    
    if os.path.exists(composer_path):
        try:
            with open(composer_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            sdks_to_install = [s for s in config.get("sdks", []) if isinstance(s, dict) and s.get("enabled", True)]
            package_name = config.get("package_name")
            print(f"[*] Reading active SDK list from composer.json: {sdks_to_install}")
        except Exception as e:
            print(f"[!] Error reading composer.json: {e}.")
            sys.exit(1)
            
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
            
    # Cache all SDKs in one consolidated fetch pass
    resolve_and_cache_sdks(sdks_to_install)
    
    # Run the installers
    for sdk in sdks_to_install:
        run_installer(sdk)
        
    if package_name:
        update_pubspec_name(package_name)
    
    if sdks_to_install:
        update_pubspec_dependencies(sdks_to_install)

if __name__ == "__main__":
    main()
