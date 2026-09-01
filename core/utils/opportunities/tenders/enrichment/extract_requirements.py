# Copyright (c) 2026 ROKCT INTELLIGENCE (PTY) LTD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

# compliance-ignore-file: structural-special-dirs
# These scripts live under .rokct/ ONLY at runtime: initiate.py fetches
# this canonical copy from The-Rokct-Protocol into .rokct/skills/ at the
# start of a workflow run, and end_protocol.py deletes it at the end.
# Nothing here is committed under .rokct/ in this repo (that path is
# gitignored) - this IS the checked-in source, at its permanent,
# allowed location.
import pdfplumber
import re
import sys
import json
import time
import requests
import io
import os
import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = Path(__file__).resolve()
while not (BASE_DIR / ".rokct").exists():
    if BASE_DIR.parent == BASE_DIR:
        # No .rokct anywhere up the tree (e.g. a bare checkout running the
        # tests) — fall back to CWD, which CI sets to the repo root. The
        # unguarded walk spun forever at the filesystem root.
        BASE_DIR = Path.cwd()
        break
    BASE_DIR = BASE_DIR.parent

LOG_FILE = (
    BASE_DIR / ".rokct" / "agent" / "logs" / "requirement_extraction_failures.log"
)


def log_failure(tender_id, reason):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(LOG_FILE.parent, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {tender_id}: {reason}\n")


def fetch_with_retries(url, tender_id, attempts=3, timeout=15):
    """GET with bounded retries + backoff so one transient network blip
    doesn't cost a tender its enrichment pass. Returns the response or
    None (the caller logs and skips — never aborts the batch)."""
    last_err = None
    for attempt in range(attempts):
        try:
            return requests.get(
                url, headers={"X-Trace-Id": "extract-requirements"}, timeout=timeout
            )
        except requests.RequestException as e:
            last_err = e
            if attempt < attempts - 1:
                time.sleep(2 * (attempt + 1))
    log_failure(tender_id, f"Fetch failed after {attempts} attempts: {last_err}")
    return None


# --- Deterministic text extraction ---------------------------------------
# Every pattern below is grounded: it only fires when the tender document
# literally contains the phrase, and it records the matched text verbatim
# (the source quote) so nothing on the checklist is invented. Patterns were
# validated against the real card corpus (203 extracted tender PDFs in
# RokctAI/opportunities, August 2026) and the SA tender completion guide's
# disqualification list (core/skills/.rok/tender-assistant/resources/).

# CIDB contractor grading: an absolute eligibility gate where present.
# Real phrasings covered (corpus tender ids in parentheses):
#   'grading of\n1EB or higher'                    (ocds-9t57fa-164683)
#   'CIDB grade 1CE or higher may respond'         (ocds-9t57fa-164649)
#   'CIDB Grading – 2EP or Higher'                 (ocds-9t57fa-164465)
#   'REQUIRED GRADING 5 GB or higher CIDB Grading' (KZN ULM panel pack)
#   'CIDB grade 1 SL or higher registration'       (NRF-SAASTA pack)
# The gap tolerates line breaks (PDF text is hard-wrapped) but stops at a
# sentence boundary; the class code whitelist (CIDB's registered classes)
# keeps 'Grade 12' school qualifications from matching.
CIDB_GRADING_RX = re.compile(
    r"(?:CIDB|contractor|grad(?:e|ing))[^.]{0,60}?"
    r"([1-9]\s?(?:GB|CE|ME|EP|EB|SB|SF|SH|SI|SJ|SK|SL|SM|SN|SO|SQ)\b"
    r"(?:\s*PE)?(?:\s+or\s+(?:higher|above))?)",
    re.I,
)

# Functionality minimum threshold: bids scoring below it are eliminated
# before price is even considered. Real phrasings covered:
#   'minimum functionality threshold of 80 points'    (ocds-9t57fa-164502)
#   'Minimum threshold for functionality: 70%.'       (ocds-9t57fa-164537)
#   'MINIMUM QUALIFYING SCORE 70 REQUIRED'            (corpus)
#   'Minimum Required Score for functionality is: 70' (corpus)
#   'ACCEPTABLE MINIMUM SCORE 60 POINTS'              (ocds-9t57fa-164598)
FUNCTIONALITY_THRESHOLD_RXES = [
    re.compile(r"minimum\s+functionality\s+threshold\s+of\s+(\d{1,3})", re.I),
    re.compile(
        r"minimum\s+threshold\s+for\s+functionality\s*[:\s]\s*(\d{1,3})\s*%?", re.I
    ),
    re.compile(
        r"minimum\s+(?:qualifying|required)\s+score\s*(?:for\s+functionality)?"
        r"\s*(?:is|of)?\s*[:\s]\s*(\d{1,3})",
        re.I,
    ),
    re.compile(r"acceptable\s+minimum\s+score\s*[:\s]?\s*(\d{1,3})", re.I),
]

# Compulsory briefing/site meeting: attendance is pass/fail wherever it
# appears. Only AFFIRMATIVE phrasings are accepted — SBD boilerplate like
# 'Where the briefing session is indicated as compulsory...' and 'Failure
# to attend the compulsory briefing session (if applicable)...' appears in
# packs with no briefing at all, so conditional wordings never match.
# Real affirmative phrasings covered:
#   'THERE WILL BE COMPULSORY BRIEFING SESSION'            (ocds-9t57fa-164547)
#   'A compulsory Briefing and Site Inspection sessions
#    will be held'                                         (corpus)
#   'Briefing Session (briefing is compulsory)'            (ocds-9t57fa-164704)
#   'Attendance of the compulsory briefing and site
#    inspection sessions.' (mandatory-criteria bullet)     (ocds-9t57fa-164423)
BRIEFING_COMPULSORY_RXES = [
    re.compile(
        r"there\s+will\s+be\s+a?\s*compulsory\s+"
        r"(?:briefing|site\s+(?:meeting|inspection|visit))[^.\n]{0,40}",
        re.I,
    ),
    re.compile(
        r"compulsory\s+(?:site\s+)?(?:briefing|clarification)"
        r"(?:\s+and\s+site\s+inspection)?\s*(?:session|meeting)?s?\s+"
        r"(?:will\s+be\s+held|will\s+take\s+place|is\s+scheduled)",
        re.I,
    ),
    re.compile(r"(?:briefing|site\s+meeting)\s+is\s+compulsory", re.I),
    re.compile(
        r"attendance\s+of\s+(?:the\s+)?compulsory\s+"
        r"(?:briefing|site\s+(?:meeting|inspection))[^.\n]{0,40}",
        re.I,
    ),
]


def extract_requirements_from_text(full_text):
    """Deterministic requirement extraction from already-extracted tender
    text. Pure function (no I/O) so it is directly testable offline; the
    PDF/table handling stays in extract_requirements_from_pdf."""
    results = {
        "gate_1_mandatory": [],
        "gate_2_functional": [],
        "pricing_preference": "Unknown",
        "cidb_grading": [],
        "briefing_compulsory": "",
        "functionality_threshold": None,
    }
    if not full_text:
        return results

    # Gate 1: mandatory-document keywords. Each entry is the literal
    # matched text. Registration gates (CSD, TCS, PSIRA, NHBRC, the
    # Restricted Suppliers / Tender Defaulters registers) follow the
    # universal-gate list in the SA tender completion guide and only fire
    # on a literal occurrence in the document.
    gate_1_patterns = [
        r"SBD\s*\d",
        r"MBD\s*\d",
        r"CSD\s*report",
        r"Tax\s*(?:compliance|clearance)",
        r"B-BBEE\s*(?:certificate|affidavit)",
        r"COIDA",
        r"Joint\s*Venture\s*Agreement",
        r"certified\s*copy",
        r"municipal\s*account",
        r"Letter\s*of\s*Good\s*Standing",
        r"Register\s*for\s*Tender\s*Defaulters",
        r"List\s*of\s*Restricted\s*Suppliers",
        r"PSIRA",
        r"NHBRC",
    ]
    for pattern in gate_1_patterns:
        matches = re.findall(pattern, full_text, re.I)
        for m in set(matches):
            clean_m = re.sub(r"[\n\r]", " ", m).strip()
            if clean_m.upper() not in [x.upper() for x in results["gate_1_mandatory"]]:
                results["gate_1_mandatory"].append(clean_m)

    # Gate 2 Regex Fallback
    weight_matches = re.findall(
        r"([A-Za-z\s]{10,100})\s+(\d{1,3})\s*(?:points|weight)", full_text, re.I
    )
    for criterion, points in weight_matches:
        if int(points) > 0:
            if not any(
                criterion.strip().lower() in x["criterion"].lower()
                for x in results["gate_2_functional"]
            ):
                results["gate_2_functional"].append(
                    {"criterion": criterion.strip(), "points": points}
                )

    # Pricing
    pp_match = re.search(r"(80/20|90/10)", full_text)
    if pp_match:
        results["pricing_preference"] = pp_match.group(1)

    # CIDB grading (deduplicated, whitespace-normalized literal grades)
    for m in CIDB_GRADING_RX.finditer(full_text):
        grade = re.sub(r"\s+", " ", m.group(1)).strip().upper()
        if grade not in results["cidb_grading"]:
            results["cidb_grading"].append(grade)

    # Compulsory briefing (store the matched sentence fragment verbatim)
    for rx in BRIEFING_COMPULSORY_RXES:
        m = rx.search(full_text)
        if m:
            results["briefing_compulsory"] = re.sub(r"\s+", " ", m.group(0)).strip()
            break

    # Functionality threshold (first explicit statement wins)
    for rx in FUNCTIONALITY_THRESHOLD_RXES:
        m = rx.search(full_text)
        if m:
            score = int(m.group(1))
            if 0 < score <= 100:
                results["functionality_threshold"] = {
                    "score": score,
                    "quote": re.sub(r"\s+", " ", m.group(0)).strip(),
                }
                break

    return results


def extract_requirements_from_pdf(pdf_stream, tender_id):
    results = {
        "gate_1_mandatory": [],
        "gate_2_functional": [],
        "pricing_preference": "Unknown",
        "cidb_grading": [],
        "briefing_compulsory": "",
        "functionality_threshold": None,
    }
    try:
        with pdfplumber.open(pdf_stream) as pdf:
            full_text = ""
            table_criteria = []
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                full_text += page_text + "\n"

                # Table-based functional criteria
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row:
                            continue
                        clean_row = [str(cell).strip() for cell in row if cell]
                        if len(clean_row) >= 2:
                            for cell in clean_row:
                                if cell.isdigit() and 0 < int(cell) <= 100:
                                    criterion = max(clean_row, key=len)
                                    if len(criterion) > 10 and not criterion.isdigit():
                                        table_criteria.append(
                                            {"criterion": criterion, "points": cell}
                                        )
                                        break

            results = extract_requirements_from_text(full_text)
            # Table criteria take precedence over the regex fallback: keep
            # them first and drop regex duplicates (same rule as before,
            # applied in merge form).
            merged = list(table_criteria)
            for item in results["gate_2_functional"]:
                if not any(
                    item["criterion"].lower() in x["criterion"].lower() for x in merged
                ):
                    merged.append(item)
            results["gate_2_functional"] = merged

            if not results["gate_1_mandatory"] and not results["gate_2_functional"]:
                log_failure(
                    tender_id, "No Gate 1 or Gate 2 requirements detected in PDF."
                )

    except Exception as e:
        log_failure(tender_id, f"PDF Processing Error: {str(e)}")
    return results


def generate_actionable_tasks(requirements, tender_id):
    tasks = []

    # Hard eligibility gates first — per the disqualification league table
    # in the SA tender completion guide, these kill bids outright, so they
    # must survive the task cap ahead of document-gathering items. Each
    # task embeds the literal text extracted from the tender document.
    cidb_grades = requirements.get("cidb_grading") or []
    if cidb_grades:
        tasks.append(
            "Confirm CIDB contractor grading "
            f"'{cidb_grades[0]}' is active and in good standing "
            "(stated in tender document) | 1"
        )
    briefing = requirements.get("briefing_compulsory") or ""
    if briefing:
        tasks.append(
            "Attend the compulsory briefing/site meeting and sign the "
            f"attendance register (document states: '{briefing[:80]}') | 1"
        )

    mandatory = requirements.get("gate_1_mandatory", [])
    if mandatory:
        sbds = sorted(
            list(
                set(
                    [
                        m.upper()
                        for m in mandatory
                        if "SBD" in m.upper() or "MBD" in m.upper()
                    ]
                )
            )
        )
        if sbds:
            tasks.append(
                f"Complete and sign all mandatory forms: {', '.join(sbds)} | 1"
            )
        if any("CSD" in m.upper() for m in mandatory):
            tasks.append(
                "Download and attach latest Full CSD Report (ensure MAAA is correct) | 1"
            )
        if any("TAX" in m.upper() for m in mandatory):
            tasks.append(
                "Verify Tax Compliance status on SARS and provide valid PIN | 1"
            )
        if any("B-BBEE" in m.upper() for m in mandatory):
            tasks.append(
                "Attach valid B-BBEE Certificate or correctly commissioned Sworn Affidavit | 1"
            )
        if any("MUNICIPAL" in m.upper() for m in mandatory):
            tasks.append(
                "Obtain recent municipal accounts (<90 days) for the Company and all Directors | 2"
            )
        if any(
            "DEFAULTERS" in m.upper() or "RESTRICTED" in m.upper() for m in mandatory
        ):
            tasks.append(
                "Verify the company and every director are NOT listed on National Treasury's Restricted Suppliers / Tender Defaulters registers | 1"
            )
        if any("PSIRA" in m.upper() for m in mandatory):
            tasks.append(
                "Attach valid PSIRA registration certificates (company and directors) | 1"
            )
        if any("NHBRC" in m.upper() for m in mandatory):
            tasks.append("Attach valid NHBRC registration proof | 1")
        if any("COIDA" in m.upper() or "GOOD STANDING" in m.upper() for m in mandatory):
            tasks.append(
                "Obtain COIDA Letter of Good Standing from the Compensation Fund | 2"
            )

    threshold = requirements.get("functionality_threshold")
    if threshold:
        tasks.append(
            "Self-score functionality before bidding — document states: "
            f"'{threshold['quote'][:80]}' | 2"
        )

    functional = requirements.get("gate_2_functional", [])
    if functional:
        unique_functional = []
        seen = set()
        for item in functional:
            c_low = item["criterion"].lower()
            if c_low not in seen:
                unique_functional.append(item)
                seen.add(c_low)
        unique_functional.sort(key=lambda x: int(x["points"]), reverse=True)
        for item in unique_functional[:2]:
            clean_crit = item["criterion"].split("\n")[0][:50]
            tasks.append(
                f"Draft detailed methodology addressing '{clean_crit}' ({item['points']} pts) | 3"
            )
        tasks.append(
            "Gather Trinity of Evidence (Appointment, SLA, Completion) for previous projects | 2"
        )

    if not tasks:
        log_failure(
            tender_id, "Insufficient extraction — checklist used generic fallback"
        )
        tasks = [
            "Analyze Tender Documents for specific requirements | 1",
            "Identify Mandatory Compliance items | 2",
            "Prepare Initial Response Proposal | 3",
        ]
    # Cap raised from 5 to 7: the new hard-gate tasks (CIDB, briefing,
    # restricted-suppliers check) must not push out the methodology and
    # evidence tasks that were previously the checklist's tail.
    return tasks[:7]


def update_tender_card(md_path, requirements):
    tender_id = md_path.stem
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    standard_comment = "<!-- This section is populated by Jules during enrichment. -->"
    tasks = generate_actionable_tasks(requirements, tender_id)
    checklist_header = "## AI Checklist (Jules)"
    new_checklist_block = f"{checklist_header}\n{standard_comment}\n"
    for task in tasks:
        new_checklist_block += f"- [ ] {task}\n"

    if checklist_header in content:
        # Replace the section until the next header or end of file
        pattern = re.escape(checklist_header) + r".*?(?=\n## |$)"
        new_content = re.sub(
            pattern, new_checklist_block.strip(), content, flags=re.DOTALL
        )
    else:
        new_content = content.strip() + "\n\n" + new_checklist_block

    # Atomic replace: write a sibling temp file and rename it over the card
    # so a crash mid-write can never leave a truncated card behind.
    tmp_path = md_path.with_name(md_path.name + f".tmp{os.getpid()}")
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_content)
    os.replace(tmp_path, md_path)


