import os
import sys
import json
import hashlib
import subprocess
from datetime import datetime, timezone

PROTOCOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.getcwd()
ROKCT_DIR = os.path.join(PROJECT_ROOT, ".rokct")
CONFIG_PATH = os.path.join(ROKCT_DIR, ".workspace_config.json")

HEADER = "<!-- ROKCT-SYNC-START: {repo}/{session}/{ts} -->\n"
FOOTER = "<!-- ROKCT-SYNC-END: {repo}/{session}/{ts} -->\n"

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print("[sync] No .workspace_config.json found")
        return None
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def file_hash(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]

def extract_new_sections(child_path, parent_path, repo, session):
    if not os.path.exists(child_path):
        return None
    child_content = open(child_path, "r", encoding="utf-8").read()
    
    if os.path.exists(parent_path):
        parent_content = open(parent_path, "r", encoding="utf-8").read()
        # Only extract what child has that parent doesn't
        if child_content == parent_content.strip() or child_content.strip() in parent_content:
            return None
        # Find lines unique to child (bottom-only append)
        child_lines = child_content.splitlines()
        parent_lines = parent_content.splitlines()
        new_lines = []
        for line in child_lines:
            if line not in parent_lines:
                new_lines.append(line)
        if not new_lines:
            return None
        new_content = "\n".join(new_lines)
    else:
        new_content = child_content.strip()
    
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return HEADER.format(repo=repo, session=session, ts=ts) + new_content + "\n" + FOOTER.format(repo=repo, session=session, ts=ts)

def sync_to_parent(config):
    parent_repo = config.get("parent_repo")
    working_files = config.get("working_files", [
        "memory.md", "decision_log.md", "project_map.md", "active_session.txt"
    ])
    if not parent_repo:
        print("[sync] No parent_repo in config")
        return
    
    session = config.get("session_id", "unknown")
    repo_name = parent_repo.split("/")[-1]
    
    parent_clone = os.path.join(ROKCT_DIR, ".parent_clone")
    
    if os.path.isdir(parent_clone):
        subprocess.run(["git", "-C", parent_clone, "fetch", "origin"], capture_output=True)
        subprocess.run(["git", "-C", parent_clone, "reset", "--hard", f"origin/{config.get('parent_branch', 'main')}"], capture_output=True)
    else:
        os.makedirs(parent_clone, exist_ok=True)
        clone_url = f"https://github.com/{parent_repo}.git"
        if config.get("parent_token"):
            clone_url = f"https://{config['parent_token']}@github.com/{parent_repo}.git"
        result = subprocess.run(["git", "clone", "--branch", config.get("parent_branch", "main"), clone_url, parent_clone], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[sync] Clone failed: {result.stderr}")
            return
    
    parent_rokct = os.path.join(parent_clone, ".rokct")
    os.makedirs(parent_rokct, exist_ok=True)
    
    any_changes = False
    for rel_file in working_files:
        child_path = os.path.join(ROKCT_DIR, rel_file)
        parent_path = os.path.join(parent_rokct, rel_file)
        
        section = extract_new_sections(child_path, parent_path, repo_name, session)
        if section:
            os.makedirs(os.path.dirname(parent_path), exist_ok=True)
            existing = ""
            if os.path.exists(parent_path):
                existing = open(parent_path, "r", encoding="utf-8").read()
            with open(parent_path, "w", encoding="utf-8") as f:
                f.write(existing.rstrip() + "\n\n" + section + "\n")
            print(f"[sync] Appended new sections to parent .rokct/{rel_file}")
            any_changes = True
        else:
            print(f"[sync] No new content for .rokct/{rel_file}")
    
    if not any_changes:
        print("[sync] No changes to push")
        return
    
    subprocess.run(["git", "-C", parent_clone, "config", "user.email", "rokct-bot@users.noreply.github.com"], capture_output=True)
    subprocess.run(["git", "-C", parent_clone, "config", "user.name", "rokct-bot"], capture_output=True)
    subprocess.run(["git", "-C", parent_clone, "add", ".rokct/"], capture_output=True)
    subprocess.run(["git", "-C", parent_clone, "commit", "-m", "chore(workspace): sync working files [skip ci]"], capture_output=True)
    result = subprocess.run(["git", "-C", parent_clone, "push"], capture_output=True, text=True)
    if result.returncode == 0:
        print("[sync] Pushed to parent repo")
    else:
        print(f"[sync] Push failed: {result.stderr}")

def main():
    config = load_config()
    if not config:
        return
    sync_to_parent(config)

if __name__ == "__main__":
    main()
