# Licensed under the MIT License.
# Copyright 2026 RokctAI

import os
import re
import urllib.parse
from pathlib import Path
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import sys

# Bulletproof print override to handle Windows console encoding issues gracefully
def safe_print(*args, sep=' ', end='\n', file=sys.stdout, flush=False):
    str_args = [str(arg) for arg in args]
    text = sep.join(str_args) + end
    try:
        file.write(text)
        if flush:
            file.flush()
    except UnicodeEncodeError:
        encoding = getattr(file, 'encoding', None) or 'utf-8'
        safe_text = text.encode(encoding, errors='replace').decode(encoding)
        try:
            file.write(safe_text)
            if flush:
                file.flush()
        except Exception:
            pass
    except Exception:
        pass

import builtins
builtins.print = safe_print

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve()
while not (BASE_DIR / '.rokct').exists():
    BASE_DIR = BASE_DIR.parent

TARGET_REGISTRIES = [
    BASE_DIR / "01_equity",
    BASE_DIR / "02_grants",
    BASE_DIR / "04_eeip"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Threading Lock for safe counter incrementing
STATS_LOCK = threading.Lock()
TOTAL_SCANNED = 0
TOTAL_DOWNGRADED = 0

def is_definitive_dead(url):
    """
    Tests a URL and returns a tuple (is_dead, reason, status_code).
    WAF/IP blocks (403, 429) or transient SSL/timeout issues are NOT considered definitive dead links.
    Definitive dead links are 404 Not Found, DNS failure, or connection refused.
    """
    try:
        # Use GET with stream=True so we only fetch headers and don't download large payloads
        response = requests.get(url, headers=HEADERS, timeout=10, stream=True)
        
        status = response.status_code
        if status == 404:
            return True, "Definitive 404 Not Found", status
        
        if status == 410:
            return True, "Definitive 410 Gone", status
            
        if status in [401, 403, 429]:
            # This is a soft block/WAF issue in GitHub VMs
            return False, f"WAF / Bot Mitigation Block (Soft Warning)", status
            
        return False, "Live / Accessible", status
        
    except requests.exceptions.ConnectionError as ce:
        err_str = str(ce).lower()
        if "name or service not known" in err_str or "failed to resolve" in err_str or "gaierror" in err_str or "nosuchhost" in err_str:
            return True, "DNS Name Resolution Failure", None
        if "connection refused" in err_str:
            return True, "Connection Refused", None
        return False, f"Connection Error (Soft Warning: {type(ce).__name__})", None
        
    except requests.exceptions.Timeout:
        return False, "Connection Timeout (Soft Warning)", None
    except requests.exceptions.SSLError:
        return False, "SSL Verification Error (Soft Warning)", None
    except Exception as e:
        return False, f"Unknown Error (Soft Warning: {type(e).__name__})", None

def check_main_domain(url):
    """
    Checks if the main root domain of the URL is live/accessible.
    Returns the root domain URL if it is live, else None.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if not parsed.netloc:
            return None
        main_domain = f"{parsed.scheme}://{parsed.netloc}/"
        if url.strip('/') == main_domain.strip('/'):
            return None
            
        response = requests.get(main_domain, headers=HEADERS, timeout=8, stream=True)
        if response.status_code in [200, 301, 302, 401, 403, 429]:
            return main_domain
    except Exception:
        pass
    return None

def check_and_update_card(path):
    """Parses a markdown card, extracts links, tests them, and downgrades status if dead."""
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"  [Error reading] {path.name}: {e}")
        return False

    # Skip files that don't have verification status
    if "Verification Status**:" not in content:
        return False

    # Extract all link fields using regex
    # Matches patterns like: - **Apply Link**: http://... or - **Source**: http://...
    link_fields = re.findall(r'-\s*\*\*(Website|Applying Link|Apply Link|Source|Source / Verification)\*\*:\s*(https?://[^\s\)]+)', content)
    
    if not link_fields:
        return False

    is_downgraded = False
    downgrade_reason = ""
    dead_url = ""

    for field, url in link_fields:
        url = url.strip()
        if not url.startswith("http"):
            continue
            
        is_dead, reason, status_code = is_definitive_dead(url)
        if is_dead:
            is_downgraded = True
            downgrade_reason = reason
            dead_url = url
            
            # Check if root domain is still live
            main_live = check_main_domain(url)
            if main_live:
                downgrade_reason += f" (Main domain is live: {main_live})"
            break  # Any definitive dead link triggers a downgrade

    if is_downgraded:
        # Find existing status
        status_match = re.search(r'(Verification Status\*\*:\s*)(VERIFIED|IN_PROGRESS|UNVERIFIED)', content)
        if status_match and status_match.group(2) != "UNVERIFIED":
            # Upgrade status to UNVERIFIED
            content = re.sub(
                r'Verification Status\*\*:\s*(VERIFIED|IN_PROGRESS)',
                'Verification Status**: UNVERIFIED',
                content
            )
            # Update Last Verified date
            today = datetime.now().strftime('%Y-%m-%d')
            content = re.sub(
                r'Last Verified\*\*:\s*[^\n]+',
                f'Last Verified**: {today}',
                content
            )
            
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                # Removed emojis to prevent print codec errors in PowerShell / Command Prompt
                print(f"[DOWNGRADED] {path.relative_to(BASE_DIR)} due to: {downgrade_reason} ({dead_url})")
                return True
            except Exception as e:
                print(f"  [Error writing] {path.name}: {e}")
        else:
            # Already unverified, no change needed but log it
            print(f"[Already Unverified] {path.relative_to(BASE_DIR)}: {dead_url} ({downgrade_reason})")
            
    return False

def audit_file(card_file):
    global TOTAL_SCANNED, TOTAL_DOWNGRADED
    fname = card_file.name.lower()
    if fname in ['template.md', 'readme.md', 'registry_audit_log.md'] or fname.startswith('registry_'):
        return
        
    with STATS_LOCK:
        TOTAL_SCANNED += 1
        
    try:
        did_downgrade = check_and_update_card(card_file)
        if did_downgrade:
            with STATS_LOCK:
                TOTAL_DOWNGRADED += 1
    except Exception as e:
        print(f"  [Error processing] {card_file.name}: {e}")

def main():
    print("==================================================")
    print("Opportunities Registry Concurrently Audited CI Link Checker")
    print("==================================================")
    
    # Collect all markdown files to check
    all_files = []
    for registry_dir in TARGET_REGISTRIES:
        if not registry_dir.exists():
            continue
        all_files.extend(list(registry_dir.rglob("*.md")))
        
    print(f"Total potential files gathered: {len(all_files)}")
    print("Running link audit concurrently with thread pool...")
    
    # Run with a thread pool of 35 threads for extremely fast, low-overhead link checks
    with ThreadPoolExecutor(max_workers=35) as executor:
        futures = {executor.submit(audit_file, f): f for f in all_files}
        for future in as_completed(futures):
            future.result()
                
    print("\n==================================================")
    print("CI Link Audit Summary:")
    print(f"  Total Cards Audited: {TOTAL_SCANNED}")
    print(f"  Total Cards Downgraded to UNVERIFIED: {TOTAL_DOWNGRADED}")
    print("==================================================")

if __name__ == "__main__":
    main()
