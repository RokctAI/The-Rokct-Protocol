import os
import shutil

PROTOCOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.getcwd()
ROKCT_DIR = os.path.join(PROJECT_ROOT, ".rokct")

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def copy(src, dst):
    ensure_dir(os.path.dirname(dst))
    shutil.copy2(src, dst)
    print(f"[init] Copied {src} -> {dst}")

def copy_dir(src, dst):
    ensure_dir(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copy_dir(s, d)
        else:
            copy(s, d)
    print(f"[init] Copied directory {src} -> {dst}")

def main():
    ensure_dir(ROKCT_DIR)

    core_templates_src = os.path.join(PROTOCOL_DIR, "core", "templates")
    for fname in ["memory.md", "decision_log.md", "project_map.md", "active_session.txt"]:
        copy(os.path.join(core_templates_src, fname), os.path.join(ROKCT_DIR, fname))

    copy(os.path.join(PROTOCOL_DIR, ".cursorrules"), os.path.join(PROJECT_ROOT, ".cursorrules"))

    copy_dir(os.path.join(PROTOCOL_DIR, "core", "skills"), os.path.join(ROKCT_DIR, "skills"))

    copy_dir(os.path.join(PROTOCOL_DIR, "profiles", "local", "skills"), os.path.join(ROKCT_DIR, "skills"))

    local_workflows_src = os.path.join(PROTOCOL_DIR, "profiles", "local", "workflows")
    if os.path.isdir(local_workflows_src):
        copy_dir(local_workflows_src, os.path.join(ROKCT_DIR, "workflows"))

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

    print("[init] Local profile file operations complete.")

if __name__ == "__main__":
    main()
