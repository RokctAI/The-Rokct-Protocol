# compliance-ignore-file: structural-special-dirs
# Licensed under the MIT License.
# Copyright 2024 RokctAI

import os
import re
import json
import difflib
import hashlib
import argparse
from pathlib import Path
from datetime import datetime


def is_duplicate_theme(new_theme, existing_themes_path, threshold=0.8):
    """Fuzzy-match a candidate theme against the recorded factory themes.

    Inlined (not imported from update_classifications) because this module is
    executed from a temp file by the protocol scaffold, where sibling imports
    do not resolve.
    """
    if not os.path.exists(existing_themes_path):
        return False, ""

    with open(existing_themes_path, 'r', encoding='utf-8') as f:
        existing_themes = [line.strip() for line in f.readlines() if line.strip()]

    for existing in existing_themes:
        similarity = difflib.SequenceMatcher(None, new_theme.lower(), existing.lower()).ratio()
        if similarity >= threshold:
            return True, existing

    return False, ""


def set_field(content, field, value):
    """Set a single-line frontmatter field, adding it if missing."""
    if re.search(rf'^{field}:', content, re.MULTILINE):
        return re.sub(rf'^{field}:.*', f'{field}: {value}', content, flags=re.MULTILINE)
    if '---' in content:
        parts = content.rsplit('---', 1)
        return f"{parts[0]}{field}: {value}\n---{parts[1]}"
    return f"{content}\n{field}: {value}"


def set_block_field(content, field, block_text):
    """Replace a frontmatter field (and any indented block under it) with a
    YAML literal block scalar holding block_text."""
    lines = content.split('\n')
    start = None
    for i, line in enumerate(lines):
        if re.match(rf'^{field}:', line):
            start = i
            break

    block_lines = [f"{field}: |"] + [f"  {l}" for l in block_text.strip().split('\n')]

    if start is None:
        # Insert before the closing frontmatter delimiter
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == '---':
                return '\n'.join(lines[:i] + block_lines + lines[i:])
        return content + '\n' + '\n'.join(block_lines)

    end = start + 1
    while end < len(lines) and (lines[end].startswith('  ') or lines[end].strip() == ''):
        # Stop at the frontmatter close even if preceded by blank lines
        if lines[end].strip() == '---':
            break
        end += 1
    return '\n'.join(lines[:start] + block_lines + lines[end:])


def get_field(content, field):
    match = re.search(rf'^{field}:[ \t]*(.*)', content, re.MULTILINE)
    return match.group(1).split('#')[0].strip() if match else ""


def log_transition(card_id, old_status, new_status, agent="groq"):
    log_path = Path('.rokct/agent/log/transitions.log')
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {card_id} | {old_status} -> {new_status} | {agent}\n")


def handle_groq_output(level, content, card_file=None):
    """Parses Groq output and performs file operations based on the pipeline level."""
    # Pipeline processor: transforms LLM thematic output into structured Markdown job cards
    # enforces deduplication against existing factory themes
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
status: theme_generated
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
        # Level 1: Expected output is ideas for a specific card.
        # Writes the ideas into the card and advances it to pending_approval
        # (theme_generated -> pending_approval per the state machine).
        if not card_file or not os.path.exists(card_file):
            print("Error: Level 1 requires --file pointing at an existing job card.")
            return False

        with open(card_file, 'r', encoding='utf-8') as f:
            card = f.read()

        card_id = get_field(card, "id")
        old_status = get_field(card, "status")

        card = set_block_field(card, "idea", content)
        card = set_field(card, "idea_status", "pending")
        card = set_field(card, "status", "pending_approval # next step is concept_expanding")
        card = set_field(card, "last_updated", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        with open(card_file, 'w', encoding='utf-8') as f:
            f.write(card)

        log_transition(card_id, old_status, "pending_approval")
        print(f"✅ Level 1: wrote ideas into {card_file} and set status to pending_approval.")
        return True

    return False


def main():
    parser = argparse.ArgumentParser(description="Handle Groq output.")
    parser.add_argument("--level", type=int, required=True, help="Pipeline level (0-6)")
    parser.add_argument("--content", required=True, help="Content from Groq")
    parser.add_argument("--file", help="Job card file (required for level 1)")

    args = parser.parse_args()

    success = handle_groq_output(args.level, args.content, args.file)
    if not success:
        print("⚠️ No actionable content found in Groq output.")

if __name__ == "__main__":
    main()
