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
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pathlib import Path
import sys
import re
import io
import time
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Add utils to path
sys.path.append(str(Path(__file__).parent.parent / "utils"))
from tender_resolver import resolve_card_path, resolve_write_path

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


def rokct_logs_dir():
    """Locate the consuming repo's .rokct/agent/logs by walking up from this
    file to the first directory containing .rokct/. A fixed parent-depth path
    breaks when this script runs from a relocated copy (e.g. the delegate
    cache under .rokct/tmp/); fall back to CWD, which CI sets to the repo
    root."""
    for parent in Path(__file__).resolve().parents:
        if (parent / ".rokct").is_dir():
            return parent / ".rokct" / "agent" / "logs"
    return Path.cwd() / ".rokct" / "agent" / "logs"


def log_failure(message):
    """Append to the extraction-failure log; never raise from logging."""
    try:
        log = rokct_logs_dir() / "pdf_extraction_failures.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as fl:
            fl.write(f"[{datetime.now().isoformat()}] {message}\n")
    except OSError:
        pass


def get_with_retries(url, trace_id, timeout, attempts=2):
    """GET with a bounded retry + backoff so one transient network error
    doesn't cost a detail page or PDF its extraction pass. Raises the last
    error after the final attempt — callers already handle failures."""
    last_err = None
    for attempt in range(attempts):
        try:
            return requests.get(url, headers={"X-Trace-Id": trace_id}, timeout=timeout)
        except requests.RequestException as e:
            last_err = e
            if attempt < attempts - 1:
                time.sleep(2 * (attempt + 1))
    raise last_err


def normalize_date(date_str):
    if not date_str:
        return None
    date_str = date_str.strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", date_str):
        return date_str[:10]
    # Numeric day-first formats are standard in SA municipal notices
    # (e.g. eThekwini RFQ1003: 'no later than: 26/05/2022 at 11:00am').
    for fmt in (
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%B %d %Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
    ):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


# One date shape shared by every closing-date pattern below: textual
# ('8 May 2026' / 'August 3, 2026' — all-caps months included, munis
# shout), numeric day-first ('26/05/2022', '21-05-2026'), or ISO.
# Time-of-day suffixes ('at 11h00', '@ 11:00am') follow the capture and
# need no handling here.
CLOSING_DATE_RX = (
    r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}"
    r"|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}"
    r"|\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}"
    r"|\d{4}-\d{2}-\d{2})"
)

# Patterns are anchored to submission/closing context words so advert or
# publication dates are never grabbed by accident. Real phrasings these
# cover (found via web search while musina.gov.za itself is
# egress-blocked here):
#   'Closing date: 27 November 2025 at 11:00'        (Musina RFQ23)
#   'closing date ... 07 April 2026 @ 11h00'         (Musina RFQ51)
#   'closing date ... 03 August 2026 at 11h00'       (Musina RFQ08, tenderbulletins.co.za)
#   'before 8 May 2026 @ 11h00'                      (Musina RFQ61)
#   'submitted on or before 23 January 2026 @ 11h00' (Musina RFQ listing)
#   'placed in the Tender Box ... no later than: 26/05/2022 at 11:00am'
#                                                    (eThekwini RFQ1003)
#   '... deposited in the designated Tender box ... not later than the
#    closing date and time'                          (Musina standard notice —
#                                                     dateless here, the dated
#                                                     variant per Ray is covered
#                                                     by the tender-box pattern)
EXPLICIT_CLOSING_PATTERNS = [
    r"Closing\s*(?:date|time)(?:\s*(?:and|&)\s*time)?\s*(?:of\s+|[:\s])\s*"
    + CLOSING_DATE_RX,
    r"Deadline\s*[:\s]\s*" + CLOSING_DATE_RX,
]
BURIED_CLOSING_PATTERNS = [
    # 'no later than' and 'not later than' both occur in the wild; allow
    # an optional colon ('no later than: 26/05/2022').
    r"(?:on\s+or\s+before|not?\s+later\s+than|submitted\s+by|deposited\s+by|before)\s*:?\s+"
    + CLOSING_DATE_RX,
    # Tender-box sentences put the venue between the anchor and the date
    # ('deposited in the tender box at reception ... by/not later than
    # <date>') — bridge a bounded gap, still ending on a submission word
    # so published dates can't sneak in.
    r"tender\s*box[^.\n]{0,150}?(?:not?\s+later\s+than|on\s+or\s+before|by|before)\s*:?\s+"
    + CLOSING_DATE_RX,
]


