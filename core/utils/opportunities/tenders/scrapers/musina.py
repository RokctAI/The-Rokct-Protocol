# Licensed under the MIT License.
# Copyright 2024 RokctAI

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pathlib import Path
import sys
import re
import io
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Add utils to path
sys.path.append(str(Path(__file__).parent.parent / 'utils'))
from tender_resolver import resolve_card_path, resolve_write_path

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


def normalize_date(date_str):
    if not date_str:
        return None
    if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
        return date_str
    for fmt in ('%d %B %Y', '%d %b %Y', '%B %d, %Y', '%B %d %Y'):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    return date_str


def calculate_fallback_date(pub_date_str):
    """Returns (date_str, is_estimated). Adds 14 days to pub date as a fallback."""
    if not pub_date_str:
        return None, False
    try:
        norm = normalize_date(pub_date_str)
        if not norm or not re.match(r'\d{4}-\d{2}-\d{2}', norm):
            return None, False
        dt = datetime.strptime(norm, '%Y-%m-%d')
        return (dt + timedelta(days=14)).strftime('%Y-%m-%d'), True
    except:
        return None, False


def extract_text_from_pdf(url):
    if not pdfplumber:
        return ""
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            return ""
        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
            return text
    except:
        return ""


def fetch_deep_details(url, existing_pub):
    """Visits the detail page or parses PDF to extract dates.
    Returns (closing_date, is_estimated, found_pub_date).
    When no closing date is found, falls back to pub_date + 14 days (is_estimated=True).
    When pub_date is also unknown, returns (None, False, ...) → caller sets 'See Documents'.
    """
    explicit_patterns = [
        r'Closing\s*date\s*[:\s]\s*(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})',
        r'Closing\s*date\s*[:\s]\s*([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})',
        r'Deadline\s*[:\s]\s*(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})'
    ]
    buried_patterns = [
        r'(?:on or before|before|not later than|submitted by)\s+(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})'
    ]

    if url.lower().endswith('.pdf'):
        pdf_text = extract_text_from_pdf(url)
        for pattern in explicit_patterns + buried_patterns:
            match = re.search(pattern, pdf_text, re.IGNORECASE)
            if match:
                norm = normalize_date(match.group(1).strip())
                if norm:
                    return norm, False, None
        # Fallback: estimate from existing pub date
        val, est = calculate_fallback_date(existing_pub)
        return val, est, None

    try:
        time.sleep(0.5)
        resp = requests.get(url, timeout=20)
        if resp.status_code != 200:
            val, est = calculate_fallback_date(existing_pub)
            return val, est, None

        soup = BeautifulSoup(resp.text, 'lxml')
        text_content = soup.get_text(" ", strip=True)

        # 1. Look for Publication Date on the page
        found_pub = existing_pub
        # BS4 structural approach for Create Date
        # Find the specific element containing the label, avoiding containers
        create_date_label = soup.find(lambda tag: tag.name in ['span', 'div', 'strong', 'b', 'td', 'th'] and
                                     "Create Date" in tag.get_text() and len(tag.find_all()) == 0)
        if not create_date_label:
            # Fallback if it has some nested tag like <b>Create Date</b>
            create_date_label = soup.find(lambda tag: tag.name in ['span', 'div', 'strong', 'b', 'td', 'th'] and
                                         "Create Date" in tag.get_text())

        if create_date_label:
            sibling = create_date_label.find_next_sibling()
            if sibling:
                found_pub = sibling.get_text(strip=True)

        # Existing regex fallback for pub date
        if not found_pub or found_pub == existing_pub:
            pub_match = re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})\s*[\s\|]+Musina Web', text_content)
            if not pub_match:
                pub_match = re.search(r'(?:Create Date|Posted)\s*:?\s*([A-Z][a-z]+ \d{1,2}, \d{4})', text_content, re.IGNORECASE)
            if pub_match:
                found_pub = pub_match.group(1).strip()

        # 2. Look for Closing Date patterns in detail page
        # Priority 1: Explicit patterns on detail page
        for pattern in explicit_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                norm = normalize_date(match.group(1).strip())
                if norm:
                    return norm, False, found_pub

        # Priority 2: Buried patterns on detail page
        for pattern in buried_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                norm = normalize_date(match.group(1).strip())
                if norm:
                    return norm, False, found_pub

        # Priority 3 & 4: PDF explicit then buried
        pdf_link = soup.find('a', href=re.compile(r'\.pdf$', re.I))
        if pdf_link:
            pdf_url = pdf_link['href']
            if not pdf_url.startswith('http'):
                pdf_url = "https://www.musina.gov.za" + pdf_url
            pdf_text = extract_text_from_pdf(pdf_url)

            # Explicit in PDF
            for pattern in explicit_patterns:
                match = re.search(pattern, pdf_text, re.IGNORECASE)
                if match:
                    norm = normalize_date(match.group(1).strip())
                    if norm:
                        return norm, False, found_pub

            # Buried in PDF
            for pattern in buried_patterns:
                match = re.search(pattern, pdf_text, re.IGNORECASE)
                if match:
                    norm = normalize_date(match.group(1).strip())
                    if norm:
                        return norm, False, found_pub

        # 4. Nothing found — fall back to pub date + 14 days
        val, est = calculate_fallback_date(found_pub)
        return val, est, found_pub

    except:
        val, est = calculate_fallback_date(existing_pub)
        return val, est, None


