import os
import shutil
import hashlib
import json
import subprocess
import sys
import urllib.request
import io
import zipfile

GITHUB_ZIP_BASE = "https://github.com/RokctAI/The-Rokct-Protocol/archive/refs/heads/main.zip"
PROTOCOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.getcwd()
ROKCT_DIR = os.path.join(PROJECT_ROOT, ".rokct")
REMOTE_PREFIX = "The-Rokct-Protocol-main"

def fetch_file_from_github(rel_path, dest_path):
    url = f"https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/{rel_path.replace(os.sep, '/')}"
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as r:
            with open(dest_path, "wb") as f:
                f.write(r.read())
        print(f"[init] Fetched {rel_path}")
    except Exception as e:
        print(f"[init] Failed to fetch {rel_path}: {e}", file=sys.stderr)

def load_local_manifest():
    manifest_path = os.path.join(PROTOCOL_DIR, "profiles", "local", "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def load_core_manifest():
    manifest_path = os.path.join(PROTOCOL_DIR, "core", "templates", "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    try:
        req = urllib.request.Request(f"https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/core/templates/manifest.json", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {}

def file_hash(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]

def ensure_file(rel_path, dest_path):
    if os.path.exists(dest_path):
        return
    src = os.path.join(PROTOCOL_DIR, rel_path)
    if os.path.exists(src):
        shutil.copy2(src, dest_path)
        print(f"[init] Copied {rel_path}")
    else:
        fetch_file_from_github(rel_path, dest_path)

def copy_versioned(src_rel, dst_abs, manifest):
    dst_dir = os.path.dirname(dst_abs)
    os.makedirs(dst_dir, exist_ok=True)

    entry = manifest.get("files", {}).get(src_rel)
    src = os.path.join(PROTOCOL_DIR, src_rel)
    if not entry:
        if os.path.exists(src):
            shutil.copy2(src, dst_abs)
        else:
            fetch_file_from_github(src_rel, dst_abs)
        print(f"[init] Copied {src_rel} -> {dst_abs}")
        return

    current_hash = file_hash(dst_abs)
    if current_hash == entry["hash"]:
        print(f"[init] Skipping unchanged {dst_abs}")
        return

    if os.path.exists(src):
        shutil.copy2(src, dst_abs)
    else:
        fetch_file_from_github(src_rel, dst_abs)
    print(f"[init] Copied {src_rel} -> {dst_abs}")

def copy_dir(src, dst):
    if not os.path.isdir(src):
        # Remote mode - derive path from src
        rel_src = src.replace(PROTOCOL_DIR + os.sep, "") if PROTOCOL_DIR in src else src
        fetch_dir_from_github(rel_src, dst)
        return
    os.makedirs(dst, exist_ok=True)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copy_dir(s, d)
        else:
            copy_versioned(os.path.relpath(s, PROTOCOL_DIR), d, manifest)
    print(f"[init] Synced directory {src} -> {dst}")

def fetch_dir_from_github(rel_src, dst):
    prefix = f"The-Rokct-Protocol-main/{rel_src.replace(os.sep, '/')}/"
    try:
        print(f"[init] Fetching directory from GitHub: {rel_src}")
        req = urllib.request.Request(GITHUB_ZIP_BASE, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as r:
            z = zipfile.ZipFile(io.BytesIO(r.read()))
        os.makedirs(dst, exist_ok=True)
        count = 0
        for name in z.namelist():
            if name.startswith(prefix) and not name.endswith("/"):
                rel = name[len(prefix):]
                dest = os.path.join(dst, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(z.read(name))
                count += 1
        print(f"[init] Fetched {count} files from {rel_src}")
    except Exception as e:
        print(f"[init] Failed to fetch directory {rel_src}: {e}", file=sys.stderr)

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

    repo_owner = detect_repo_owner()
    if repo_owner:
        copy_dir(os.path.join(PROTOCOL_DIR, "core", "skills"), os.path.join(ROKCT_DIR, "skills"))
    else:
        core_skills_dir = os.path.join(PROTOCOL_DIR, "core", "skills")
        dst = os.path.join(ROKCT_DIR, "skills")
        os.makedirs(dst, exist_ok=True)
        for item in os.listdir(core_skills_dir):
            s = os.path.join(core_skills_dir, item)
            if os.path.isdir(s) and item != "startup_os":
                copy_dir(s, os.path.join(dst, item))

    copy_versioned(os.path.join("profiles", "web", "rules.md"), os.path.join(ROKCT_DIR, "profiles.md"), manifest)

    copy_dir(os.path.join(PROTOCOL_DIR, "workflows"), os.path.join(ROKCT_DIR, "workflows"))

    gitignore_path = os.path.join(ROKCT_DIR, ".gitignore")
    if not os.path.exists(gitignore_path):
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write("skills/\n")
        print(f"[init] Created {gitignore_path}")

    print("[init] Web profile file operations complete.")

    ensure_file("workflows/sync_workspace.py", os.path.join(ROKCT_DIR, "sync_workspace.py"))
    ensure_file("workflows/sync_workspace.yml", os.path.join(PROJECT_ROOT, ".github", "workflows", "sync_workspace.yml"))

    dest_initiate = os.path.join(ROKCT_DIR, "initiate.py")
    if os.path.abspath(__file__) != dest_initiate:
        shutil.copy2(os.path.abspath(__file__), dest_initiate)
        print("[init] Copied initiate.py -> .rokct/initiate.py")

    ensure_file("profiles/web/end_protocol.py", os.path.join(ROKCT_DIR, "end_protocol.py"))

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
