import os
import hashlib
import json
import shutil

PROTOCOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.getcwd()
ROKCT_DIR = os.path.join(PROJECT_ROOT, ".rokct")

def dir_hash(d):
    if not os.path.isdir(d):
        return None
    h = hashlib.sha256()
    for root, dirs, files in os.walk(d):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(root, f)
            h.update(f.encode())
            with open(p, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()[:16]

def file_hash(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]

def load_json(name):
    p = os.path.join(PROTOCOL_DIR, name)
    if not os.path.exists(p):
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def touch(path):
    with open(path, "w", encoding="utf-8") as f:
        f.write("")

def main():
    if not os.path.isdir(ROKCT_DIR):
        print("[end] .rokct/ not found, nothing to do")
        return

    core_manifest = load_json("core/templates/manifest.json")
    profile_manifest = load_json("profiles/web/manifest.json")

    pristine_skills = "f7cfce8ecd1c06e7"
    pristine_workflows = "af7192f8a988c3a6"

    skills_dir = os.path.join(ROKCT_DIR, "skills")
    if os.path.isdir(skills_dir) and dir_hash(skills_dir) == pristine_skills:
        shutil.rmtree(skills_dir)
        print("[end] Deleted pristine skills/ (auto-clean)")
    else:
        print("[end] Kept modified skills/")

    workflows_dir = os.path.join(ROKCT_DIR, "workflows")
    if os.path.isdir(workflows_dir) and dir_hash(workflows_dir) == pristine_workflows:
        shutil.rmtree(workflows_dir)
        print("[end] Deleted pristine workflows/ (auto-clean)")
    else:
        print("[end] Kept modified workflows/")

    for item in os.listdir(ROKCT_DIR):
        item_path = os.path.join(ROKCT_DIR, item)
        if item == "active_session.txt":
            print("[end] Kept active_session.txt (workspace working file)")
            continue
        if item == ".sync_ready":
            continue
        if os.path.isdir(item_path):
            continue
        core_key = f"core/templates/{item}"
        profile_key = f"profiles/web/{item}"
        if item == "profiles.md":
            profile_key = "profiles/web/rules.md"
        if file_hash(item_path) in (core_manifest.get("files", {}).get(core_key, {}).get("hash"), profile_manifest.get("files", {}).get(profile_key, {}).get("hash")):
            os.remove(item_path)
            print(f"[end] Deleted pristine {item}")
        else:
            print(f"[end] Kept modified {item}")

    touch(os.path.join(ROKCT_DIR, ".sync_ready"))
    print("[end] Created .sync_ready marker — CI will pick this up when active session ends")
    print("[end] End protocol cleanup complete.")

if __name__ == "__main__":
    main()