def find_closing_date(text):
    """Scans free text (detail page or PDF) for a closing date using the
    explicit patterns first, then the buried/loose phrasings. Returns a
    normalized YYYY-MM-DD string or None."""
    if not text:
        return None
    for pattern in EXPLICIT_CLOSING_PATTERNS + BURIED_CLOSING_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            norm = normalize_date(match.group(1).strip())
            if norm and re.match(r"\d{4}-\d{2}-\d{2}", norm):
                return norm
    return None


def pub_date_from_url(url):
    """Last-resort publication date from a WordPress upload path
    (/wp-content/uploads/YYYY/MM/...): month-accurate, day unknown, so
    day 01 is used. Every 'Skipped: no published date found' entry in
    the 2026-07-14 runs was a direct-PDF link carrying exactly this
    path — those RFQs produced no card at all because the listing page
    showed no date next to the link and PDFs never get a pub-date scan."""
    m = re.search(r"/uploads/(\d{4})/(\d{2})/", url)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{m.group(1)}-{m.group(2)}-01"
    return None


def calculate_fallback_date(pub_date_str):
    """Returns (date_str, is_estimated). Adds 14 days to pub date as a fallback."""
    if not pub_date_str:
        return None, False
    try:
        norm = normalize_date(pub_date_str)
        if not norm or not re.match(r"\d{4}-\d{2}-\d{2}", norm):
            return None, False
        dt = datetime.strptime(norm, "%Y-%m-%d")
        return (dt + timedelta(days=14)).strftime("%Y-%m-%d"), True
    except Exception as e:
        log_failure(f"Fallback-date parse failed for '{pub_date_str}': {e}")
        return None, False


def extract_text_from_pdf(url):
    if not pdfplumber:
        return ""
    try:
        resp = get_with_retries(url, "musina-list", timeout=30)
        if resp.status_code != 200:
            return ""
        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
            return text
    except Exception as e:
        log_failure(f"PDF extraction failed for {url}: {e}")
        return ""


def fetch_deep_details(url, existing_pub):
    """Visits the detail page or parses PDF to extract dates.
    Returns (closing_date, is_estimated, found_pub_date).
    When no closing date is found, falls back to pub_date + 14 days (is_estimated=True).
    When pub_date is also unknown, returns (None, False, ...) → caller sets 'See Documents'.
    """
    if url.lower().endswith(".pdf"):
        pdf_text = extract_text_from_pdf(url)
        norm = find_closing_date(pdf_text)
        if norm:
            return norm, False, None
        # Fallback: estimate from existing pub date
        val, est = calculate_fallback_date(existing_pub)
        return val, est, None

    try:
        time.sleep(0.5)
        resp = get_with_retries(url, "musina-detail", timeout=20)
        if resp.status_code != 200:
            val, est = calculate_fallback_date(existing_pub)
            return val, est, None

        soup = BeautifulSoup(resp.text, "lxml")
        text_content = soup.get_text(" ", strip=True)

        # 1. Look for Publication Date on the page
        found_pub = existing_pub
        # BS4 structural approach for Create Date
        # Find the specific element containing the label, avoiding containers
        create_date_label = soup.find(
            lambda tag: (
                tag.name in ["span", "div", "strong", "b", "td", "th"]
                and "Create Date" in tag.get_text()
                and len(tag.find_all()) == 0
            )
        )
        if not create_date_label:
            # Fallback if it has some nested tag like <b>Create Date</b>
            create_date_label = soup.find(
                lambda tag: (
                    tag.name in ["span", "div", "strong", "b", "td", "th"]
                    and "Create Date" in tag.get_text()
                )
            )

        if create_date_label:
            sibling = create_date_label.find_next_sibling()
            if sibling:
                # Only accept the sibling text if it actually parses as a
                # date — pages put script fragments (e.g. 'window.RS_') next
                # to the label, and normalize_date passes unparseable strings
                # through, so junk here used to end up as the card's
                # Date Published.
                candidate = sibling.get_text(strip=True)
                norm = normalize_date(candidate)
                if norm and re.match(r"\d{4}-\d{2}-\d{2}", norm):
                    found_pub = candidate

        # Existing regex fallback for pub date
        if not found_pub or found_pub == existing_pub:
            pub_match = re.search(
                r"([A-Z][a-z]+ \d{1,2}, \d{4})\s*[\s\|]+Musina Web", text_content
            )
            if not pub_match:
                pub_match = re.search(
                    r"(?:Create Date|Posted)\s*:?\s*([A-Z][a-z]+ \d{1,2}, \d{4})",
                    text_content,
                    re.IGNORECASE,
                )
            if pub_match:
                found_pub = pub_match.group(1).strip()

        # 2. Look for Closing Date patterns in detail page
        # Priority 1 & 2: Explicit then buried patterns on detail page
        norm = find_closing_date(text_content)
        if norm:
            return norm, False, found_pub

        # Priority 3 & 4: PDF explicit then buried
        pdf_link = soup.find("a", href=re.compile(r"\.pdf$", re.I))
        if pdf_link:
            # Resolve relative links against the detail page's own URL, not a
            # hardcoded host — the source URL in sources/musinaZA.md governs.
            pdf_url = urljoin(url, pdf_link["href"])
            pdf_text = extract_text_from_pdf(pdf_url)
            norm = find_closing_date(pdf_text)
            if norm:
                return norm, False, found_pub

        # 4. Nothing found — fall back to pub date + 14 days
        val, est = calculate_fallback_date(found_pub)
        return val, est, found_pub

    except Exception as e:
        log_failure(f"Detail-page fetch/parse failed for {url}: {e}")
        val, est = calculate_fallback_date(existing_pub)
        return val, est, None


