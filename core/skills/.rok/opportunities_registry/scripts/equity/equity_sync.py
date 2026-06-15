# compliance-silent
import os, sys, subprocess, urllib.request, zipfile, io

GITHUB_ZIP_BASE = "https://github.com/RokctAI/The-Rokct-Protocol/archive/refs/heads/main.zip"

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = current_dir
    while repo_root:
        if os.path.exists(os.path.join(repo_root, ".rokct")):
            break
        parent = os.path.dirname(repo_root)
        if parent == repo_root:
            break
        repo_root = parent
        
    cache_dir = os.path.join(repo_root, ".rokct", "cache", "opportunities")
    
    if not os.path.exists(cache_dir):
        print("[wrapper] Fetching opportunities scripts from GitHub...")
        os.makedirs(cache_dir, exist_ok=True)
        try:
            req = urllib.request.Request(GITHUB_ZIP_BASE, headers={"User-Agent": "Mozilla/5.0", "X-Trace-Id": "agent-http"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                z = zipfile.ZipFile(io.BytesIO(resp.read()))
            prefix = "The-Rokct-Protocol-main/core/utils/opportunities/"
            count = 0
            for name in z.namelist():
                if name.startswith(prefix) and not name.endswith("/"):
                    rel = name[len(prefix):]
                    dest = os.path.join(cache_dir, rel)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with open(dest, "wb") as f:
                        f.write(z.read(name))
                    count += 1
            print(f"[wrapper] Fetched {count} files to cache.")
        except Exception as e:
            print(f"Error downloading opportunities script cache: {e}", file=sys.stderr)
            sys.exit(1)
            
    skills_scripts_dir = os.path.join(repo_root, ".rokct", "skills", ".rok", "opportunities_registry", "scripts")
    rel_path = os.path.relpath(os.path.abspath(__file__), skills_scripts_dir)
    target_script = os.path.join(cache_dir, rel_path)
    
    if not os.path.exists(target_script):
        print(f"Error: Target script not found in cache: {target_script}", file=sys.stderr)
        sys.exit(1)
        
    res = subprocess.run([sys.executable, target_script] + sys.argv[1:])
    sys.exit(res.returncode)

if __name__ == "__main__":
    main()
