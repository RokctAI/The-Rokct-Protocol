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
        
        # Check if repo exists locally in the parent folder of PROJECT_ROOT
        workspace_parent = os.path.dirname(PROJECT_ROOT)
        local_repo_path = os.path.join(workspace_parent, repo_name)
        
        is_local_available = os.path.exists(local_repo_path)
        
        if is_local_available:
            print(f"[*] Found local repository for {repo_name} at {local_repo_path}. Using local copy.")
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
                subprocess.run(["git", "clone", "-b", ref, "--depth", "1", git_url, temp_repo_dir], check=True)
                repo_source_dir = temp_repo_dir
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
            src_dir = os.path.join(repo_source_dir, *subpath.split("/"))
            
            if os.path.exists(src_dir):
                print(f"[+] Extracting {sdk_name} from {subpath} to {target_dir}...")
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir)
                shutil.copytree(src_dir, target_dir)
            else:
                print(f"[!] Error: Path {subpath} not found in repository {repo_source_dir}")
                
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
            while i < len(lines) and (lines[i].startswith(" ") or lines[i].strip() == ""):
                stripped = lines[i].strip()
                if stripped and not stripped.startswith("#") and ":" in stripped:
                    existing_keys.add(stripped.split(":", 1)[0].strip())
                i += 1

        missing = {k: v for k, v in REQUIRED_DEPENDENCY_OVERRIDES.items() if k not in existing_keys}
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
            lines[overrides_start + 1:overrides_start + 1] = new_override_lines

        with open(pubspec_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"[*] Ensured required dependency_overrides in pubspec.yaml: {list(missing.keys())}")
    except Exception as e:
        print(f"[!] Error ensuring pubspec.yaml dependency_overrides: {e}")

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
    pub_get = subprocess.run(["flutter", "pub", "get"], cwd=PROJECT_ROOT, shell=True)
    if pub_get.returncode != 0:
        print("[!] flutter pub get failed; skipping code generation.")
        return

    print("[*] Running build_runner (--force-jit, required for packages with native-asset build hooks)...")
    build = subprocess.run(
        ["dart", "run", "build_runner", "build", "--force-jit"],
        cwd=PROJECT_ROOT,
        shell=True,
        capture_output=True,
        text=True,
    )
    if build.returncode != 0 and "Could not find an option named" in (build.stdout + build.stderr):
        print("[*] This build_runner version doesn't support --force-jit; retrying with --delete-conflicting-outputs...")
        build = subprocess.run(
            ["dart", "run", "build_runner", "build", "--delete-conflicting-outputs"],
            cwd=PROJECT_ROOT,
            shell=True,
        )
    else:
        # Either it succeeded or failed for a real reason - show the output either way.
        print(build.stdout, end="")
        print(build.stderr, end="")

    if build.returncode == 0:
        print("[+] Code generation completed successfully.")
    else:
        print(f"[!] Code generation failed (exit {build.returncode}). Check output above for the specific error.")

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

    ensure_pubspec_overrides()
    remove_stale_widget_test()
    run_code_generation()

if __name__ == "__main__":
    main()
