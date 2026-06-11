# Licensed under the MIT License.
import os, re
from pathlib import Path
def generate():
    print("[Response Kits] Checking for verified tenders...")
    tenders_dir = Path('03_tenders')
    responses_dir = Path('responses')
    if not tenders_dir.exists(): return
    for f in tenders_dir.glob('ocds-*.md'):
        with open(f, 'r', encoding='utf-8') as content:
            text = content.read()
            if "Verification Status: VERIFIED" in text or "Status: VERIFIED" in text:
                title = re.search(r'# Tender Opportunity:\s*(.+)', text).group(1).strip()
                tid = re.search(r'-\s+\*\*Tender Number\*\*:\s*(.+)', text).group(1).strip()
                kit_dir = responses_dir / f"{tid}_kit"
                if not kit_dir.exists():
                    kit_dir.mkdir(parents=True, exist_ok=True)
                    with open(kit_dir / 'proposal_draft.md', 'w') as p:
                        p.write(f"# Proposal for {title}\n\n## Opportunity {tid}\n- [ ] Draft Response")
                    print(f"  [+] Created Kit for {tid}")
if __name__ == '__main__':
    generate()
