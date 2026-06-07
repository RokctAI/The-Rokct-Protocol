import os
import shutil
import hashlib
import json
import subprocess

PROTOCOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.getcwd()
ROKCT_DIR = os.path.join(PROJECT_ROOT, ".rokct")

def load_local_manifest():
    manifest_path = os.path.join(PROTOCOL_DIR, "profiles", "local", "manifest.json")
    if not os.path.exists(manifest_path):
        return {}
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_core_manifest():
    manifest_path = os.path.join(PROTOCOL_DIR, "core", "templates", "manifest.json")
    if not os.path.exists(manifest_path):
        return {}
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)

def file_hash(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]

def copy_versioned(src_rel, dst_abs, manifest):
    dst_dir = os.path.dirname(dst_abs)
    os.makedirs(dst_dir, exist_ok=True)

    entry = manifest.get("files", {}).get(src_rel)
    if not entry:
        print(f"[init] Warning: no manifest entry for {src_rel}, copying unconditionally")
        shutil.copy2(os.path.join(PROTOCOL_DIR, src_rel), dst_abs)
        print(f"[init] Copied {src_rel} -> {dst_abs}")
        return

    current_hash = file_hash(dst_abs)
    if current_hash == entry["hash"]:
        print(f"[init] Skipping unchanged {dst_abs}")
        return

    if current_hash is None:
        print(f"[init] New file {dst_abs}, copying from protocol")
    else:
        print(f"[init] WARNING: {dst_abs} differs from protocol version, replacing")
    shutil.copy2(os.path.join(PROTOCOL_DIR, src_rel), dst_abs)
    print(f"[init] Copied {src_rel} -> {dst_abs}")

def copy_dir(src, dst):
    os.makedirs(dst, exist_ok=True)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copy_dir(s, d)
        else:
            copy_versioned(os.path.relpath(s, PROTOCOL_DIR), d, manifest)
    print(f"[init] Synced directory {src} -> {dst}")

def detect_repo_owner():
    try:
        url = subprocess.check_output(["git", "config", "--get", "remote.origin.url"], text=True, stderr=subprocess.DEVNULL).strip()
        if "RokctAI/" in url:
            return url.split("RokctAI/")[-1].replace(".git", "")
    except Exception:
        pass
    return None

def main():
    global manifest
    manifest = load_core_manifest()
    os.makedirs(ROKCT_DIR, exist_ok=True)

    core_templates_src = os.path.join(PROTOCOL_DIR, "core", "templates")
    for fname in ["memory.md", "decision_log.md", "project_map.md", "active_session.txt"]:
        copy_versioned(os.path.join("core", "templates", fname), os.path.join(ROKCT_DIR, fname), manifest)

    copy_versioned(".cursorrules", os.path.join(PROJECT_ROOT, ".cursorrules"), manifest)

    copy_dir(os.path.join(PROTOCOL_DIR, "core", "skills"), os.path.join(ROKCT_DIR, "skills"))

    copy_versioned(os.path.join("profiles", "web", "rules.md"), os.path.join(ROKCT_DIR, "profiles.md"), manifest)

    gitignore_path = os.path.join(ROKCT_DIR, ".gitignore")
    if not os.path.exists(gitignore_path):
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write("skills/\n")
        print(f"[init] Created {gitignore_path}")

    print("[init] Web profile file operations complete.")

    shutil.copy2(os.path.join(PROTOCOL_DIR, "workflows", "sync_workspace.py"), os.path.join(ROKCT_DIR, "sync_workspace.py"))
    print("[init] Copied sync_workspace.py -> .rokct/sync_workspace.py")

    shutil.copy2(os.path.abspath(__file__), os.path.join(ROKCT_DIR, "initiate.py"))
    print("[init] Copied initiate.py -> .rokct/initiate.py")

    shutil.copy2(os.path.join(PROTOCOL_DIR, "profiles", "web", "end_protocol.py"), os.path.join(ROKCT_DIR, "end_protocol.py"))
    print("[init] Copied end_protocol.py -> .rokct/end_protocol.py")

    config_path = os.path.join(ROKCT_DIR, ".workspace_config.json")
    if not os.path.exists(config_path):
        repo_owner = detect_repo_owner()
        if repo_owner:
            parent_repo = "RokctAI/occultation"
            print(f"[init] Detected RokctAI repo — routing working files to {parent_repo}")
        else:
            print("[init] Not a RokctAI repo — skipping workspace config (web agent cannot prompt for parent repo)")
            parent_repo = None

        if parent_repo:
            workspace_config = {
                "parent_repo": parent_repo,
                "parent_branch": "main",
                "working_files": [
                    "memory.md",
                    "decision_log.md",
                    "project_map.md",
                    "active_session.txt"
                ]
            }
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(workspace_config, f, indent=2)
            print(f"[init] Created .rokct/.workspace_config.json pointing to {workspace_config['parent_repo']}")

if __name__ == "__main__":
    main()