def run_sync(tender_dir, sources_dir, generate_md_fn):
    print("[Musina] Starting Scraper Sync...")
    source_file = sources_dir / "musinaZA.md"
    if not source_file.exists():
        return

    with open(source_file, "r", encoding="utf-8") as f:
        content = f.read()
        u_match = re.search(r"URL\*\*:\s*(https?://[^\s\n]+)", content)
        f_match = re.search(r"Flag\*\*:\s*([A-Z]{2})", content)
        if not u_match or not f_match:
            return
        base_url = u_match.group(1).strip()
        if not base_url.endswith("/"):
            base_url += "/"
        flag = f_match.group(1).strip()
        source_ref = f"sources/{source_file.name}"

    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=Retry(total=5, backoff_factor=2)))
    session.headers.update({"User-Agent": "Mozilla/5.0 RokctAI-Scraper/1.0"})

    # 1. Bids Received Intelligence
    log_path = rokct_logs_dir() / "musina_bids_intelligence.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    audit_entries = []

    try:
        b_resp = session.get(f"{base_url}bids-received/", timeout=30)
        if b_resp.status_code == 200:
            b_soup = BeautifulSoup(b_resp.text, "lxml")
            for b_link in b_soup.find_all("a", href=True):
                b_text = b_link.get_text(" ", strip=True)
                if any(kw in b_text.upper() for kw in ["TENDER", "RFQ", "BID"]):
                    audit_entries.append(f"BID RECEIVED - {b_text}")
    except Exception as e:
        log_failure(f"Bids-received page fetch failed ({base_url}bids-received/): {e}")

    # 2. RFQ Scraping
    try:
        response = session.get(f"{base_url}request-for-quotations/", timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        rfqs_found = {}
        for link in soup.find_all("a", href=True):
            text = link.get_text(" ", strip=True)
            # Relative links resolve against the configured source URL, not a
            # hardcoded host.
            url = urljoin(base_url, link["href"])

            if any(kw in text.upper() for kw in ["TENDER", "RFQ", "BID"]):
                audit_entries.append(text)

            rfq_match = re.search(r"RFQ\s*([\d/A-Z-]+)", text, re.I)
            if rfq_match:
                raw_full = rfq_match.group(1).strip().upper()
                # DEDUPLICATION: Extract just the numeric ID (e.g., 59 from 59/2024)
                base_id_match = re.search(r"(\d+)", raw_full)
                base_id = (
                    base_id_match.group(1)
                    if base_id_match
                    else raw_full.replace("/", "-")
                )
                full_id = f"musina-rfq{base_id}"

                pub_date = ""
                # Try sibling text or parent container for publication date
                context_text = link.get_text()
                parent = link.find_parent()
                if parent:
                    context_text = parent.get_text(" ", strip=True)

                date_match = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})", context_text)
                if date_match:
                    pub_date = date_match.group(1)

                if full_id not in rfqs_found:
                    rfqs_found[full_id] = {"text": text, "url": url, "pub": pub_date}
                else:
                    # Prefer PDF links if duplicates exist
                    if url.lower().endswith(".pdf"):
                        rfqs_found[full_id] = {
                            "text": text,
                            "url": url,
                            "pub": pub_date,
                        }

        updates = 0
        failure_log = rokct_logs_dir() / "pdf_extraction_failures.log"
        failure_log.parent.mkdir(parents=True, exist_ok=True)

        for fid, rdata in rfqs_found.items():
            # Per-item isolation: one malformed RFQ or unwritable card
            # logs and skips - it must never abort the rest of the sync.
            try:
                card_path = resolve_card_path(tender_dir, fid)
                existing = ""
                if card_path and card_path.exists():
                    with open(card_path, "r", encoding="utf-8") as f:
                        existing = f.read()
                    if "VERIFIED" in existing:
                        continue

                closing_date, is_est, found_pub = fetch_deep_details(
                    rdata["url"], rdata["pub"]
                )

                # Only a string that actually normalised to YYYY-MM-DD counts as
                # a published date; normalize_date echoes unparseable input.
                final_pub = ""
                for cand in (found_pub, rdata["pub"]):
                    norm = normalize_date(cand)
                    if norm and re.match(r"\d{4}-\d{2}-\d{2}", norm):
                        final_pub = norm
                        break

                if not final_pub:
                    # Direct-PDF RFQs often have no date in the listing context;
                    # recover the month from the upload path instead of dropping
                    # the tender entirely (closing date stays whatever
                    # fetch_deep_details found — 'See Documents' when unknown,
                    # which generate_md flags as INCOMPLETE).
                    final_pub = pub_date_from_url(rdata["url"])
                    if final_pub:
                        with open(failure_log, "a", encoding="utf-8") as fl:
                            fl.write(
                                f"[{datetime.now().isoformat()}] Pub date approximated from upload path (day unknown, using 01) - {fid} ({rdata['url']})\n"
                            )

                if not final_pub:
                    with open(failure_log, "a", encoding="utf-8") as fl:
                        fl.write(
                            f"[{datetime.now().isoformat()}] Skipped: no published date found - {fid} ({rdata['url']})\n"
                        )
                    continue

                # Apply (Estimated) suffix when date is a fallback, "See Documents" when unknown
                if closing_date:
                    final_close = (
                        f"{closing_date} (Estimated)" if is_est else closing_date
                    )
                else:
                    final_close = "See Documents"

                release = {
                    "ocid": fid,
                    "date": final_pub,
                    "tender": {
                        "title": rdata["text"],
                        "procuringEntity": {"name": "Musina Local Municipality"},
                        "procurementMethodDetails": "Request for Quotation",
                        "province": "Limpopo",
                        "deliveryLocation": "Musina",
                        "category": "General Procurement",
                        "description": rdata["text"],
                        "tenderPeriod": {"endDate": final_close},
                        "documents": [{"title": "RFQ Document", "url": rdata["url"]}],
                    },
                }

                new_c = generate_md_fn(release, flag, source_ref, existing)
                if [l.strip() for l in existing.splitlines() if l.strip()] != [
                    l.strip() for l in new_c.splitlines() if l.strip()
                ]:
                    write_path = resolve_write_path(tender_dir, fid)
                    # Atomic replace so a crash mid-write can never leave
                    # a truncated card behind.
                    tmp_path = write_path.with_name(
                        write_path.name + f".tmp{os.getpid()}"
                    )
                    with open(tmp_path, "w", encoding="utf-8", newline="\n") as fw:
                        fw.write(new_c)
                    os.replace(tmp_path, write_path)
                    updates += 1
            except Exception as e:
                log_failure(f"RFQ {fid} processing failed: {e}")
                continue

        if audit_entries:
            with open(log_path, "a", encoding="utf-8") as log_f:
                log_f.write(f"\n--- Audit: {datetime.now().isoformat()} ---\n")
                for entry in audit_entries:
                    log_f.write(f"{entry}\n")

        print(f"  [+] Musina: Updated {updates} items. Intelligence log updated.")

    except Exception as e:
        print(f"  [Error] Musina sync failed: {e}")
        if "Timeout" in str(e) or "Max retries exceeded" in str(e):
            print("🚨 Musina site is likely broken or down. Skipping.")
