# Licensed under the MIT License.
# Copyright 2024 RokctAI

import os
import re
import sys
import difflib
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# --- Duplication & Classifications (formerly update_classifications.py) ---

def is_duplicate_theme(new_theme, existing_themes_path, threshold=0.8):
    if not os.path.exists(existing_themes_path):
        return False, ""

    with open(existing_themes_path, 'r', encoding='utf-8') as f:
        existing_themes = [line.strip() for line in f.readlines() if line.strip()]

    for existing in existing_themes:
        similarity = difflib.SequenceMatcher(None, new_theme.lower(), existing.lower()).ratio()
        if similarity >= threshold:
            return True, existing

    return False, ""

def update_classifications():
    """Generates classification reference files for factory books."""
    print("🏷️ Updating Factory Classifications...")

    config_dir = Path('.rokct/config/classifications')
    config_dir.mkdir(parents=True, exist_ok=True)

    job_dir = Path('.rokct/agent/jobs/pending')
    themes = set()
    genres = set()

    if job_dir.exists():
        for f in job_dir.glob('*.md'):
            if f.name == 'template.md': continue
            with open(f, 'r') as content:
                text = content.read()
                theme_match = re.search(r'theme:\s*(.*)', text)
                if theme_match: themes.add(theme_match.group(1).strip())

                genre_match = re.search(r'type:\s*(.*)', text)
                if genre_match: genres.add(genre_match.group(1).strip())

    save_list(config_dir / 'factory_themes.txt', themes)
    save_list(config_dir / 'factory_genres.txt', genres)

def save_list(path, items):
    clean_items = sorted(list(set([i.strip() for i in items if i.strip()])))
    with open(path, 'w') as f:
        f.write('\n'.join(clean_items))
    print(f"✅ Saved {path.name} ({len(clean_items)} entries)")

# --- Production Kits (formerly response_kits.py) ---

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

        if "concept_status: approved" in content.lower():
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
                with open(book_path / 'metadata.md', 'w') as p:
                    p.write(f"---\nid: {book_id}\ntitle: {book_title}\nstatus: production\n---")
                print(f"✅ Created Production Kit: {book_path.name}")

# --- Helper fields extractor/mutator ---

def get_field(content, field):
    match = re.search(rf'^{field}:[ \t]*(.*)', content, re.MULTILINE)
    return match.group(1).split('#')[0].strip() if match else ""

def set_field(content, field, value):
    if re.search(rf'^{field}:', content, re.MULTILINE):
        return re.sub(rf'^{field}:.*', f'{field}: {value}', content, flags=re.MULTILINE)
    else:
        if '---' in content:
            parts = content.rsplit('---', 1)
            return f"{parts[0]}{field}: {value}\n---{parts[1]}"
        return f"{content}\n{field}: {value}"

# --- Lock/Claim logic (formerly lock_job.py) ---

def run_lock(args):
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File {args.file} not found.")
        sys.exit(1)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    session_id = get_field(content, "session_id")
    session_started = get_field(content, "session_started")
    now = datetime.utcnow()

    if args.action == "check":
        print(session_id)
        sys.exit(0 if not session_id else 1)
    elif args.action == "release":
        content = set_field(content, "session_id", "")
        content = set_field(content, "session_started", "")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Lock released.")
        sys.exit(0)
    elif args.action == "claim":
        is_stale = False
        if session_started:
            try:
                start_time = datetime.strptime(session_started, "%Y-%m-%d %H:%M:%S")
                if now - start_time > timedelta(hours=6):
                    is_stale = True
            except ValueError:
                is_stale = True

        if not session_id or is_stale:
            if not args.session:
                print("Error: --session required for claim action.")
                sys.exit(1)
            content = set_field(content, "session_id", args.session)
            content = set_field(content, "session_started", now.strftime("%Y-%m-%d %H:%M:%S"))
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Lock claimed with session {args.session}.")
            sys.exit(0)
        else:
            print(f"LOCKED by session {session_id}")
            sys.exit(1)

# --- Status transition validation (formerly update_status.py) ---