def process_file(md_file):
    tender_id = md_file.stem
    try:
        with open(md_file, "r", encoding="utf-8") as f:
            md_content = f.read()
        url_match = re.search(
            r"- \*\*Direct Link\*\*:\s*(https?://[^\s\n]+)", md_content
        )
        if not url_match:
            log_failure(tender_id, "No Direct Link found in card.")
            return False
        url = url_match.group(1).strip()

        resp = fetch_with_retries(url, tender_id)
        if resp is None:
            return False
        if resp.status_code == 200:
            # Accept the same responses pdf_to_md.py accepts: a Direct Link
            # may serve a real PDF from a download endpoint or a URL with
            # query parameters. The old endswith(".pdf") pre-check rejected
            # those without ever looking at the response, so cards whose text
            # pdf_to_md.py had already extracted were still logged here as
            # "not a PDF" and never got a requirements checklist (recurring
            # entries in requirement_extraction_failures.log; ported from
            # opportunities#50). Extension and Content-Type are hints only -
            # the %PDF magic-byte sniff is what decides for everything else.
            content_type = resp.headers.get("Content-Type", "").lower()
            if (
                "application/pdf" not in content_type
                and not url.lower().endswith(".pdf")
                and not resp.content.startswith(b"%PDF")
            ):
                log_failure(tender_id, f"Direct Link is not a PDF: {url}")
                return False
            pdf_stream = io.BytesIO(resp.content)
            reqs = extract_requirements_from_pdf(pdf_stream, tender_id)
            update_tender_card(md_file, reqs)
            return True
        else:
            log_failure(tender_id, f"Failed to fetch PDF: HTTP {resp.status_code}")
            return False
    except Exception as e:
        log_failure(tender_id, f"Error processing file: {str(e)}")
        return False


