# compliance-ignore-file: structural-special-dirs
import os
import sys
import shutil
import subprocess
import hashlib
import json
import time
import urllib.request
import urllib.error
import http.client

import io
import zipfile

# Pinned by tools/gen_protocol_lock.py - do not edit these constants by hand.
# Every fetch below is pinned to this commit, so what this script downloads is
# immutable; the executable targets are additionally SHA-256 verified against
# EXPECTED_SHA256 before they are written anywhere.
PROTOCOL_REF = "ab78bedfc5ca981d0170310dc88c3a328134eb58"
EXPECTED_SHA256 = {
    "profiles/local/initiate.py": "de86f15f1ed7e11870f47a7f6164ff6b034818eb97690ba5252d9b08e2b55aa7",
    "workflows/maintenance.yml": "3826ea73fee8b939c0798ae65173fb0ff6dd188758e4564b51373019bc7a7716",
}
GITHUB_RAW_BASE = f"https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/{PROTOCOL_REF}"
GITHUB_ZIP_BASE = f"https://github.com/RokctAI/The-Rokct-Protocol/archive/{PROTOCOL_REF}.zip"
GITHUB_ZIP_PREFIX = f"The-Rokct-Protocol-{PROTOCOL_REF}"
PROTOCOL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) if "profiles" in os.path.abspath(__file__) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.getcwd()
ROKCT_DIR = os.path.join(PROJECT_ROOT, ".rokct")

def check_for_update():
    """Data-only update check. The old self-update fetched initiate.py from
    the mutable main branch and execv'd it - executing unpinned future code,
    which the PROTOCOL_REF pinning exists to prevent. Now we only fetch the
    lockfile from main AS DATA, compare its pinned ref to ours, and tell the
    user to re-run the installer. Nothing fetched here is ever executed."""
    if os.environ.get("CI"):
        # CI must run the committed copy deterministically.
        return
    url = "https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/protocol.lock.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "X-Trace-Id": "initiate-bootstrap"})
        with urllib.request.urlopen(req, timeout=10) as r:
            latest_ref = json.loads(r.read().decode()).get("ref", "")
        if latest_ref and latest_ref != PROTOCOL_REF:
            print("[init] A newer protocol version is available - re-run the installer to update.")
    except Exception as e:
        print(f"[init] Update check failed: {e}", file=sys.stderr)

def verify_pinned(rel_posix, data):
    """SHA-256 check for the executable fetch targets, before any write."""
    expected = EXPECTED_SHA256.get(rel_posix)
    if expected is None:
        return
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected:
        print(f"[init] Integrity check failed for {rel_posix} (ref {PROTOCOL_REF}):", file=sys.stderr)
        print(f"[init]   expected sha256 {expected}", file=sys.stderr)
        print(f"[init]   actual   sha256 {digest}", file=sys.stderr)
        print("[init] Refusing to install unverified code.", file=sys.stderr)
        sys.exit(1)

# Bounded retry for transient network failures (connection resets, timeouts,
# 429/5xx): 4 attempts with 2s/4s/8s backoff. Definitive HTTP errors such as
# 404 or 401/403 still fail fast - retrying cannot fix those.
FETCH_ATTEMPTS = 4
TRANSIENT_HTTP_CODES = (429, 500, 502, 503, 504)

def fetch_url(url):
    """GET url, retrying transient errors; raises the last error when out of
    attempts (with e.fetch_attempts set so callers can report the count)."""
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "X-Trace-Id": "initiate-bootstrap"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in TRANSIENT_HTTP_CODES or attempt == FETCH_ATTEMPTS:
                e.fetch_attempts = attempt
                raise
            err = e
        except (urllib.error.URLError, http.client.HTTPException, ConnectionError, TimeoutError) as e:
            if attempt == FETCH_ATTEMPTS:
                e.fetch_attempts = attempt
                raise
            err = e
        delay = 2 ** attempt
        print(f"[init] Transient error fetching {url} (attempt {attempt}/{FETCH_ATTEMPTS}): {err} - retrying in {delay}s", file=sys.stderr)
        time.sleep(delay)

def fetch_from_github(rel_path, dest_path):
    rel_posix = rel_path.replace(os.sep, "/")
    url = f"{GITHUB_RAW_BASE}/{rel_posix}"
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    try:
        data = fetch_url(url)
    except Exception as e:
        print(f"[init] Failed to fetch {rel_path} after {getattr(e, 'fetch_attempts', 1)} attempt(s): {e}", file=sys.stderr)
        sys.exit(1)
    verify_pinned(rel_posix, data)
    with open(dest_path, "wb") as f:
        f.write(data)
    print(f"[init] Fetched {rel_path}")

