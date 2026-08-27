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

import sys
import re
from pathlib import Path
from datetime import datetime

# Add internal paths to sys.path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir / "api"))
sys.path.append(str(current_dir / "scrapers"))

import ocds
import musina

# Walk up to the real repo root instead of a fixed parent-count: this script
# is invoked from more than one on-disk depth (the canonical
# .rokct/skills/.rok/opportunities_registry/scripts/ path, and the
# self-relocated .rokct/tmp/opportunities/ cache path used by
# registry_orchestrator/index.py's wrapper), and a fixed .parent chain
# silently lands one level short (inside .rokct/) for the latter.
BASE_DIR = Path(__file__).resolve()
while not (BASE_DIR / ".rokct").exists():
    BASE_DIR = BASE_DIR.parent
TENDER_DIR = BASE_DIR / "03_tenders"
SOURCES_DIR = TENDER_DIR / "sources"


def generate_md(release, flag, source_ref, existing_content=""):
    """Universal Markdown Generator with AI Preservation."""
    tender = release.get("tender", {})
    ocid = release.get("ocid")

    # --- BASIC DATA GENERATION ---
    title = tender.get("title", "Untitled Opportunity")
    institution = tender.get("procuringEntity", {}).get("name", "Unknown")
    t_type = tender.get(
        "procurementMethodDetails", tender.get("mainProcurementCategory", "Tender")
    )
    province = tender.get("province", "National")
    published = release.get("date", "")[:10]
    closing = (tender.get("tenderPeriod", {}).get("endDate", "") or "").replace(
        "T", " "
    )[:16]
    location = tender.get("deliveryLocation", "See Documents")
    category = tender.get("category", "General")
    description = tender.get("description", "No description provided.")

    # Briefing
    briefing = tender.get("briefingSession", {})
    has_briefing = "Yes" if briefing.get("isSession") else "No"
    compulsory = "Yes" if briefing.get("compulsory") else "No"
    b_date = (
        briefing.get("date", "N/A").replace("T", " ")[:16]
        if briefing.get("date")
        else "N/A"
    )
    b_venue = briefing.get("venue", "N/A")

    # Documents
    raw_docs = tender.get("documents", [])
    processed_docs = sorted(
        [(doc.get("title", "Document"), doc.get("url", "#")) for doc in raw_docs],
        key=lambda x: (x[0], x[1]),
    )
    docs_md = (
        "".join([f"    - [{t}]({u})\n" for t, u in processed_docs])
        or "    - No documents listed.\n"
    )
    direct_link = (
        processed_docs[0][1]
        if processed_docs
        else "https://www.etenders.gov.za/Home/opportunities?id=1"
    )

    # --- DATA COMPLETENESS ---
    # A scraped card missing required fields must say so visibly instead of
    # reading identically to a complete one ('Untitled Opportunity' with the
    # generic etenders link looked like a real card).
    missing = []
    if not tender.get("title"):
        missing.append("title")
    if not closing or closing.startswith("See Documents"):
        missing.append("closing date")
    if not re.match(r"\d{4}-\d{2}-\d{2}", published):
        missing.append("publication date")
    if not processed_docs:
        missing.append("source link")
    completeness = (
        f"INCOMPLETE — missing: {', '.join(missing)}" if missing else "COMPLETE"
    )

    # --- AI SECTION PRESERVATION ---
    # Default Checklist
    ai_section = """## AI Checklist (Jules)
<!-- This section is populated by Jules during enrichment. -->
- [ ] Review Tender Documents | 1
- [ ] Prepare Initial Response | 3
"""
    # If the card exists and has an AI section, we preserve Jules' work!
    if "## AI Checklist (Jules)" in existing_content:
        # Extract everything from the Jules header to the end
        match = re.search(r"(## AI Checklist \(Jules\)[\s\S]*)$", existing_content)
        if match:
            ai_section = match.group(1).strip() + "\n"

    # --- FINAL ASSEMBLY ---
    return f"""# Tender Opportunity: {title}

## Quick Stats
- **Tender Number**: {ocid}
- **Institution**: {institution}
- **Source Card**: {source_ref}
- **Flag**: {flag}
- **Tender Type**: {t_type}
- **Province**: {province}
- **Date Published**: {published}
- **Closing Date**: {closing}
- **Place Required**: {location}

## Detailed Description
### Category
{category}

### Tender Description
{description}

## Briefing Session
- **Is there a briefing session?**: {has_briefing}
- **Is it compulsory?**: {compulsory}
- **Briefing Date and Time**: {b_date}
- **Briefing Venue**: {b_venue}

## Enquiries
- **Contact Person**: {tender.get("contactPerson", {}).get("name", "N/A")}
- **Email**: {tender.get("contactPerson", {}).get("email", "N/A")}
- **Telephone**: {tender.get("contactPerson", {}).get("telephoneNumber", "N/A")}

## Documents & Links
- **Direct Link**: {direct_link}
- **Tender Documents**:
{docs_md}

## Audit & Status
- **Status**: ACTIVE
- **Data Completeness**: {completeness}
- **Last Verified**: {datetime.now().strftime("%Y-%m-%d")}

{ai_section}"""


if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] --- Tender Engine (AI-Aware) ---")

    # Each sub-sync is isolated: an unexpected crash in one source must not
    # abort the other, nor fail the workflow step (the sync-engine step runs
    # the grants and equity fetchers after this script under bash -e, so an
    # uncaught exception here used to cancel those syncs entirely).
    # Run API Syncs (OCDS)
    try:
        ocds.run_sync(TENDER_DIR, SOURCES_DIR, generate_md)
    except Exception as e:
        print(f"  [Error] OCDS sync crashed: {e}")

    # Run Scrapers (Musina)
    try:
        musina.run_sync(TENDER_DIR, SOURCES_DIR, generate_md)
    except Exception as e:
        print(f"  [Error] Musina sync crashed: {e}")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Sync Complete.")
