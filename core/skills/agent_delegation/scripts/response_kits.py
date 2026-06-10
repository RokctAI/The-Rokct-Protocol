# Licensed under the MIT License.
# Copyright 2024 RokctAI

import os
import re
from pathlib import Path

# Ported from opportunities: Adapt for 'factory' book context
def generate_response_kits():
    """Generates a starting production package for approved concepts."""
    print("📂 Checking for Jobs ready for Production Kits...")

    job_dir = Path('.rokct/agent/jobs/pending')
    drafts_dir = Path('books/drafts')

    if not job_dir.exists(): return

    for md_file in job_dir.glob('*.md'):
        if md_file.name == 'template.md': continue
        with open(md_file, 'r') as f:
            content = f.read()

        # Create kits for jobs that have approved concepts
        if "concept_status: approved" in content.lower():
            # Extract metadata
            title_match = re.search(r'book_name:\s*(.*)', content)
            id_match = re.search(r'id:\s*(.*)', content)

            if not title_match or not id_match: continue

            book_id = id_match.group(1).strip()
            book_title = title_match.group(1).strip()
            if not book_title: book_title = book_id

            safe_name = "".join([c if c.isalnum() else "_" for c in book_title])[:50]

            book_path = drafts_dir / f"{book_id}_{safe_name}"
            if not book_path.exists():
                book_path.mkdir(parents=True, exist_ok=True)

                # Copy template files (logic would be expanded to actually copy)
                # For now, we create foundational placeholders
                with open(book_path / 'metadata.md', 'w') as p:
                    p.write(f"---\nid: {book_id}\ntitle: {book_title}\nstatus: production\n---")

                print(f"✅ Created Production Kit: {book_path.name}")

if __name__ == "__main__":
    generate_response_kits()
