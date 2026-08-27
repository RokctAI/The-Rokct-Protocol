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
import sys
import json
import time
import requests
import pdfplumber
import shutil
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

# Add utils to path
sys.path.append(str(Path(__file__).parent.parent / "utils"))
from tender_resolver import resolve_card_path

BASE_DIR = Path(__file__).resolve()
while not (BASE_DIR / ".rokct").exists():
    if BASE_DIR.parent == BASE_DIR:
        # No .rokct anywhere up the tree (misconfigured checkout) - fall
        # back to CWD, which CI sets to the repo root, instead of spinning
        # forever at the filesystem root.
        BASE_DIR = Path.cwd()
        break
    BASE_DIR = BASE_DIR.parent
TENDER_DIR = BASE_DIR / "03_tenders"
TODO_JSON = BASE_DIR / ".rokct" / "agent" / "todo.json"
LOG_FILE = BASE_DIR / ".rokct" / "agent" / "logs" / "pdf_extraction_failures.log"


def log_failure(tender_id, reason):
    """Logs failures to the specified log file."""
    timestamp = datetime.now().isoformat()
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] Tender ID: {tender_id} | Reason: {reason}\n")


def extract_direct_link(card_path):
    """Extracts the Direct Link URL from the tender card."""
    with open(card_path, "r", encoding="utf-8") as f:
        content = f.read()
        match = re.search(r"-\s+\*\*Direct Link\*\*:\s*(https?://[^\s\n]+)", content)
        if match:
            return match.group(1).strip()
    return None


def get_last_verified_date(card_path):
    """Extracts the Last Verified date from the tender card."""
    with open(card_path, "r", encoding="utf-8") as f:
        content = f.read()
        match = re.search(r"-\s+\*\*Last Verified\*\*:\s*(\d{4}-\d{2}-\d{2})", content)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y-%m-%d")
            except ValueError:
                return None
    return None


def clean_markdown(text):
    """Cleans extracted PDF text to resolve common markdownlint errors."""
    if not text:
        return text

    lines = text.splitlines()
    cleaned_lines = []

    list_counter = 0
    in_list = False

    for line in lines:
        # Fix MD010: Hard tabs
        line = line.replace("\t", "    ")

        # MD029: Ordered list item prefix
        # Detect if line starts with a digit followed by . or )
        list_match = re.match(r"^(\s*)(\d+)[.)]\s+(.*)", line)
        if list_match:
            in_list = True
            indent, _, content = list_match.groups()
            list_counter += 1
            line = f"{indent}{list_counter}. {content}"
        else:
            # If it's not a list item, but has indent, it might be part of the list
            if not (line.strip() == "" or re.match(r"^\s{2,}", line)):
                in_list = False
                list_counter = 0

        # Fix MD035: Horizontal rule style
        stripped = line.strip()
        if stripped and all(c in " _-*" for c in stripped) and len(stripped) >= 3:
            line = "---"

        cleaned_lines.append(line)

    # Join with a real newline. This used to be the two-character literal
    # "\n" (an escaped backslash), which flattened every extracted
    # *_content.md into a single line of visible '\n' sequences — visible
    # in the whole committed corpus.
    result = "\n".join(cleaned_lines)

    # Fix MD037: Spaces inside emphasis markers
    result = re.sub(r"_\s+(.*?)\s+_", r"_\1_", result)

    return result


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

        # Fetch PDF (bounded retries with backoff: a transient network
        # error must not cost the tender its extraction pass)
        try:
            resp = None
            last_err = None
            for attempt in range(3):
                try:
                    resp = requests.get(
                        direct_link, headers={"X-Trace-Id": "pdf-to-md"}, timeout=60
                    )
                    break
                except requests.RequestException as e:
                    last_err = e
                    if attempt < 2:
                        time.sleep(2 * (attempt + 1))
            if resp is None:
                raise last_err
            resp.raise_for_status()
            if "application/pdf" not in resp.headers.get(
                "Content-Type", ""
            ).lower() and not direct_link.lower().endswith(".pdf"):
                # Try to check if it's actually a PDF even if header is missing
                if not resp.content.startswith(b"%PDF"):
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
                log_failure(
                    tender_id, "PDF has no extractable text (likely scanned image)"
                )
                return

            md_content = clean_markdown(md_content)

            # Atomic replace: a crash or timeout mid-write must never
            # leave a truncated content file behind.
            tmp_file = content_file.with_name(content_file.name + f".tmp{os.getpid()}")
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(md_content)
            os.replace(tmp_file, content_file)

        except Exception as e:
            log_failure(tender_id, f"PDF extraction error: {str(e)}")

    except Exception as e:
        log_failure(tender_id, f"Unexpected error: {str(e)}")


def main():
    # Also check 03_tenders/todo.json as fallback per task description
    todo_path = TODO_JSON
    if not todo_path.exists():
        todo_path = TENDER_DIR / "todo.json"

    if not todo_path.exists():
        print(f"Todo file not found. Skipping.")
        return

    try:
        with open(todo_path, "r", encoding="utf-8") as f:
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

    # PER_TENDER_TIMEOUT_SECONDS: pdfplumber's page-by-page parse has no
    # timeout of its own, unlike every network call in this file (60s PDF
    # fetch above, 15s in extract_requirements.py). A single hung or
    # pathological PDF here previously stalled the whole SEQUENTIAL run
    # indefinitely - consistent with the scheduled Jul 27 run dying after
    # 2h29m with "runner lost communication" (a crashed/unresponsive VM,
    # not the 6-hour default job timeout). This bounds the damage to one
    # tender's wall-clock budget and lets the batch continue past it.
    PER_TENDER_TIMEOUT_SECONDS = 180
    with ThreadPoolExecutor(max_workers=1) as executor:
        for item in todo_list:
            # item might be "03_tenders/ocds-xxx.md" or "ocds-xxx"
            tender_id = str(item).replace(".md", "")
            print(f"Processing {tender_id}...")
            future = executor.submit(process_tender, tender_id)
            try:
                future.result(timeout=PER_TENDER_TIMEOUT_SECONDS)
            except FutureTimeoutError:
                log_failure(
                    tender_id,
                    f"Timed out after "
                    f"{PER_TENDER_TIMEOUT_SECONDS}s (likely a "
                    f"pathological or oversized PDF) - skipped",
                )


if __name__ == "__main__":
    main()
