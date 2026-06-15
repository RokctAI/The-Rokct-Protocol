# compliance-silent
import os
import hashlib
import json
import shutil
import urllib.request

PROTOCOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.getcwd()
ROKCT_DIR = os.path.join(PROJECT_ROOT, ".rokct")
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main"

def dir_hash(d):
    if not os.path.isdir(d):
        return None
    h = hashlib.sha256()
    for root, dirs, files in os.walk(d):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(root, f)
            h.update(os.path.relpath(p, d).encode())
            with open(p, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()[:16]

def file_hash(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]

def load_json_remote(name):
    url = f"{GITHUB_RAW_BASE}/{name}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "X-Trace-Id": "agent-http"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {}

def load_json(name):
    p = os.path.join(PROTOCOL_DIR, name)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return load_json_remote(name)

def touch(path):
    with open(path, "w", encoding="utf-8") as f:
        f.write("")

def main():
    if not os.path.isdir(ROKCT_DIR):
        print("[end] .rokct/ not found, nothing to do")
        return

    core_manifest = load_json("core/templates/manifest.json")
    profile_manifest = load_json("profiles/web/manifest.json")

    pristine_skills = "86400b7a6e267879"

    skills_dir = os.path.join(ROKCT_DIR, "skills")
    if os.path.isdir(skills_dir):
        shutil.rmtree(skills_dir)
        print("[end] Deleted skills/ (unconditional cleanup)")

    workflows_dir = os.path.join(ROKCT_DIR, "workflows")
    if os.path.isdir(workflows_dir):
        for f in os.listdir(workflows_dir):
            fpath = os.path.join(workflows_dir, f)
            if os.path.isfile(fpath) and f != "init_protocol.md":
                os.remove(fpath)
                print(f"[end] Deleted workflow: {f}")
        print("[end] Cleaned workflows/ (kept init_protocol.md)")

    for item in os.listdir(ROKCT_DIR):
        item_path = os.path.join(ROKCT_DIR, item)
        if item in ("active_session.txt", "initiate.py"):
            print(f"[end] Kept {item} (protocol tool)")
            continue
        if item == ".sync_ready":
            continue
        if os.path.isdir(item_path):
            if item in ("workflows", "agent", "evidence", "images"):
                continue
            shutil.rmtree(item_path)
            print(f"[end] Deleted directory: {item}")
            continue
        core_key = f"core/templates/{item}"
        profile_rel = f"profiles/web/{item}"
        if item == "profiles.md":
            profile_rel = "profiles/web/rules.md"
        if file_hash(item_path) in (core_manifest.get("files", {}).get(core_key, {}).get("hash"), profile_manifest.get("files", {}).get(profile_rel, {}).get("hash")):
            os.remove(item_path)
            print(f"[end] Deleted pristine {item}")
        else:
            print(f"[end] Kept modified {item}")

    touch(os.path.join(ROKCT_DIR, ".sync_ready"))
    print("[end] Created .sync_ready marker — CI will pick this up when active session ends")
    print("[end] End protocol cleanup complete.")

if __name__ == "__main__":
    main()

