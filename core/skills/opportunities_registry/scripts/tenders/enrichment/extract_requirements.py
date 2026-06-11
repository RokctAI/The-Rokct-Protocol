import pdfplumber
import re
import sys
import json
import requests
import io
import os
import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = Path(__file__).resolve()
while not (BASE_DIR / '.rokct').exists():
    BASE_DIR = BASE_DIR.parent

LOG_FILE = BASE_DIR / ".rokct" / "agent" / "logs" / "requirement_extraction_failures.log"

def log_failure(tender_id, reason):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(LOG_FILE.parent, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {tender_id}: {reason}\n")

def extract_requirements_from_pdf(pdf_stream, tender_id):
    results = {
        "gate_1_mandatory": [],
        "gate_2_functional": [],
        "pricing_preference": "Unknown"
    }
    try:
        with pdfplumber.open(pdf_stream) as pdf:
            full_text = ""
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                full_text += page_text + "\n"

                # Table-based functional criteria
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row: continue
                        clean_row = [str(cell).strip() for cell in row if cell]
                        if len(clean_row) >= 2:
                            for cell in clean_row:
                                if cell.isdigit() and 0 < int(cell) <= 100:
                                    criterion = max(clean_row, key=len)
                                    if len(criterion) > 10 and not criterion.isdigit():
                                        results["gate_2_functional"].append({"criterion": criterion, "points": cell})
                                        break

            # Gate 1
            gate_1_patterns = [
                r'SBD\s*\d', r'MBD\s*\d', r'CSD\s*report', r'Tax\s*compliance',
                r'B-BBEE\s*(?:certificate|affidavit)', r'COIDA', r'Joint\s*Venture\s*Agreement',
                r'certified\s*copy', r'municipal\s*account', r'Letter\s*of\s*Good\s*Standing'
            ]
            for pattern in gate_1_patterns:
                matches = re.findall(pattern, full_text, re.I)
                for m in set(matches):
                    clean_m = re.sub(r'[\n\r]', ' ', m).strip()
                    if clean_m.upper() not in [x.upper() for x in results["gate_1_mandatory"]]:
                        results["gate_1_mandatory"].append(clean_m)

            # Gate 2 Regex Fallback
            weight_matches = re.findall(r'([A-Za-z\s]{10,100})\s+(\d{1,3})\s*(?:points|weight)', full_text, re.I)
            for criterion, points in weight_matches:
                if int(points) > 0:
                    if not any(criterion.strip().lower() in x["criterion"].lower() for x in results["gate_2_functional"]):
                        results["gate_2_functional"].append({"criterion": criterion.strip(), "points": points})

            # Pricing
            pp_match = re.search(r'(80/20|90/10)', full_text)
            if pp_match:
                results["pricing_preference"] = pp_match.group(1)

            if not results["gate_1_mandatory"] and not results["gate_2_functional"]:
                log_failure(tender_id, "No Gate 1 or Gate 2 requirements detected in PDF.")

    except Exception as e:
        log_failure(tender_id, f"PDF Processing Error: {str(e)}")
    return results

def generate_actionable_tasks(requirements, tender_id):
    tasks = []
    mandatory = requirements.get("gate_1_mandatory", [])
    if mandatory:
        sbds = sorted(list(set([m.upper() for m in mandatory if 'SBD' in m.upper() or 'MBD' in m.upper()])))
        if sbds:
            tasks.append(f"Complete and sign all mandatory forms: {', '.join(sbds)} | 1")
        if any('CSD' in m.upper() for m in mandatory):
            tasks.append("Download and attach latest Full CSD Report (ensure MAAA is correct) | 1")
        if any('TAX' in m.upper() for m in mandatory):
            tasks.append("Verify Tax Compliance status on SARS and provide valid PIN | 1")
        if any('B-BBEE' in m.upper() for m in mandatory):
            tasks.append("Attach valid B-BBEE Certificate or correctly commissioned Sworn Affidavit | 1")
        if any('MUNICIPAL' in m.upper() for m in mandatory):
            tasks.append("Obtain recent municipal accounts (<90 days) for the Company and all Directors | 2")

    functional = requirements.get("gate_2_functional", [])
    if functional:
        unique_functional = []
        seen = set()
        for item in functional:
            c_low = item["criterion"].lower()
            if c_low not in seen:
                unique_functional.append(item)
                seen.add(c_low)
        unique_functional.sort(key=lambda x: int(x['points']), reverse=True)
        for item in unique_functional[:2]:
            clean_crit = item['criterion'].split('\n')[0][:50]
            tasks.append(f"Draft detailed methodology addressing '{clean_crit}' ({item['points']} pts) | 3")
        tasks.append("Gather Trinity of Evidence (Appointment, SLA, Completion) for previous projects | 2")

    if not tasks:
        log_failure(tender_id, "Insufficient extraction — checklist used generic fallback")
        tasks = ["Analyze Tender Documents for specific requirements | 1", "Identify Mandatory Compliance items | 2", "Prepare Initial Response Proposal | 3"]
    return tasks[:5]

def update_tender_card(md_path, requirements):
    tender_id = md_path.stem
    with open(md_path, 'r', encoding='utf-8') as f:
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
        new_content = re.sub(pattern, new_checklist_block.strip(), content, flags=re.DOTALL)
    else:
        new_content = content.strip() + "\n\n" + new_checklist_block

    with open(md_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_content)

def process_file(md_file):
    tender_id = md_file.stem
    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            md_content = f.read()
        url_match = re.search(r'- \*\*Direct Link\*\*:\s*(https?://[^\s\n]+)', md_content)
        if not url_match:
            log_failure(tender_id, "No Direct Link found in card.")
            return False
        url = url_match.group(1).strip()
        if not url.lower().endswith(".pdf"):
            log_failure(tender_id, f"Direct Link is not a PDF: {url}")
            return False

        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
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
            with open(todo_path, 'r', encoding='utf-8') as f:
                todo_data = json.load(f)
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
        print("todo.json not found or empty — falling back to full scan")
        all_md_files = list(tender_dir.rglob("*.md"))
        target_files = []
        for f in all_md_files:
            if f.name in ["template.md", "registry_audit_log.md"] or f.name.endswith("_content.md"):
                continue
            if f.parent == tender_dir or f.stem == f.parent.name:
                target_files.append(f)
    else:
        # Safety filter even for todo.json items
        filtered_targets = []
        for f in target_files:
            if not f.exists():
                continue
            if f.name in ["template.md", "registry_audit_log.md"] or f.name.endswith("_content.md"):
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
