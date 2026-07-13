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
            return "/".join(parts[idx + 1:])
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return normalized


def _rmtree_force(path):
    def remove_readonly(func, p, excinfo):
        import stat
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=remove_readonly)


def resolve_and_cache_sdks(sdks):
    """Identical resolution strategy to the Flutter composer: group by git
    remote to avoid re-cloning the same repo for multiple SDKs living in it,
    fall back to a local sibling checkout if present, otherwise shallow-clone.
    This part of the pattern has nothing Dart-specific about it, so it is
    reused as-is rather than redesigned.
    """
    cache_base = os.path.join(PROJECT_ROOT, ".rokct", "cache")
    os.makedirs(cache_base, exist_ok=True)

    git_groups = {}
    local_sdks = []

    for sdk in sdks:
        if not isinstance(sdk, dict):
            local_sdks.append({"name": sdk, "path": f"../SDKs/{clean_sdk_name(sdk)}/nextjs"})
            continue
        source = sdk.get("source", "local")
        if source == "git" and sdk.get("git"):
            git_groups.setdefault(sdk["git"], []).append(sdk)
        else:
            local_sdks.append(sdk)

    for git_url, group_sdks in git_groups.items():
        repo_name = extract_repo_name(git_url)
        temp_repo_dir = os.path.join(cache_base, f"{repo_name}_sdk")
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
                if os.path.exists(temp_repo_dir):
                    _rmtree_force(temp_repo_dir)
                subprocess.run(["git", "clone", "-b", ref, "--depth", "1", git_url, temp_repo_dir], check=True)
                repo_source_dir = temp_repo_dir
            except Exception as e:
                print(f"[!] Failed to clone {git_url}: {e}")
                sys.exit(1)

        for sdk in group_sdks:
            sdk_name = sdk["name"]
            clean_name = clean_sdk_name(sdk_name)
            target_dir = os.path.join(cache_base, clean_name)
            subpath = get_subpath_in_repo(sdk.get("path", ""), repo_name)
            src_dir = os.path.join(repo_source_dir, *subpath.split("/"))

            if os.path.exists(src_dir):
                print(f"[+] Extracting {sdk_name} from {subpath} to {target_dir}...")
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir)
                shutil.copytree(src_dir, target_dir)
            else:
                print(f"[!] Error: Path {subpath} not found in repository {repo_source_dir}")

        if not is_local_available and os.path.exists(temp_repo_dir):
            _rmtree_force(temp_repo_dir)

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
        subprocess.run([sys.executable, installer_script], cwd=PROJECT_ROOT,
                        capture_output=True, text=True, check=True)
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


def run_npm_install():
    """Single npm install pass after all SDK installers have merged their
    dependencies into package.json — mirrors the Flutter composer running
    `flutter pub get` once at the end rather than per-SDK. Unlike Flutter,
    there is no codegen/build_runner-equivalent step: Next.js SDK templates
    are plain .ts/.tsx source, nothing to generate.
    """
    if not os.path.exists(os.path.join(PROJECT_ROOT, "package.json")):
        return
    print("\n[*] Running npm install...")
    result = subprocess.run(["npm", "install"], cwd=PROJECT_ROOT, shell=True)
    if result.returncode == 0:
        print("[+] npm install completed successfully.")
    else:
        print(f"[!] npm install failed (exit {result.returncode}). Check output above.")


def main():
    composer_path = os.path.join(PROJECT_ROOT, "composer.json")
    sdks_to_install = []

    if os.path.exists(composer_path):
        try:
            with open(composer_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            sdks_to_install = [s for s in config.get("sdks", []) if isinstance(s, dict) and s.get("enabled", True)]
            print(f"[*] Reading active SDK list from composer.json: {sdks_to_install}")
        except Exception as e:
            print(f"[!] Error reading composer.json: {e}.")
            sys.exit(1)

    if len(sys.argv) >= 2:
        requested_names = sys.argv[1:]
        sdks_to_install = [s for s in sdks_to_install if s["name"] in requested_names]

    if not sdks_to_install:
        print("[-] No SDKs found to install.")
        sys.exit(1)

    resolve_and_cache_sdks(sdks_to_install)

    for sdk in sdks_to_install:
        run_installer(sdk)

    run_npm_install()


if __name__ == "__main__":
    main()