def main():
    root = BASE_DIR
    tender_dir = root / "03_tenders"
    todo_path = root / ".rokct" / "agent" / "todo.json"

    target_files = []
    use_fallback = False

    if todo_path.exists():
        try:
            with open(todo_path, "r", encoding="utf-8") as f:
                todo_data = json.load(f)
            # save_jules_todo (registry_orchestrator/updaters.py) writes a
            # dict {"title", "pending_count", "files": [...]} — the same
            # format pdf_to_md.py already accepts. This reader only took
            # the legacy bare list, so every committed todo.json was
            # misread as "empty" and the run fell back to the full-corpus
            # scan that blew the 6-hour job limit.
            if isinstance(todo_data, dict) and "files" in todo_data:
                todo_data = todo_data["files"]
            if isinstance(todo_data, list) and todo_data:
                for rel_path in todo_data:
                    target_files.append(root / rel_path)
            else:
                use_fallback = True
        except Exception as e:
            print(f"Error reading todo.json: {e}")
            use_fallback = True
    else:
        use_fallback = True

    if use_fallback:
        # FALLBACK_LIMIT: the previous fallback enriched the ENTIRE corpus
        # in one run. With ~1200+ cards, each a PDF fetch + pdfplumber
        # parse (which has no parse timeout of its own), the sync-engine
        # job ran past GitHub's 6-hour default execution limit and was
        # canceled mid-enrichment — before maintenance/purge and before
        # any commit, throwing away the whole (successful) OCDS sync.
        # A missing todo.json now enriches a bounded chunk instead:
        # cards without an AI Checklist first (never enriched), newest
        # first, capped. Successive weekly runs work through the backlog.
        FALLBACK_LIMIT = 200
        print(
            "todo.json not found or empty — falling back to bounded scan "
            f"(unenriched/newest first, capped at {FALLBACK_LIMIT})"
        )
        all_md_files = list(tender_dir.rglob("*.md"))
        unenriched = []
        enriched = []
        for f in all_md_files:
            if f.name in ["template.md", "registry_audit_log.md"] or f.name.endswith(
                "_content.md"
            ):
                continue
            if f.parent == tender_dir or f.stem == f.parent.name:
                try:
                    has_checklist = "## AI Checklist" in f.read_text(
                        encoding="utf-8", errors="ignore"
                    )
                except Exception:
                    has_checklist = False
                (enriched if has_checklist else unenriched).append(f)
        # Sort by name, newest ids first (OCDS ids are chronological;
        # file mtimes are useless in CI where checkout stamps everything
        # with the same time).
        unenriched.sort(key=lambda f: f.name, reverse=True)
        enriched.sort(key=lambda f: f.name, reverse=True)
        target_files = (unenriched + enriched)[:FALLBACK_LIMIT]
    else:
        # Safety filter even for todo.json items
        filtered_targets = []
        for f in target_files:
            if not f.exists():
                continue
            if f.name in ["template.md", "registry_audit_log.md"] or f.name.endswith(
                "_content.md"
            ):
                continue
            filtered_targets.append(f)
        target_files = filtered_targets

    print(f"Enriching {len(target_files)} tender cards...")
    for f in target_files:
        try:
            print(f" - {f.relative_to(root)}")
        except ValueError:
            print(f" - {f}")

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(process_file, target_files))
    print(f"Finished. Enriched {sum(results)} tenders.")


if __name__ == "__main__":
    main()
