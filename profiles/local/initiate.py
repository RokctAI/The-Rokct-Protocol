import os
import shutil
import subprocess
import hashlib
import json

PROTOCOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.getcwd()
ROKCT_DIR = os.path.join(PROJECT_ROOT, ".rokct")

def load_manifest():
    manifest_path = os.path.join(PROTOCOL_DIR, "profiles", "local", "manifest.json")
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

def main():
    global manifest
    manifest = load_manifest()
    os.makedirs(ROKCT_DIR, exist_ok=True)

    core_templates_src = os.path.join(PROTOCOL_DIR, "core", "templates")
    for fname in ["memory.md", "decision_log.md", "project_map.md", "active_session.txt"]:
        copy_versioned(os.path.join("core", "templates", fname), os.path.join(ROKCT_DIR, fname), manifest)

    copy_versioned(".cursorrules", os.path.join(PROJECT_ROOT, ".cursorrules"), manifest)

    copy_dir(os.path.join(PROTOCOL_DIR, "core", "skills"), os.path.join(ROKCT_DIR, "skills"))

    copy_dir(os.path.join(PROTOCOL_DIR, "profiles", "local", "skills"), os.path.join(ROKCT_DIR, "skills"))

    copy_versioned(os.path.join("profiles", "local", "rules.md"), os.path.join(ROKCT_DIR, "profiles.md"), manifest)

    local_workflows_src = os.path.join(PROTOCOL_DIR, "profiles", "local", "workflows")
    if os.path.isdir(local_workflows_src):
        copy_dir(local_workflows_src, os.path.join(ROKCT_DIR, "workflows"))

    try:
        email = subprocess.check_output(["git", "config", "user.email"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        email = ""
    if email:
        prefix = email.split("@")[0].replace(".", "").lower()
        domain = email.split("@")[1].lower()
        domain_hash = hashlib.md5(domain.encode()).hexdigest()[:6]
        safe_id = f"{prefix}.{domain_hash}"
        mem_path = os.path.join(ROKCT_DIR, "memory.md")
        with open(mem_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n## Safe ID\n{safe_id}\n")
        print(f"[init] Registered safe identity: {safe_id}")

    gitignore_path = os.path.join(ROKCT_DIR, ".gitignore")
    if not os.path.exists(gitignore_path):
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write("active_session.txt\n")
        print(f"[init] Created {gitignore_path}")
    else:
        content = open(gitignore_path, "r", encoding="utf-8").read()
        if "active_session.txt" not in content:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write("\nactive_session.txt\n")
            print(f"[init] Updated {gitignore_path}")

    print("[init] Local profile initialization complete.")

if __name__ == "__main__":
    main()
