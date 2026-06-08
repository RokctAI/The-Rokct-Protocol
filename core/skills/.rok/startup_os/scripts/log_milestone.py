# compliance-silent
import sys
import os
import argparse
import urllib.request
import io
import zipfile

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main"

def fetch_core_from_github():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)

    core_dir = os.path.join(parent_dir, "core")
    os.makedirs(core_dir, exist_ok=True)

    init_py = os.path.join(core_dir, "__init__.py")
    if not os.path.exists(init_py):
        with open(init_py, 'w') as f:
            f.write("")

    core_files = ["compiler.py", "parser.py", "agent_bridge.py"]
    github_raw_core = f"{GITHUB_RAW_BASE}/core/utils/startup_os"

    for f_name in core_files:
        dest_file = os.path.join(core_dir, f_name)
        url = f"{github_raw_core}/{f_name}"
        try:
            print(f"[StartupOS] Fetching core engine from GitHub: {f_name}")
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

    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

fetch_core_from_github()

try:
    from core.agent_bridge import log_ambient_milestone
    from core.compiler import resolve_workspace_root
except ImportError as e:
    print(f"[Error] Sourced milestone imports failed: {e}", file=sys.stderr)
    sys.exit(1)

def sync_templates():
    active_startup_os_root = resolve_workspace_root()
    active_templates_dir = os.path.join(active_startup_os_root, "templates")
    os.makedirs(active_templates_dir, exist_ok=True)

    zip_url = f"{GITHUB_RAW_BASE}/archive/refs/heads/main.zip"
    print(f"[StartupOS] Fetching templates from GitHub raw: {zip_url}")

    try:
        req = urllib.request.Request(zip_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            zip_data = response.read()

        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            sync_count = 0
            for name in z.namelist():
                if "core/skills/startup_os/templates/" in name and not name.endswith("/"):
                    parts = name.split("core/skills/startup_os/templates/")
                    if len(parts) == 2:
                        rel_path = parts[1]
                        dest_path = os.path.join(active_templates_dir, rel_path)
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

                        with open(dest_path, "wb") as f:
                            f.write(z.read(name))
                        sync_count += 1
        print(f"[Success] Retrieved and synced {sync_count} templates from GitHub!")
    except Exception as e:
        print(f"[Warning] Failed to fetch templates from GitHub: {e}", file=sys.stderr)

def main():
    # Wrapper for the ambient milestone logging engine
    # appends user-provided accomplishments to the living ledger (questions.md)
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