def ensure_file(rel_path, dest_path):
    src = os.path.join(PROTOCOL_DIR, rel_path)
    if os.path.exists(dest_path):
        if os.path.exists(src) and file_hash(src) == file_hash(dest_path):
            return
    if os.path.exists(src):
        shutil.copy2(src, dest_path)
        print(f"[init] Updated {rel_path}")
    else:
        fetch_from_github(rel_path, dest_path)

def file_hash(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]

def copy_versioned(src_rel, dst_abs):
    src = os.path.join(PROTOCOL_DIR, src_rel)
    manifest_path = os.path.join(PROTOCOL_DIR, "core", "templates", "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as mf:
            manifest = json.load(mf)
    else:
        try:
            manifest = json.loads(fetch_url(f"{GITHUB_RAW_BASE}/core/templates/manifest.json").decode())
        except Exception:
            manifest = {}
    entry = manifest.get("files", {}).get(src_rel.split("core/templates/")[-1] if "core/templates/" in src_rel else src_rel.split("profiles/local/")[-1])
    if not entry or not os.path.exists(src):
        fetch_from_github(src_rel, dst_abs)
        return
    current_hash = file_hash(dst_abs)
    if current_hash and current_hash == entry.get("hash"):
        return
    shutil.copy2(src, dst_abs)

def copy_dir(rel_src, dst):
    src = os.path.join(PROTOCOL_DIR, rel_src)
    if not os.path.isdir(src):
        fetch_dir_from_github(rel_src, dst)
        return
    os.makedirs(dst, exist_ok=True)
    for item in os.listdir(src):
        # Skip sync files, maintenance, and the init guide - handled separately or not needed in .rokct
        if item in ("sync_workspace.py", "sync_workspace.yml", "maintenance.yml", "init_protocol.md", ".rok"):
            continue
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copy_dir(os.path.relpath(s, PROTOCOL_DIR), d)
        else:
            rel = os.path.relpath(s, PROTOCOL_DIR)
            ensure_file(rel, d)

def fetch_dir_from_github(rel_src, dst):
    # Zip entries always use forward slashes; on Windows callers pass
    # os.sep-separated paths (e.g. from os.path.relpath), which would
    # match no entries and silently fetch 0 files.
    rel_src = rel_src.replace(os.sep, "/")
    prefix = f"{GITHUB_ZIP_PREFIX}/{rel_src}/"
    try:
        print(f"[init] Fetching directory from GitHub: {rel_src}")
        z = zipfile.ZipFile(io.BytesIO(fetch_url(GITHUB_ZIP_BASE)))
        os.makedirs(dst, exist_ok=True)
        count = 0
        for name in z.namelist():
            if name.startswith(prefix) and not name.endswith("/"):
                rel = name[len(prefix):]
                if rel_src == "workflows" and (rel in ("sync_workspace.py", "sync_workspace.yml", "maintenance.yml") or rel.startswith(".rok/")):
                    continue
                data = z.read(name)
                verify_pinned(f"{rel_src}/{rel}", data)
                dest = os.path.join(dst, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(data)
                count += 1
        print(f"[init] Fetched {count} files from {rel_src}")
    except Exception as e:
        print(f"[init] Failed to fetch directory {rel_src} after {getattr(e, 'fetch_attempts', 1)} attempt(s): {e}", file=sys.stderr)

def main():
    check_for_update()
    os.makedirs(ROKCT_DIR, exist_ok=True)

    templates = ["memory.md", "decision_log.md", "project_map.md", "active_session.txt"]
    for t in templates:
        dest_t = os.path.join(ROKCT_DIR, t)
        if not os.path.exists(dest_t):
            ensure_file(f"core/templates/{t}", dest_t)

    ensure_file(".cursorrules", os.path.join(PROJECT_ROOT, ".cursorrules"))

    copy_dir("core/skills", os.path.join(ROKCT_DIR, "skills"))
    try:
        origin_url = subprocess.check_output(["git", "config", "--get", "remote.origin.url"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        origin_url = ""
    if "RokctAI/" in origin_url:
        copy_dir("profiles/local/skills", os.path.join(ROKCT_DIR, "skills"))
        # For RokctAI repos, we already copied .rok via copy_dir("core/skills")
    else:
        # For non-RokctAI repos, remove .rok from skills
        rok_path = os.path.join(ROKCT_DIR, "skills", ".rok")
        if os.path.isdir(rok_path):
            shutil.rmtree(rok_path)
            print("[init] Removed .rok skill (non-RokctAI repo)")

    # Distribution of Protocol-only (RokctAI) workflows
    if "RokctAI/" in origin_url:
        rok_workflows_src = os.path.join(PROTOCOL_DIR, "workflows", ".rok")
        temp_rok_workflows = os.path.join(ROKCT_DIR, "workflows", ".rok")
        if not os.path.isdir(rok_workflows_src):
            fetch_dir_from_github("workflows/.rok", temp_rok_workflows)
            src_dir = temp_rok_workflows
        else:
            src_dir = rok_workflows_src

        if os.path.isdir(src_dir):
            dst_workflows = os.path.join(PROJECT_ROOT, ".github", "workflows")
            os.makedirs(dst_workflows, exist_ok=True)
            for item in os.listdir(src_dir):
                src_file = os.path.join(src_dir, item)
                if os.path.isfile(src_file):
                    shutil.copy2(src_file, os.path.join(dst_workflows, item))
                    print(f"[init] Deployed Protocol workflow: {item}")
            if src_dir == temp_rok_workflows and os.path.isdir(temp_rok_workflows):
                shutil.rmtree(temp_rok_workflows)
                print("[init] Cleaned up temporary workflows/.rok directory")

    ensure_file("profiles/local/rules.md", os.path.join(ROKCT_DIR, "profiles.md"))

    copy_dir("profiles/local/workflows", os.path.join(ROKCT_DIR, "workflows"))
    copy_dir("workflows", os.path.join(ROKCT_DIR, "workflows"))
    # Removed ensure_file("workflows/reinit_protocol.md", ...) as it was deleted and replaced by init_protocol.md


    try:
        email = subprocess.check_output(["git", "config", "user.email"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        email = ""
    if email:
        prefix = email.split("@")[0].replace(".", "").lower()
        domain = email.split("@")[1].lower()
        domain_hash = hashlib.md5(domain.encode()).hexdigest()[:6]
        safe_id = f"{prefix}.{domain_hash}"
        mem = os.path.join(ROKCT_DIR, "memory.md")
        existing_mem_content = ""
        if os.path.exists(mem):
            with open(mem, "r", encoding="utf-8") as f:
                existing_mem_content = f.read()
        if safe_id not in existing_mem_content:
            with open(mem, "a", encoding="utf-8") as f:
                f.write(f"\n\n## Safe ID\n{safe_id}\n")
            print(f"[init] Registered safe identity: {safe_id}")

    ignore = os.path.join(ROKCT_DIR, ".gitignore")
    if not os.path.exists(ignore):
        with open(ignore, "w", encoding="utf-8") as f:
            f.write("skills/\n")
        print("[init] Created .gitignore")
    else:
        txt = open(ignore, "r", encoding="utf-8").read()
        if "skills/" not in txt:
            with open(ignore, "a", encoding="utf-8") as f:
                f.write("skills/\n")
            print("[init] Updated .gitignore")

    ensure_file("workflows/sync_workspace.py", os.path.join(ROKCT_DIR, "sync_workspace.py"))
    ensure_file("workflows/sync_workspace.yml", os.path.join(PROJECT_ROOT, ".github", "workflows", "sync_workspace.yml"))
    ensure_file("profiles/local/end_protocol.py", os.path.join(ROKCT_DIR, "end_protocol.py"))
    # Don't copy initiate.py to itself if already running from .rokct/
    dest_initiate = os.path.join(ROKCT_DIR, "initiate.py")
    src_initiate = "profiles/local/initiate.py"
    if os.path.abspath(__file__) != dest_initiate:
        ensure_file(src_initiate, dest_initiate)
    print("[init] Copied initiate.py -> .rokct/initiate.py")
    
    cfg = os.path.join(ROKCT_DIR, ".workspace_config.json")
    if not os.path.exists(cfg):
        try:
            url = subprocess.check_output(["git", "config", "--get", "remote.origin.url"], text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            url = ""
        if "RokctAI/" in url:
            parent = "RokctAI/occultation"
            print(f"[init] Auto-detected RokctAI repo, routing to {parent}")
        else:
            parent = input("[init] Enter parent workspace repo (owner/repo) or press Enter for standalone: ").strip()
        if parent:
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump({"parent_repo": parent, "parent_branch": "main", "working_files": templates}, f, indent=2)
            print(f"[init] Created .workspace_config.json -> {parent}")
        else:
            print("[init] Standalone mode (no workspace sync)")
            # Only standalone or parent repos get the maintenance workflow (children don't need it)
            ensure_file("workflows/maintenance.yml", os.path.join(PROJECT_ROOT, ".github", "workflows", "maintenance.yml"))
            print("[init] Installed maintenance workflow for parent/standalone repo")
    else:
        # If config already exists, check if it's a parent (no parent_repo set)
        with open(cfg, "r", encoding="utf-8") as f:
            config_data = json.load(f)
            if not config_data.get("parent_repo"):
                ensure_file("workflows/maintenance.yml", os.path.join(PROJECT_ROOT, ".github", "workflows", "maintenance.yml"))
                print("[init] Verified maintenance workflow for parent/standalone repo")


    print("[init] Local profile init complete.")

if __name__ == "__main__":
    main()


