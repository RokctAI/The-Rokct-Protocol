import os
import hashlib
import json
import shutil

PROTOCOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.getcwd()
ROKCT_DIR = os.path.join(PROJECT_ROOT, ".rokct")

DEFAULT_GITIGNORE_CONTENT = "active_session.txt\n"

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

def is_pristine_dir(abs_path, expected_hash):
    return dir_hash(abs_path) == expected_hash

def is_pristine_gitignore(abs_path):
    if not os.path.exists(abs_path):
        return True
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            return f.read() == DEFAULT_GITIGNORE_CONTENT
    except Exception:
        return False

def main():
    if not os.path.isdir(ROKCT_DIR):
        print("[end] .rokct/ not found, nothing to do")
        return

    skills_dir = os.path.join(ROKCT_DIR, "skills")
    workflows_dir = os.path.join(ROKCT_DIR, "workflows")
    gitignore_path = os.path.join(ROKCT_DIR, ".gitignore")

    pristine_skills_hash = "f7cfce8ecd1c06e7"
    pristine_workflows_hash = "af7192f8a988c3a6"

    if os.path.isdir(skills_dir):
        if is_pristine_dir(skills_dir, pristine_skills_hash):
            shutil.rmtree(skills_dir)
            print("[end] Deleted pristine skills/ (auto-clean)")
        else:
            print("[end] Kept modified skills/")

    if os.path.isdir(workflows_dir):
        if is_pristine_dir(workflows_dir, pristine_workflows_hash):
            shutil.rmtree(workflows_dir)
            print("[end] Deleted pristine workflows/ (auto-clean)")
        else:
            print("[end] Kept modified workflows/")

    if is_pristine_gitignore(gitignore_path):
        try:
            os.remove(gitignore_path)
            print("[end] Deleted pristine .gitignore (auto-clean)")
        except FileNotFoundError:
            pass
    else:
        print("[end] Kept modified .gitignore")

    print("[end] End protocol cleanup complete.")

if __name__ == "__main__":
    main()
