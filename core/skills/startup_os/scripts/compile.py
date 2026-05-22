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
    from core.compiler import compile_instance
except ImportError as e:
    print(f"[Error] Failed to import compiler logic from ROKCT Protocol repository: {e}", file=sys.stderr)
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="StartupOS Strategic Compiler Local Project Wrapper")
    parser.add_argument("--type", choices=["business", "life"], required=True, help="Profile type")
    parser.add_argument("--name", required=True, help="Profile/instance name (folder name)")
    parser.add_argument("--monorepo-root", default=None, help="Custom monorepo root path override")
    
    args = parser.parse_args()
    
    try:
        compile_instance(
            instance_type=args.type,
            instance_name=args.name,
            monorepo_root=args.monorepo_root
        )
    except Exception as e:
        print(f"[Error] Compile failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
