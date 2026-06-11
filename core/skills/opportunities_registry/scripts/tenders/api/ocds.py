# Licensed under the MIT License.
# Copyright 2024 RokctAI

import requests
import re
from datetime import datetime, timedelta
from pathlib import Path
import sys
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Add utils to path
sys.path.append(str(Path(__file__).parent.parent / 'utils'))
from tender_resolver import resolve_card_path, resolve_write_path

def run_sync(tender_dir, sources_dir, generate_md_fn):
    """Resilient OCDS Sync with full parameters."""
    print("[OCDS] Starting API Sync (PageSize: 5000)...")
    
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=Retry(total=5, backoff_factor=2)))
    session.headers.update({'User-Agent': 'Mozilla/5.0 RokctAI-Sync/1.0'})

    configs = []
    if sources_dir.exists():
        for sf in sources_dir.glob('*.md'):
            with open(sf, 'r', encoding='utf-8') as f:
                content = f.read()
                if re.search(r'-\s+\*\*Is API\*\*:\s*true', content, re.I) and 'OCDS' in content:
                    u = re.search(r'URL\*\*:\s*(https?://[^\s\n]+)', content)
                    f_match = re.search(r'Flag\*\*:\s*([A-Z]{2})', content)
                    if u and f_match:
                        configs.append({"url": u.group(1).strip(), "flag": f_match.group(1).strip(), "ref": f"sources/{sf.name}"})
    
    for c in configs:
        now = datetime.now()
        date_to = now.strftime('%Y-%m-%d')
        date_from = (now - timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Include BOTH dateFrom and dateTo for API compliance
        params = {
            "PageNumber": 1, 
            "PageSize": 5000, 
            "dateFrom": date_from, 
            "dateTo": date_to
        }
        
        try:
            resp = session.get(c['url'], params=params, timeout=120)
            resp.raise_for_status()
            releases = resp.json().get('releases', [])
            
            latest_map = {}
            for r in releases:
                ocid = r.get('ocid')
                if ocid and (ocid not in latest_map or r.get('date', '') > latest_map[ocid].get('date', '')):
                    latest_map[ocid] = r
            
            updates = 0
            for ocid, rel in latest_map.items():
                card_path = resolve_card_path(tender_dir, ocid)
                existing = ""
                if card_path and card_path.exists():
                    with open(card_path, 'r', encoding='utf-8') as f:
                        existing = f.read()
                    if "VERIFIED" in existing: continue
                
                new_c = generate_md_fn(rel, c['flag'], c['ref'], existing)
                if [l.strip() for l in existing.splitlines() if l.strip()] != [l.strip() for l in new_c.splitlines() if l.strip()]:
                    write_path = resolve_write_path(tender_dir, ocid)
                    with open(write_path, 'w', encoding='utf-8', newline='\n') as fw: fw.write(new_c)
                    updates += 1
            print(f"  [+] {c['flag']}: {len(releases)} releases. Updated {updates} files.")
        except Exception as e: print(f"  [Error] {c['flag']} Sync: {e}")
