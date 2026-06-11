# Licensed under the MIT License.
# Copyright 2024 RokctAI

import re
from pathlib import Path
from healers import heal_equity_flags

# --- THE GOLDEN DEFAULTS ---
DEFAULT_AI_BLOCK = """- [ ] Review Tender Documents | 1
- [ ] Prepare Initial Response | 3"""

# --- THE WHITELIST (Only aggregate these for the JSON) ---
# We use 'Flag' instead of 'Country' for more deterministic counting
INTERESTING_KEYS = [
    "Category", "Tender Type", "Province", "Institution", # Tenders
    "Industry", "Territory", "Funder Type", "Funding Type", "Flag", # Equity
    "Focus Area", # Grants
    "Multinational Company", "Investment / Funding Type", "Application Status" # EEIP
]

def scan_registry(name, path, base_dir):
    """Scans a directory with Multi-Tag splitting and ISO Flag aggregation."""
    total = 0
    verified = 0
    stats_aggregation = {} 
    advanced_tenders = {}
    todo_list = []
    
    if not path.exists():
        return 0, 0, {}, {}, []

    for file in path.rglob('*.md'):
        fname = file.name.lower()
        if fname in ['template.md', 'readme.md', 'registry_audit_log.md'] or fname.startswith('registry_') or fname.endswith('_content.md'):
            continue
        
        total += 1
        try:
            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # 1. Healing Step
                if name == "Equity":
                    content = heal_equity_flags(file, content)

                # 2. Verification Logic
                is_active = re.search(r'-\s+\*\*Status\*\*:\s*ACTIVE', content, re.I)
                is_verified = re.search(r'Verification Status\*\*:\s*VERIFIED', content, re.I)
                has_date = re.search(r'-\s+\*\*Last Verified\*\*:\s*\d{4}-\d{2}-\d{2}', content, re.I)
                
                # Strict verification for Equity/Grants (must have VERIFIED status)
                # Tenders are verified if active and have a date (legacy logic)
                is_v = False
                if name == "Tenders":
                    is_v = is_active or is_verified or has_date
                else:
                    is_v = is_verified

                if is_v:
                    verified += 1
                
                # 3. Multi-Tag Metadata Extraction (Only for Verified Entries)
                if is_v:
                    stat_matches = re.finditer(r'-\s+\*\*(?P<key>.*?)\*\*:\s*(?P<val>.*)', content)
                    for m in stat_matches:
                        key = m.group('key').strip()
                        val = m.group('val').strip()
                        
                        if key in INTERESTING_KEYS:
                            if key not in stats_aggregation: stats_aggregation[key] = {}

                            # Split by slash for multi-tag support
                            tags = [t.strip() for t in val.split('/')] if "/" in val else [val]

                            for tag in tags:
                                if tag: # Don't count empty tags
                                    stats_aggregation[key][tag] = stats_aggregation[key].get(tag, 0) + 1

                # 4. Tender AI Logic
                if name == "Tenders":
                    match = re.search(r'## AI Checklist \(Jules\)[\s\S]*?-->\s*([\s\S]*)$', content)
                    if match:
                        current_tasks = match.group(1).strip()
                        if current_tasks != DEFAULT_AI_BLOCK and len(current_tasks) > 10:
                            advanced_tenders[file.stem] = {
                                "enrichment": "ADVANCED",
                                "tasks": [t.strip('- [ ]').strip() for t in current_tasks.splitlines() if t.strip()]
                            }
                        else:
                            todo_list.append(str(file.relative_to(base_dir)))

                # 5. Equity / Grants / EEIP Unverified Logic
                if name in ["Equity", "Grants", "EEIP"]:
                    if "Verification Status**: UNVERIFIED" in content or "Verification Status**: IN_PROGRESS" in content:
                        todo_list.append(str(file.relative_to(base_dir)))
                            
        except Exception:
            continue
                
    return total, verified, stats_aggregation, advanced_tenders, todo_list