ALLOWED_TRANSITIONS = {
    "theme_generated": ["pending_approval", "failed", "stalled"],
    "idea_generated": ["pending_approval", "failed", "stalled"],
    "pending_approval": ["concept_expanding", "declined", "failed", "stalled"],
    "concept_expanding": ["concept_generated", "failed", "stalled"],
    "concept_generated": ["pending_concept_approval", "failed", "stalled"],
    "pending_concept_approval": ["rules_generating", "declined", "failed", "stalled"],
    "rules_generating": ["rules_generated", "failed", "stalled"],
    "rules_generated": ["pending_rules_approval", "failed", "stalled"],
    "pending_rules_approval": ["writing", "declined", "failed", "stalled"],
    "writing": ["evaluating", "failed", "stalled"],
    "evaluating": ["draft_ready", "writing", "failed", "stalled"],
    "draft_ready": ["pending_acceptance", "failed", "stalled"],
    "pending_acceptance": ["publishing", "writing", "failed", "stalled"],
    "publishing": ["published", "failed", "stalled"],
    "declined": ["failed", "stalled"],
    "failed": ["writing", "stalled"],
    "stalled": ["writing", "failed"]
}

VISUALS_TRANSITIONS = {
    "pending": ["summarizing", "reel_briefing"],
    "summarizing": ["briefing"],
    "briefing": ["rendering"],
    "rendering": ["done"],
    "reel_pending": ["reel_briefing"],
    "reel_briefing": ["reel_rendering"],
    "reel_rendering": ["reel_done"]
}

def run_status(args):
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File {args.file} not found.")
        sys.exit(1)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    now = datetime.now()
    card_id = get_field(content, "id")
    attempts = int(get_field(content, "attempts") or 0)
    log_entries = []

    if args.status:
        current_status = get_field(content, "status")
        if current_status and current_status in ALLOWED_TRANSITIONS:
            if args.status not in ALLOWED_TRANSITIONS[current_status]:
                print(f"Error: Invalid transition from {current_status} to {args.status}")
                sys.exit(1)
        elif current_status:
            if args.status not in ["failed", "stalled"]:
                print(f"Error: Unknown current status {current_status}. Transition to {args.status} rejected.")
                sys.exit(1)

        status_to_write = args.status
        if args.status == "pending_approval":
            status_to_write = f"{args.status} # next step is concept_expanding"
        elif args.status == "pending_concept_approval":
            status_to_write = f"{args.status} # next step is rules_generating"
        elif args.status == "pending_rules_approval":
            status_to_write = f"{args.status} # next step is writing"
        elif args.status == "pending_acceptance":
            status_to_write = f"{args.status} # next step is publishing"

        content = set_field(content, "status", status_to_write)
        log_entries.append(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] {card_id} | {current_status} -> {args.status} | {args.agent}")

    if args.visuals_status:
        is_reel = args.visuals_status.startswith("reel_")
        field = "visuals_reel_status" if is_reel else "visuals_status"
        current_val = get_field(content, field)

        if current_val and current_val in VISUALS_TRANSITIONS:
            if args.visuals_status not in VISUALS_TRANSITIONS[current_val]:
                print(f"Error: Invalid transition from {current_val} to {args.visuals_status}")
                sys.exit(1)

        content = set_field(content, field, args.visuals_status)
        log_entries.append(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] {card_id} | {field}: {current_val} -> {args.visuals_status} | {args.agent}")

    if not args.status and not args.visuals_status:
        print("Error: Either --status or --visuals-status must be provided.")
        sys.exit(1)

    content = set_field(content, "last_updated", now.strftime("%Y-%m-%d %H:%M:%S"))
    content = set_field(content, "attempts", str(attempts + 1))

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    log_path = Path('.rokct/agent/log/transitions.log')
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, 'a', encoding='utf-8') as f:
        for entry in log_entries:
            f.write(entry + "\n")
    print("Status updated successfully.")

# --- CLI entrypoint ---

def main():
    parser = argparse.ArgumentParser(description="Job Card Pipeline Manager.")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Lock command
    lock_parser = subparsers.add_parser("lock", help="Lock/claim or release job card lock")
    lock_parser.add_argument("--file", required=True, help="Path to the job card file")
    lock_parser.add_argument("--action", required=True, choices=["claim", "release", "check"], help="Lock action")
    lock_parser.add_argument("--agent", help="Agent name")
    lock_parser.add_argument("--session", help="Session ID")

    # Status command
    status_parser = subparsers.add_parser("status", help="Update card status with validation")
    status_parser.add_argument("--file", required=True, help="Path to job card file")
    status_parser.add_argument("--status", help="New main pipeline status")
    status_parser.add_argument("--visuals-status", help="New visuals/reel status")
    status_parser.add_argument("--agent", default="system", help="Agent name")

    # Kits command
    subparsers.add_parser("kits", help="Generate response production packages")

    # Classify command
    subparsers.add_parser("classify", help="Update genre/themes classification list")

    args = parser.parse_args()

    if args.command == "lock":
        run_lock(args)
    elif args.command == "status":
        run_status(args)
    elif args.command == "kits":
        generate_response_kits()
    elif args.command == "classify":
        update_classifications()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