def run_sync(tender_dir, sources_dir, generate_md_fn):
    print("[Musina] Starting Scraper Sync...")
    source_file = sources_dir / 'musinaZA.md'
    if not source_file.exists():
        return

    with open(source_file, 'r', encoding='utf-8') as f:
        content = f.read()
        u_match = re.search(r'URL\*\*:\s*(https?://[^\s\n]+)', content)
        f_match = re.search(r'Flag\*\*:\s*([A-Z]{2})', content)
        if not u_match or not f_match:
            return
        base_url = u_match.group(1).strip()
        if not base_url.endswith('/'):
            base_url += '/'
        flag = f_match.group(1).strip()
        source_ref = f"sources/{source_file.name}"

    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=Retry(total=5, backoff_factor=2)))
    session.headers.update({'User-Agent': 'Mozilla/5.0 RokctAI-Scraper/1.0'})

    # 1. Bids Received Intelligence
    log_path = Path(__file__).resolve().parent.parent.parent.parent.parent / '.rokct' / 'agent' / 'logs' / 'musina_bids_intelligence.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    audit_entries = []

    try:
        b_resp = session.get(f"{base_url}bids-received/", timeout=30)
        if b_resp.status_code == 200:
            b_soup = BeautifulSoup(b_resp.text, 'lxml')
            for b_link in b_soup.find_all('a', href=True):
                b_text = b_link.get_text(" ", strip=True)
                if any(kw in b_text.upper() for kw in ["TENDER", "RFQ", "BID"]):
                    audit_entries.append(f"BID RECEIVED - {b_text}")
    except:
        pass

    # 2. RFQ Scraping
    try:
        response = session.get(f"{base_url}request-for-quotations/", timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')

        rfqs_found = {}
        for link in soup.find_all('a', href=True):
            text = link.get_text(" ", strip=True)
            url = link['href']
            if not url.startswith('http'):
                url = "https://www.musina.gov.za" + url

            if any(kw in text.upper() for kw in ["TENDER", "RFQ", "BID"]):
                audit_entries.append(text)

            rfq_match = re.search(r'RFQ\s*([\d/A-Z-]+)', text, re.I)
            if rfq_match:
                raw_full = rfq_match.group(1).strip().upper()
                # DEDUPLICATION: Extract just the numeric ID (e.g., 59 from 59/2024)
                base_id_match = re.search(r'(\d+)', raw_full)
                base_id = base_id_match.group(1) if base_id_match else raw_full.replace('/', '-')
                full_id = f"musina-rfq{base_id}"

                pub_date = ""
                # Try sibling text or parent container for publication date
                context_text = link.get_text()
                parent = link.find_parent()
                if parent:
                    context_text = parent.get_text(" ", strip=True)

                date_match = re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})', context_text)
                if date_match:
                    pub_date = date_match.group(1)

                if full_id not in rfqs_found:
                    rfqs_found[full_id] = {'text': text, 'url': url, 'pub': pub_date}
                else:
                    # Prefer PDF links if duplicates exist
                    if url.lower().endswith('.pdf'):
                        rfqs_found[full_id] = {'text': text, 'url': url, 'pub': pub_date}

        updates = 0
        failure_log = Path(__file__).resolve().parent.parent.parent.parent.parent / '.rokct' / 'agent' / 'logs' / 'pdf_extraction_failures.log'
        failure_log.parent.mkdir(parents=True, exist_ok=True)

        for fid, rdata in rfqs_found.items():
            card_path = resolve_card_path(tender_dir, fid)
            existing = ""
            if card_path and card_path.exists():
                with open(card_path, 'r', encoding='utf-8') as f:
                    existing = f.read()
                if "VERIFIED" in existing:
                    continue

            closing_date, is_est, found_pub = fetch_deep_details(rdata['url'], rdata['pub'])

            final_pub = normalize_date(found_pub) or normalize_date(rdata['pub']) or ""

            if not final_pub:
                with open(failure_log, 'a', encoding='utf-8') as fl:
                    fl.write(f"[{datetime.now().isoformat()}] Skipped: no published date found - {fid} ({rdata['url']})\n")
                continue

            # Apply (Estimated) suffix when date is a fallback, "See Documents" when unknown
            if closing_date:
                final_close = f"{closing_date} (Estimated)" if is_est else closing_date
            else:
                final_close = "See Documents"

            release = {
                "ocid": fid,
                "date": final_pub,
                "tender": {
                    "title": rdata['text'],
                    "procuringEntity": {"name": "Musina Local Municipality"},
                    "procurementMethodDetails": "Request for Quotation",
                    "province": "Limpopo",
                    "deliveryLocation": "Musina",
                    "category": "General Procurement",
                    "description": rdata['text'],
                    "tenderPeriod": {"endDate": final_close},
                    "documents": [{"title": "RFQ Document", "url": rdata['url']}]
                }
            }

            new_c = generate_md_fn(release, flag, source_ref, existing)
            if [l.strip() for l in existing.splitlines() if l.strip()] != [l.strip() for l in new_c.splitlines() if l.strip()]:
                write_path = resolve_write_path(tender_dir, fid)
                with open(write_path, 'w', encoding='utf-8', newline='\n') as fw:
                    fw.write(new_c)
                updates += 1

        if audit_entries:
            with open(log_path, 'a', encoding='utf-8') as log_f:
                log_f.write(f"\n--- Audit: {datetime.now().isoformat()} ---\n")
                for entry in audit_entries:
                    log_f.write(f"{entry}\n")

        print(f"  [+] Musina: Updated {updates} items. Intelligence log updated.")

    except Exception as e:
        print(f"  [Error] Musina sync failed: {e}")
        if "Timeout" in str(e) or "Max retries exceeded" in str(e):
            print("🚨 Musina site is likely broken or down. Skipping.")
