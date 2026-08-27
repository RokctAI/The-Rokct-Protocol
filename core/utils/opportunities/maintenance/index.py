# Copyright (c) 2026 ROKCT INTELLIGENCE (PTY) LTD
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Licensed under the MIT License.
# Copyright 2024 ROKCT INTELLIGENCE (PTY) LTD
# compliance-ignore-file: structural-special-dirs
# These scripts live under .rokct/ ONLY at runtime: initiate.py fetches
# this canonical copy from The-Rokct-Protocol into .rokct/skills/ at the
# start of a workflow run, and end_protocol.py deletes it at the end.
# Nothing here is committed under .rokct/ in this repo (that path is
# gitignored) - this IS the checked-in source, at its permanent,
# allowed location.

import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
import json

# Add utils to path
sys.path.append(str(Path(__file__).parent.parent / "tenders" / "utils"))
from tender_resolver import resolve_card_path

# --- CONFIGURATION ---
# Walk up to the real repo root instead of a fixed parent-count: this script
# is invoked from more than one on-disk depth (the canonical
# .rokct/skills/.rok/opportunities_registry/scripts/ path, and the
# self-relocated .rokct/tmp/opportunities/ cache path used by
# registry_orchestrator/index.py's wrapper), and a fixed .parent chain
# silently lands one level short (inside .rokct/) for the latter.
BASE_DIR = Path(__file__).resolve()
while not (BASE_DIR / ".rokct").exists():
    BASE_DIR = BASE_DIR.parent
TENDER_DIR = BASE_DIR / "03_tenders"
GRANT_DIR = BASE_DIR / "02_grants"
QUEUE_DIR = BASE_DIR / ".rokct" / "agent" / "queue"


def purge_expired():
    """Removes tenders and grants that have passed their deadlines."""
    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] [Maintenance] Purging expired entries..."
    )
    now = datetime.now()
    count = 0

    # Purge Tenders
    # We need to find all unique tender IDs first to avoid double processing or missing folder structures
    tender_ids = set()
    for item in TENDER_DIR.iterdir():
        if item.is_file() and item.suffix == ".md":
            if item.name in [
                "template.md",
                "registry_audit_log.md",
            ] or item.name.startswith("registry_"):
                continue
            tender_ids.add(item.stem)
        elif item.is_dir():
            # If it's a directory, we check if it follows the folder structure {tender_id}/{tender_id}.md
            if (item / f"{item.name}.md").exists():
                tender_ids.add(item.name)

    for tender_id in tender_ids:
        card_path = resolve_card_path(TENDER_DIR, tender_id)
        if not card_path or not card_path.exists():
            continue

        with open(card_path, "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(
                r"-\s+\*\*Closing Date\*\*:\s*(\d{4}-\d{2}-\d{2})", content
            )
            if match and datetime.strptime(match.group(1), "%Y-%m-%d") < now:
                # If it's in a folder, delete the entire folder
                if card_path.parent != TENDER_DIR:
                    shutil.rmtree(card_path.parent)
                else:
                    os.remove(card_path)
                count += 1

    print(f"  [Status] Purged {count} expired items.")


def queue_ai():
    """Queues new tenders for AI analysis."""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    new_tenders = []

    for f in TENDER_DIR.glob("ocds-*.md"):
        with open(f, "r", encoding="utf-8") as content:
            text = content.read()
            if "Status: ACTIVE" in text and "[e.g.," in text:
                new_tenders.append(f.name)

    if new_tenders:
        task = {
            "title": f"Tender Analysis: {datetime.now().strftime('%Y-%m-%d')}",
            "files": new_tenders[:20],
            "instruction": "Verify document requirements and update AI Analysis section.",
        }
        with open(
            QUEUE_DIR / f"ai_queue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "w"
        ) as f:
            json.dump(task, f, indent=2)
        print(f"  [Status] Queued AI task for {len(new_tenders)} items.")


if __name__ == "__main__":
    purge_expired()
    queue_ai()
