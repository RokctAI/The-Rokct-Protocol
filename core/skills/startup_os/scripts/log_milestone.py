import sys
import os
import argparse

# Dynamic ROKCT Protocol Path Resolution
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main"

def find_protocol_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        probe_path = os.path.join(current_dir, "The-Rokct-Protocol")
        if os.path.isdir(probe_path):
            return os.path.join(probe_path, "core", "skills", "startup_os", "scripts")
        parent = os.path.dirname(current_dir)
        if parent == current_dir:
            break
        current_dir = parent
    return None

PROTOCOL_SCRIPTS_PATH = find_protocol_path()
if not PROTOCOL_SCRIPTS_PATH:
    # If this script is executed inside the protocol repository itself, resolve relative directory
    local_scripts = os.path.dirname(os.path.abspath(__file__))
    if os.path.isdir(os.path.join(local_scripts, "core")):
        PROTOCOL_SCRIPTS_PATH = local_scripts

if not PROTOCOL_SCRIPTS_PATH:
    print("[Error] Could not locate ROKCT Protocol repository locally.", file=sys.stderr)
    sys.exit(1)

if PROTOCOL_SCRIPTS_PATH not in sys.path:
    sys.path.append(PROTOCOL_SCRIPTS_PATH)

try:
    from core.agent_bridge import log_ambient_milestone
    from core.compiler import resolve_workspace_root
except ImportError as e:
    print(f"[Error] Failed to import bridge logic from ROKCT Protocol repository: {e}", file=sys.stderr)
    sys.exit(1)

def sync_templates():
    active_startup_os_root = resolve_workspace_root()
        
    active_templates_dir = os.path.join(active_startup_os_root, "templates")
    protocol_templates = os.path.join(os.path.dirname(PROTOCOL_SCRIPTS_PATH), "templates")
    
    if os.path.isdir(protocol_templates):
        import shutil
        os.makedirs(active_templates_dir, exist_ok=True)
        for t_type in ["business", "life"]:
            src_sub = os.path.join(protocol_templates, t_type)
            if os.path.isdir(src_sub):
                dest_sub = os.path.join(active_templates_dir, t_type)
                os.makedirs(dest_sub, exist_ok=True)
                for f_name in os.listdir(src_sub):
                    src_file = os.path.join(src_sub, f_name)
                    dest_file = os.path.join(dest_sub, f_name)
                    if os.path.isfile(src_file):
                        shutil.copy2(src_file, dest_file)
        print(f"[StartupOS] Auto-synced templates to workspace: {active_templates_dir}")

def main():
    sync_templates()
    
    parser = argparse.ArgumentParser(description="StartupOS Conversational Milestone Log Local Wrapper")
    parser.add_argument("--name", required=True, help="Profile/instance name (e.g. Rendani)")
    parser.add_argument("--type", choices=["business", "life"], default="life", help="Profile type")
    parser.add_argument("--category", required=True, help="Milestone category (e.g., Technical Mastery, Legacy Sowing)")
    parser.add_argument("--entry", required=True, help="Verbal accomplishment logged by user")
    
    args = parser.parse_args()
    
    active_startup_os_root = resolve_workspace_root()
    questions_path = os.path.join(active_startup_os_root, "instances", args.type, args.name, "questions.md")
    
    if not os.path.exists(questions_path):
        print(f"[Error] Missing questions file under local instance: {questions_path}")
        sys.exit(1)
        
    try:
        log_ambient_milestone(
            filepath=questions_path,
            category=args.category,
            entry_text=args.entry
        )
        print(f"[Success] Milestone logged under {questions_path}")
    except Exception as e:
        print(f"[Error] Milestone log failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
