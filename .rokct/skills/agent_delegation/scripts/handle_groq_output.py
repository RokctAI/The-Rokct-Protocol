# Licensed under the MIT License.
# Copyright 2024 RokctAI

import os
import re
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from update_classifications import is_duplicate_theme

def handle_groq_output(level, content):
    """Parses Groq output and performs file operations based on the pipeline level."""
    print(f"🛠️ Processing Groq Output for Level {level}...")

    job_dir = Path('.rokct/agent/jobs/pending')
    job_dir.mkdir(parents=True, exist_ok=True)
    themes_path = Path('.rokct/config/classifications/factory_themes.txt')

    if level == 0:
        # Level 0: Expected output is a list of themes
        # Format: theme | type
        lines = content.strip().split('\n')
        count = 0
        for line in lines:
            if '|' not in line: continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 2: continue

            theme = parts[0]
            book_type = parts[1].lower()

            # Deduplication Check
            is_dup, matched = is_duplicate_theme(theme, str(themes_path))
            if is_dup:
                print(f"⏭️ Skipping duplicate theme: {theme} (similar to: {matched})")
                continue

            # Create a new job card
            hash_str = hashlib.sha256(f"{theme}{book_type}{datetime.now()}".encode()).hexdigest()[:6]
            filename = f"{theme.replace(' ', '_').lower()}_{book_type}_{hash_str}.md"

            card_content = f"""<!-- CARD RULES
     This card is the source of truth for this job.
     Status field controls pipeline progression.
     All status changes must go through update_status.py.
     Direct edits to status field will be rejected by the state machine.
-->
---
id: {theme.replace(' ', '_').lower()}_{hash_str}
theme: {theme}
type: {book_type}
age:
metarules:
guardrail:
idea:
idea_status:
concept:
concept_status:
rules_status:
book_name:
book_path:
status: idea_generated
created: {datetime.now().strftime('%Y-%m-%d')}
last_updated: {datetime.now().strftime('%Y-%m-%d')}
session_id:
session_started:
attempts: 0
last_error:
loop_iterations: 0
max_iterations: 10
---
"""
            with open(job_dir / filename, 'w') as f:
                f.write(card_content)
            print(f"✅ Created job card: {filename}")
            count += 1
        return count > 0

    elif level == 1:
        # Level 1: Expected output is 5 ideas for a specific card
        print("ℹ️ Level 1 Groq output handling: Card update logic.")
        return True

    return False

def main():
    parser = argparse.ArgumentParser(description="Handle Groq output.")
    parser.add_argument("--level", type=int, required=True, help="Pipeline level (0-6)")
    parser.add_argument("--content", required=True, help="Content from Groq")

    args = parser.parse_args()

    success = handle_groq_output(args.level, args.content)
    if not success:
        print("⚠️ No actionable content found in Groq output.")

if __name__ == "__main__":
    main()
