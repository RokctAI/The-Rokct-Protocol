import sys
import os
import argparse
import urllib.request
import io
import zipfile

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

def ensure_core_engines():
    protocol_path = find_protocol_path()
    if protocol_path:
        if protocol_path not in sys.path:
            sys.path.append(protocol_path)
        return
        
    # Standalone/Docker mode: Download core engines from GitHub raw
    current_dir = os.path.dirname(os.path.abspath(__file__))
    core_dir = os.path.join(current_dir, "core")
    os.makedirs(core_dir, exist_ok=True)
    
    init_py = os.path.join(core_dir, "__init__.py")
    if not os.path.exists(init_py):
        with open(init_py, 'w') as f:
            f.write("")
            
    core_files = ["compiler.py", "parser.py", "agent_bridge.py"]
    github_raw_core = f"{GITHUB_RAW_BASE}/core/skills/startup_os/scripts/core"
    
    for f_name in core_files:
        dest_file = os.path.join(core_dir, f_name)
        url = f"{github_raw_core}/{f_name}"
        try:
            print(f"[StartupOS] Sourcing latest core engine from GitHub raw: {f_name}")
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                with open(dest_file, 'wb') as f:
                    f.write(response.read())
        except Exception as e:
            if not os.path.exists(dest_file):
                print(f"[Error] Failed to fetch core engine {f_name}: {e}", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"[Warning] Using cached core engine {f_name} (fetch failed: {e})", file=sys.stderr)
                
    if current_dir not in sys.path:
        sys.path.append(current_dir)

# Initialize Core
ensure_core_engines()

try:
    from core.agent_bridge import log_ambient_milestone
    from core.compiler import resolve_workspace_root
except ImportError as e:
    print(f"[Error] Sourced milestone imports failed: {e}", file=sys.stderr)
    sys.exit(1)

def sync_templates():
    active_startup_os_root = resolve_workspace_root()
    active_templates_dir = os.path.join(active_startup_os_root, "templates")
    
    # Path to baked-in templates (if running locally or inside a fully baked repo)
    protocol_path = find_protocol_path()
    if protocol_path:
        protocol_templates = os.path.join(os.path.dirname(protocol_path), "templates")
    else:
        # Fallback to local sibling search
        current_dir = os.path.dirname(os.path.abspath(__file__))
        protocol_templates = os.path.join(os.path.dirname(current_dir), "templates")
    
    # Method A: Local folder exists (Desktop development)
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
        print(f"[StartupOS] Auto-synced templates from local repository: {active_templates_dir}")
        
    # Method B: Standalone/Docker environment (Fetch dynamically from GitHub Raw)
    else:
        zip_url = "https://github.com/RokctAI/The-Rokct-Protocol/archive/refs/heads/main.zip"
        print(f"[StartupOS] Sourcing latest templates from GitHub raw: {zip_url}")
        
        try:
            req = urllib.request.Request(
                zip_url, 
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req) as response:
                zip_data = response.read()
                
            with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
                sync_count = 0
                for name in z.namelist():
                    # Parse only templates folder contents
                    if "core/skills/startup_os/templates/" in name and not name.endswith("/"):
                        parts = name.split("core/skills/startup_os/templates/")
                        if len(parts) == 2:
                            rel_path = parts[1] # e.g. business/10_lean_canvas.md
                            dest_path = os.path.join(active_templates_dir, rel_path)
                            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                            
                            with open(dest_path, "wb") as f:
                                f.write(z.read(name))
                            sync_count += 1
            print(f"[Success] Dynamically retrieved and synced {sync_count} templates from GitHub raw!")
        except Exception as e:
            print(f"[Warning] Failed to dynamically fetch templates from GitHub raw: {e}", file=sys.stderr)

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
        print(f"[Error] Missing questions file under local instance: {questions_path}", file=sys.stderr)
        sys.exit(1)
        
    try:
        log_ambient_milestone(
            filepath=questions_path,
            category=args.category,
            entry_text=args.entry
        )
        print(f"[Success] Milestone logged under {questions_path}")
    except Exception as e:
        print(f"[Error] Milestone log failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
