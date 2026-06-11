# Licensed under the MIT License.
# Copyright 2024 RokctAI

import sys
import re
from pathlib import Path
from datetime import datetime

# Add internal paths to sys.path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir / 'api'))
sys.path.append(str(current_dir / 'scrapers'))

import ocds
import musina

BASE_DIR = Path(__file__).parent.parent.parent.parent
TENDER_DIR = BASE_DIR / '03_tenders'
SOURCES_DIR = TENDER_DIR / 'sources'

def generate_md(release, flag, source_ref, existing_content=""):
    """Universal Markdown Generator with AI Preservation."""
    tender = release.get('tender', {})
    ocid = release.get('ocid')
    
    # --- BASIC DATA GENERATION ---
    title = tender.get('title', 'Untitled Opportunity')
    institution = tender.get('procuringEntity', {}).get('name', 'Unknown')
    t_type = tender.get('procurementMethodDetails', tender.get('mainProcurementCategory', 'Tender'))
    province = tender.get('province', 'National')
    published = release.get('date', '')[:10]
    closing = (tender.get('tenderPeriod', {}).get('endDate', '') or "").replace('T', ' ')[:16]
    location = tender.get('deliveryLocation', 'See Documents')
    category = tender.get('category', 'General')
    description = tender.get('description', 'No description provided.')

    # Briefing
    briefing = tender.get('briefingSession', {})
    has_briefing = "Yes" if briefing.get('isSession') else "No"
    compulsory = "Yes" if briefing.get('compulsory') else "No"
    b_date = briefing.get('date', 'N/A').replace('T', ' ')[:16] if briefing.get('date') else "N/A"
    b_venue = briefing.get('venue', 'N/A')
    
    # Documents
    raw_docs = tender.get('documents', [])
    processed_docs = sorted([(doc.get('title', 'Document'), doc.get('url', '#')) for doc in raw_docs], key=lambda x: (x[0], x[1]))
    docs_md = "".join([f"    - [{t}]({u})\n" for t, u in processed_docs]) or "    - No documents listed.\n"
    direct_link = processed_docs[0][1] if processed_docs else "https://www.etenders.gov.za/Home/opportunities?id=1"

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
        match = re.search(r'(## AI Checklist \(Jules\)[\s\S]*)$', existing_content)
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
- **Contact Person**: {tender.get('contactPerson', {}).get('name', 'N/A')}
- **Email**: {tender.get('contactPerson', {}).get('email', 'N/A')}
- **Telephone**: {tender.get('contactPerson', {}).get('telephoneNumber', 'N/A')}

## Documents & Links
- **Direct Link**: {direct_link}
- **Tender Documents**:
{docs_md}

## Audit & Status
- **Status**: ACTIVE
- **Last Verified**: {datetime.now().strftime('%Y-%m-%d')}

{ai_section}"""

if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] --- Tender Engine (AI-Aware) ---")
    
    # Run API Syncs (OCDS)
    ocds.run_sync(TENDER_DIR, SOURCES_DIR, generate_md)
    
    # Run Scrapers (Musina)
    musina.run_sync(TENDER_DIR, SOURCES_DIR, generate_md)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Sync Complete.")
