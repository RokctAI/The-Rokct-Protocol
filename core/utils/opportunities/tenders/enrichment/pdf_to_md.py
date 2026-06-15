# Licensed under the MIT License.
# Copyright 2024 RokctAI

import os
import re
import sys
import json
import requests
import pdfplumber
import shutil
from pathlib import Path
from datetime import datetime

# Add utils to path
sys.path.append(str(Path(__file__).parent.parent / 'utils'))
from tender_resolver import resolve_card_path

BASE_DIR = Path(__file__).resolve()
while not (BASE_DIR / '.rokct').exists():
    BASE_DIR = BASE_DIR.parent
TENDER_DIR = BASE_DIR / '03_tenders'
TODO_JSON = BASE_DIR / '.rokct' / 'agent' / 'todo.json'
LOG_FILE = BASE_DIR / '.rokct' / 'agent' / 'logs' / 'pdf_extraction_failures.log'

def log_failure(tender_id, reason):
    """Logs failures to the specified log file."""
    timestamp = datetime.now().isoformat()
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] Tender ID: {tender_id} | Reason: {reason}\n")

def extract_direct_link(card_path):
    """Extracts the Direct Link URL from the tender card."""
    with open(card_path, 'r', encoding='utf-8') as f:
        content = f.read()
        match = re.search(r'-\s+\*\*Direct Link\*\*:\s*(https?://[^\s\n]+)', content)
        if match:
            return match.group(1).strip()
    return None

def get_last_verified_date(card_path):
    """Extracts the Last Verified date from the tender card."""
    with open(card_path, 'r', encoding='utf-8') as f:
        content = f.read()
        match = re.search(r'-\s+\*\*Last Verified\*\*:\s*(\d{4}-\d{2}-\d{2})', content)
        if match:
            try:
                return datetime.strptime(match.group(1), '%Y-%m-%d')
            except ValueError:
                return None
    return None

def process_tender(tender_id):
    try:
        # Normalize tender_id in case it's a full path
        tender_id = Path(tender_id).stem

        card_path = resolve_card_path(TENDER_DIR, tender_id)
        if not card_path:
            return

        direct_link = extract_direct_link(card_path)
        if not direct_link:
            log_failure(tender_id, "No Direct Link found in card")
            return

        # Folder Migration Logic
        if card_path.parent == TENDER_DIR:
            # Flat file, need to migrate
            tender_folder = TENDER_DIR / tender_id
            tender_folder.mkdir(parents=True, exist_ok=True)
            new_card_path = tender_folder / f"{tender_id}.md"
            shutil.move(str(card_path), str(new_card_path))
            card_path = new_card_path
        else:
            tender_folder = card_path.parent

        content_file = tender_folder / f"{tender_id}_content.md"

        # Check if we should overwrite
        if content_file.exists() and content_file.stat().st_size > 0:
            last_verified = get_last_verified_date(card_path)
            content_mtime = datetime.fromtimestamp(content_file.stat().st_mtime)
            if last_verified and last_verified <= content_mtime:
                # Content is up to date
                return

        # Fetch PDF
        try:
            resp = requests.get(direct_link, headers={'X-Trace-Id': 'pdf-to-md'}, timeout=60)
            resp.raise_for_status()
            if 'application/pdf' not in resp.headers.get('Content-Type', '').lower() and not direct_link.lower().endswith('.pdf'):
                # Try to check if it's actually a PDF even if header is missing
                if not resp.content.startswith(b'%PDF'):
                    log_failure(tender_id, f"URL is not a PDF: {direct_link}")
                    return
        except Exception as e:
            log_failure(tender_id, f"Fetch failed: {str(e)}")
            return

        # Convert to Markdown
        try:
            md_content = ""
            import io
            with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        md_content += text + "\n\n"

            if not md_content.strip():
                log_failure(tender_id, "PDF has no extractable text (likely scanned image)")
                return

            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(md_content)

        except Exception as e:
            log_failure(tender_id, f"PDF extraction error: {str(e)}")

    except Exception as e:
        log_failure(tender_id, f"Unexpected error: {str(e)}")

def main():
    # Also check 03_tenders/todo.json as fallback per task description
    todo_path = TODO_JSON
    if not todo_path.exists():
        todo_path = TENDER_DIR / 'todo.json'

    if not todo_path.exists():
        print(f"Todo file not found. Skipping.")
        return

    try:
        with open(todo_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {todo_path}: {e}")
        return

    todo_list = []
    if isinstance(data, list):
        todo_list = data
    elif isinstance(data, dict) and "files" in data:
        todo_list = data["files"]
    else:
        print(f"Invalid format in {todo_path}")
        return

    for item in todo_list:
        # item might be "03_tenders/ocds-xxx.md" or "ocds-xxx"
        tender_id = str(item).replace('.md', '')
        print(f"Processing {tender_id}...")
        process_tender(tender_id)

if __name__ == "__main__":
    main()
