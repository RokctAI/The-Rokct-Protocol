# Licensed under the MIT License.
# Copyright 2024 RokctAI

import argparse
import sys
import re
from pathlib import Path
from datetime import datetime, timedelta

def get_field(content, field):
    match = re.search(rf'^{field}:[ \t]*(.*)', content, re.MULTILINE)
    return match.group(1).strip() if match else ""

def set_field(content, field, value):
    if re.search(rf'^{field}:', content, re.MULTILINE):
        return re.sub(rf'^{field}:.*', f'{field}: {value}', content, flags=re.MULTILINE)
    else:
        if '---' in content:
            parts = content.rsplit('---', 1)
            return f"{parts[0]}{field}: {value}\n---{parts[1]}"
        return f"{content}\n{field}: {value}"

def lock_job():
    parser = argparse.ArgumentParser(description="Claim or release a lock on a job card.")
    parser.add_argument("--file", required=True, help="Path to the job card file")
    parser.add_argument("--action", required=True, choices=["claim", "release", "check"], help="Action to perform")
    parser.add_argument("--agent", help="Agent name (Unused in new schema but kept for compat)")
    parser.add_argument("--session", help="Session ID (required for claim)")

    args = parser.parse_args()
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

if __name__ == "__main__":
    lock_job()
