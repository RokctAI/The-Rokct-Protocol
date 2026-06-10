# Licensed under the MIT License.
# Copyright 2024 RokctAI

import requests
import re
import os
from pathlib import Path

def check_link_health():
    """Scans book jobs for broken links."""
    print("🔍 Starting Global Job Link Health Check...")

    # Target book draft directories
    directories = [Path('books/drafts')]
    broken_count = 0
    checked_count = 0

    for directory in directories:
        if not directory.exists(): continue
        print(f"📂 Auditing {directory.name}...")

        # Scan all markdown files in book subdirectories
        for md_file in directory.rglob('*.md'):
            if md_file.name in ['template.md', 'metadata.md']:
                continue

            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Pattern to find URLs in markdown links [text](url) or standing alone
            links = re.findall(r'\(https?://[^\s\)]+\)|https?://[^\s\n\)]+', content)

            file_broken = False
            for link in links:
                url = link.strip('() ')

                checked_count += 1
                try:
                    # Use a short timeout and allow redirects
                    response = requests.head(url, timeout=15, allow_redirects=True)
                    # 403 Forbidden is often a bot block, so we only flag >= 404
                    if response.status_code >= 404:
                        print(f"❌ Broken Link in {md_file.name}: {url} (Status: {response.status_code})")
                        file_broken = True
                        broken_count += 1
                except:
                    # Connection errors are often temporary or firewall blocks,
                    # but we flag for steward review.
                    print(f"⚠️ Connection Error in {md_file.name}: {url}")
                    file_broken = True
                    broken_count += 1

            if file_broken:
                # Mark status as BROKEN in the file if not already marked
                if "Status: BROKEN" not in content and "Verification Status: BROKEN" not in content:
                    updated = content.replace("Status: ACTIVE", "Status: BROKEN")
                    updated = updated.replace("Verification Status: VERIFIED", "Verification Status: BROKEN")
                    updated = updated.replace("Verification Status: IN_PROGRESS", "Verification Status: BROKEN")
                    with open(md_file, 'w', encoding='utf-8') as f:
                        f.write(updated)

    print(f"🏁 Health check complete. Checked {checked_count} links. Found {broken_count} issues.")

if __name__ == "__main__":
    check_link_health()
