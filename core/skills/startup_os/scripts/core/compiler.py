import os
import re
import glob
import json
from pathlib import Path

# Try to import pypdf gracefully
try:
    import pypdf
except ImportError:
    pypdf = None

# Relative path mapping: Import parser from same sibling folder
from core.parser import parse_questions_md

# Bidirectional footer mapping rules
FOOTER_MAPS = {
    "business": {
        "09_business_model_canvas.md": [
            ("10_lean_canvas.md", "Venture Strategic Lean Canvas", "Lean Canvas"),
            ("business_plan_on_a_page.md", "1-Page Commercial Mechanics", "Business Plan on a Page"),
            ("financial_plan_on_a_page.md", "1-Page Financial Projections", "Financial Plan on a Page")
        ],
        "10_lean_canvas.md": [
            ("09_business_model_canvas.md", "High-Level 9-Box Canvas Grid", "Business Model Canvas"),
            ("business_plan_on_a_page.md", "1-Page Commercial Mechanics", "Business Plan on a Page")
        ],
        "business_plan_on_a_page.md": [
            ("09_business_model_canvas.md", "High-Level 9-Box Canvas Grid", "Business Model Canvas"),
            ("10_lean_canvas.md", "Venture Strategic Lean Canvas", "Lean Canvas"),
            ("financial_plan_on_a_page.md", "1-Page Financial Projections", "Financial Plan on a Page")
        ],
        "financial_plan_on_a_page.md": [
            ("09_business_model_canvas.md", "High-Level 9-Box Canvas Grid", "Business Model Canvas"),
            ("business_plan_on_a_page.md", "1-Page Commercial Mechanics", "Business Plan on a Page")
        ]
    },
    "life": {
        "09_life_model_canvas.md": [
            ("10_life_lean_canvas.md", "Personal Lean Growth Canvas", "Personal Lean Canvas"),
            ("life_plan_on_a_page.md", "1-Page Life Rhythm Plan", "Life Plan on a Page")
        ],
        "10_life_lean_canvas.md": [
            ("09_life_model_canvas.md", "Personal Life Model Canvas", "Personal Life Canvas"),
            ("life_plan_on_a_page.md", "1-Page Life Rhythm Plan", "Life Plan on a Page")
        ],
        "life_plan_on_a_page.md": [
            ("09_life_model_canvas.md", "Personal Life Model Canvas", "Personal Life Canvas"),
            ("10_life_lean_canvas.md", "Personal Lean Growth Canvas", "Personal Lean Canvas"),
            ("health_plan_on_a_page.md", "1-Page Biological Conditioning Plan", "Health Plan on a Page"),
            ("financial_legacy_plan_on_a_page.md", "1-Page Multigenerational Stewardship Plan", "Financial Legacy Plan on a Page")
        ],
        "health_plan_on_a_page.md": [
            ("life_plan_on_a_page.md", "1-Page Life Rhythm Plan", "Life Plan on a Page")
        ],
        "financial_legacy_plan_on_a_page.md": [
            ("life_plan_on_a_page.md", "1-Page Life Rhythm Plan", "Life Plan on a Page")
        ]
    }
}

def parse_compliance_pdfs_standalone(compliance_dir, folder_name, primary_base=None):
    """
    Stand-alone PDF parsing implementation that mirrors the monorepo logic.
    Gracefully handles missing pypdf or missing compliance files by using placeholders
    and answers parsed from questions.md.
    """
    trading_name = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', folder_name).strip()
    
    # 1. Detect South Africa base (using word boundaries for short acronyms)
    is_sa = False
    if primary_base:
        base_lower = str(primary_base).lower()
        words = re.findall(r"\b\w+\b", base_lower)
        if "sa" in words or "za" in words or "south africa" in base_lower:
            is_sa = True

    # If compliance folder exists, we can also infer SA base
    if os.path.exists(compliance_dir):
        is_sa = True

    # Build default fallbacks based on SA vs International
    if is_sa:
        data = {
            "company_name": f"{trading_name} (Pty) Ltd",
            "reg_number": "Pending — add Business Registration Certificate.pdf",
            "reg_date": "Pending — add Business Registration Certificate.pdf",
            "tax_number": "Pending — add Tax_Pin.pdf",
            "registered_office": "Pending — add Business Registration Certificate.pdf",
            "postal_address": "Pending — add Business Registration Certificate.pdf",
            "bee_level": "Level 1 Contributor",
            "bee_procurement_recognition": "135%",
            "bee_black_ownership": "100%",
            "bee_youth_owned": "100%",
            "bee_disabled_owned": "0%",
            "bee_rural_owned": "0%",
            "bee_cert_number": "Pending — add BEE.pdf",
            "bee_issue_date": "Pending",
            "bee_expiry_date": "Pending",
            "tax_pin": "Pending — add Tax_Pin.pdf",
            "tax_pin_issue_date": "Pending",
            "tax_pin_expiry_date": "Pending",
            "tax_compliance_status": "Good Standing",
            "trademarks": []
        }
    else:
        # Non-SA Venture
        data = {
            "company_name": f"{trading_name} LLC",
            "reg_number": "Pending — add Business Registration Certificate",
            "reg_date": "Pending — add Business Registration Certificate",
            "tax_number": "Pending — add Tax ID Certificate",
            "registered_office": "Pending — add Registration Document",
            "postal_address": "Pending — add Registration Document",
            "bee_level": "Not Applicable (International Venture)",
            "bee_procurement_recognition": "Not Applicable",
            "bee_black_ownership": "Not Applicable",
            "bee_youth_owned": "Not Applicable",
            "bee_disabled_owned": "Not Applicable",
            "bee_rural_owned": "Not Applicable",
            "bee_cert_number": "Not Applicable",
            "bee_issue_date": "Not Applicable",
            "bee_expiry_date": "Not Applicable",
            "tax_pin": "Not Applicable",
            "tax_pin_issue_date": "Not Applicable",
            "tax_pin_expiry_date": "Not Applicable",
            "tax_compliance_status": "Not Applicable",
            "trademarks": []
        }

    if not pypdf:
        print("[Warning] pypdf is not installed. Skipping PDF extraction; relying on placeholders & answers.")
        return data

    if not os.path.exists(compliance_dir):
        print(f"[Warning] Compliance folder '{compliance_dir}' not found. Using standard default fallbacks.")
        return data

    # 1. Parse CIPC Business Registration Certificate.pdf
    cipc_path = os.path.join(compliance_dir, "Business Registration Certificate.pdf")
    if os.path.exists(cipc_path):
        try:
            reader = pypdf.PdfReader(cipc_path)
            full_text = ""
            for page in reader.pages:
                full_text += page.extract_text() + "\n"

            reg_match = re.search(r"(\d{4}\s*/\s*\d{6}\s*/\s*\d{2})", full_text)
            if reg_match:
                data["reg_number"] = re.sub(r"\s+", "", reg_match.group(1))

            name_match = re.search(r"Enterprise Name:\s*([A-Z\s\(\)]+)", full_text, re.IGNORECASE)
            if not name_match:
                name_match = re.search(r"Enterprise Name\s*([A-Z\s\(\)]+)", full_text, re.IGNORECASE)
            if name_match:
                data["company_name"] = name_match.group(1).strip()

            tax_match = re.search(r"(\d+)\s*TAX\s*Number", full_text, re.IGNORECASE)
            if tax_match:
                data["tax_number"] = tax_match.group(1).strip()

            reg_date_match = re.search(r"Registration Date[:\s]+(\d{1,2}\s+\w+\s+\d{4}|\d{4}-\d{2}-\d{2})", full_text, re.IGNORECASE)
            if reg_date_match:
                data["reg_date"] = reg_date_match.group(1).strip()

            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            idx = -1
            for i, line in enumerate(lines):
                if "addresses" in line.lower():
                    idx = i
                    break

            if idx != -1:
                addr_lines = []
                for j in range(idx + 1, min(idx + 15, len(lines))):
                    l_val = lines[j]
                    if any(x in l_val.lower() for x in ["registration date", "business start date", "enterprise type", "active members", "directors", "appointment", "tax"]):
                        break
                    addr_lines.append(l_val)

                postal_parts = []
                reg_parts = []
                in_reg = False
                for part in addr_lines:
                    if not in_reg:
                        postal_parts.append(part)
                        if re.match(r"^\d{4}$", part):
                            in_reg = True
                    else:
                        reg_parts.append(part)
                        if re.match(r"^\d{4}$", part):
                            break

                def clean_parts(parts):
                    seen = []
                    for p in parts:
                        if p not in seen:
                            seen.append(p)
                    return ", ".join(seen)

                if postal_parts:
                    data["postal_address"] = clean_parts(postal_parts)
                if reg_parts:
                    data["registered_office"] = clean_parts(reg_parts)

            print(f"  Successfully parsed CIPC: {data['company_name']}")
        except Exception as e:
            print(f"  Error parsing CIPC PDF: {e}")

    # 2. Parse BEE.pdf
    bee_path = os.path.join(compliance_dir, "BEE.pdf")
    if os.path.exists(bee_path):
        try:
            reader = pypdf.PdfReader(bee_path)
            full_text = ""
            for page in reader.pages:
                full_text += page.extract_text() + "\n"

            level_match = re.search(r"(LEVEL\s+\d+\s+CONTRIBUTOR)", full_text, re.IGNORECASE)
            if level_match:
                data["bee_level"] = level_match.group(1).strip()

            proc_match = re.search(r"(\d+%)\s*PROCUREMENT\s*RECOGNITION", full_text, re.IGNORECASE)
            if proc_match:
                data["bee_procurement_recognition"] = proc_match.group(1).strip()

            cert_match = re.search(r"Certificate Number\s*(\d+)", full_text, re.IGNORECASE)
            if not cert_match:
                cert_match = re.search(r"Tracking Number:\s*(\d+)", full_text, re.IGNORECASE)
            if cert_match:
                data["bee_cert_number"] = cert_match.group(1).strip()

            dates = re.findall(r"(\d{1,2}-[a-zA-Z]+-\d{4})", full_text)
            if len(dates) >= 2:
                data["bee_issue_date"] = dates[-2]
                data["bee_expiry_date"] = dates[-1]

            bo_match = re.search(r"(\d+%)\s*BLACK\s*OWNERSHIP", full_text, re.IGNORECASE)
            if bo_match:
                data["bee_black_ownership"] = bo_match.group(1).strip()

            yo_match = re.search(r"youth\s+as\s+defined.*?\n\s*(\d+%)", full_text, re.DOTALL | re.IGNORECASE)
            if yo_match:
                data["bee_youth_owned"] = yo_match.group(1).strip()

            print(f"  Successfully parsed BEE: {data['bee_level']}")
        except Exception as e:
            print(f"  Error parsing BEE PDF: {e}")

    # 3. Parse Tax_Pin.pdf
    tax_pin_path = os.path.join(compliance_dir, "Tax_Pin.pdf")
    if os.path.exists(tax_pin_path):
        try:
            reader = pypdf.PdfReader(tax_pin_path)
            full_text = ""
            for page in reader.pages:
                full_text += page.extract_text() + "\n"

            tax_ref_match = re.search(r"Taxpayer Reference Number[:\s]+(?:IT\s*-\s*)?(\d+)", full_text, re.IGNORECASE)
            if not tax_ref_match:
                tax_ref_match = re.search(r"Tax reference No:\s*(\d+)", full_text, re.IGNORECASE)
            if tax_ref_match:
                data["tax_number"] = tax_ref_match.group(1).strip()

            pin_match = re.search(r"\bPIN\s+([A-Z0-9]{8,12})\b", full_text)
            if pin_match:
                data["tax_pin"] = pin_match.group(1).strip()

            pin_issue_match = re.search(r"Issue Date:\s*([\d/\-]+)", full_text, re.IGNORECASE)
            if pin_issue_match:
                data["tax_pin_issue_date"] = pin_issue_match.group(1).strip()

            pin_expiry_match = re.search(r"PIN Expiry Date\s+([\d/\-]+)", full_text, re.IGNORECASE)
            if pin_expiry_match:
                data["tax_pin_expiry_date"] = pin_expiry_match.group(1).strip()

            print(f"  Successfully parsed Tax Pin: {data['tax_pin']}")
        except Exception as e:
            print(f"  Error parsing Tax Pin PDF: {e}")

    # 4. Parse Overrides Layer if present
    overrides_path = os.path.join(compliance_dir, "compliance_overrides.json")
    if os.path.exists(overrides_path):
        try:
            with open(overrides_path, 'r', encoding='utf-8') as f:
                overrides = json.load(f)
            for k, v in overrides.items():
                if v is not None and not k.startswith("_"):
                    data[k] = v
            print(f"  Applied compliance overrides from json.")
        except Exception as e:
            print(f"  Error applying overrides: {e}")

    # 5. Entity Suffix and BEE Conditioning logic based on final registration format
    final_reg = data.get("reg_number", "")
    if final_reg and not final_reg.startswith("Pending"):
        # Match South African pattern YYYY/NNNNNN/EE or YYYY / NNNNNN / EE
        sa_reg_match = re.search(r"(\d{4})\s*/\s*(\d{6})\s*/\s*(\d{2})", final_reg)
        if sa_reg_match:
            is_sa = True
            entity_code = sa_reg_match.group(3)
            
            # Map entity code to standard SA suffix
            if entity_code == "07":
                entity_suffix = " (Pty) Ltd"
            elif entity_code == "28":
                entity_suffix = " CC"
            elif entity_code == "06":
                entity_suffix = " NPC"
            elif entity_code == "08":
                entity_suffix = " Ltd"
            elif entity_code == "21":
                entity_suffix = " Inc"
            else:
                entity_suffix = " (Pty) Ltd"

            # Clean and format company name to append the correct dynamic suffix
            current_company_name = data.get("company_name", trading_name)
            
            # Remove any standard suffixes from the end of the parsed name to prevent duplicates
            clean_name = current_company_name
            for sfx in ["(Pty) Ltd", "PTY LTD", "Pty Ltd", "CC", "NPC", "Ltd", "LTD", "Inc", "INC", "LLC"]:
                if clean_name.endswith(sfx):
                    clean_name = clean_name[:-len(sfx)].strip()
                elif clean_name.endswith(f" ({sfx})"):
                    clean_name = clean_name[:-len(f" ({sfx})")].strip()

            data["company_name"] = f"{clean_name}{entity_suffix}"

    # If the final check determines it is not in SA, ensure BEE & Tax Pin are conditionalized out
    if not is_sa:
        data["bee_level"] = "Not Applicable (International Venture)"
        data["bee_procurement_recognition"] = "Not Applicable"
        data["bee_black_ownership"] = "Not Applicable"
        data["bee_youth_owned"] = "Not Applicable"
        data["bee_disabled_owned"] = "Not Applicable"
        data["bee_rural_owned"] = "Not Applicable"
        data["bee_cert_number"] = "Not Applicable"
        data["bee_issue_date"] = "Not Applicable"
        data["bee_expiry_date"] = "Not Applicable"
        data["tax_pin"] = "Not Applicable"
        data["tax_pin_issue_date"] = "Not Applicable"
        data["tax_pin_expiry_date"] = "Not Applicable"
        data["tax_compliance_status"] = "Not Applicable"

    return data


def parse_trademark_pdfs_standalone(trademark_dir):
    """Parses CIPC trademark documents from the monorepo trademark folder if they exist."""
    trademarks = []
    if not pypdf or not os.path.exists(trademark_dir):
        return trademarks

    tm_files = glob.glob(os.path.join(trademark_dir, "*.pdf"))
    for tm_path in tm_files:
        try:
            reader = pypdf.PdfReader(tm_path)
            full_text = ""
            for page in reader.pages:
                full_text += page.extract_text() + "\n"

            tm = {
                "application_number": "Pending",
                "application_date": "Pending",
                "mark": "Pending",
                "status": "Pending",
                "international_class": "Pending",
                "nature": "Ordinary",
                "specification": "Pending",
                "generated_date": "Pending"
            }

            app_match = re.search(r"21\s*Official Application No\.\s*(\d+/\d+)", full_text, re.IGNORECASE)
            if app_match:
                tm["application_number"] = app_match.group(1).strip()

            date_match = re.search(r"22\s*Application date\s*([\d\-]+)", full_text, re.IGNORECASE)
            if date_match:
                tm["application_date"] = date_match.group(1).strip()

            mark_match = re.search(r"54\s*Representation of Trade mark\s*\n([^\n]+)", full_text, re.IGNORECASE)
            if mark_match:
                tm["mark"] = mark_match.group(1).strip()

            status_match = re.search(r"TRADE MARK STATUS:\s*(\S+)", full_text, re.IGNORECASE)
            if status_match:
                tm["status"] = status_match.group(1).strip()

            class_match = re.search(r"51\s*International Classification\s*(\d+)", full_text, re.IGNORECASE)
            if class_match:
                tm["international_class"] = class_match.group(1).strip()

            trademarks.append(tm)
            print(f"  Parsed trademark CIPC doc: {tm['mark']}")
        except Exception as e:
            print(f"  Error parsing trademark PDF: {e}")

    return trademarks


def resolve_workspace_root():
    import sys
    main_file = None
    try:
        import __main__
        if hasattr(__main__, "__file__") and __main__.__file__:
            main_file = os.path.abspath(__main__.__file__)
    except Exception:
        pass
        
    if not main_file and sys.argv and sys.argv[0]:
        main_file = os.path.abspath(sys.argv[0])

    resolved_root = None
    if main_file:
        # Search upwards for the "skills" folder
        current = main_file
        while True:
            parent = os.path.dirname(current)
            if parent == current:
                break
            if os.path.basename(current) == "skills":
                resolved_root = parent
                break
            current = parent

        if not resolved_root:
            # Search upwards for "startup_os"
            current = main_file
            while True:
                parent = os.path.dirname(current)
                if parent == current:
                    break
                if os.path.basename(current) == "startup_os":
                    resolved_root = parent
                    break
                current = parent

    if not resolved_root:
        resolved_root = os.getcwd()

    # Standardize on StartupOS directory under the resolved project root
    if resolved_root:
        # If the resolved root is .rokct, the project root is the parent of .rokct
        if os.path.basename(resolved_root) == ".rokct":
            project_root = os.path.dirname(resolved_root)
        # If the resolved root is core (e.g. The-Rokct-Protocol/core), the project root is the parent of core
        elif os.path.basename(resolved_root) == "core":
            project_root = os.path.dirname(resolved_root)
        else:
            project_root = resolved_root
            
        return os.path.join(project_root, "StartupOS")

    return os.path.join(os.getcwd(), "StartupOS")


def compile_instance(instance_type, instance_name, monorepo_root=None):
    """
    Compiles templates for a specific instance.
    - Loads template folder `templates/{instance_type}/`
    - Parses questions from `instances/{instance_type}/{instance_name}/questions.md`
    - Searches for compliance in `monorepo_root/Compliance/{instance_name}`
    - Performs placeholder interpolation
    - Inject Document versioning control & bidirectional links
    - Writes outcome to `instances/{instance_type}/{instance_name}/output/`
    """
    print(f"\n[StartupOS] Compiling {instance_type.upper()} suite for: {instance_name}...")

    active_startup_os_root = resolve_workspace_root()

    questions_path = os.path.join(active_startup_os_root, "instances", instance_type, instance_name, "questions.md")
    output_dir = os.path.join(active_startup_os_root, "instances", instance_type, instance_name, "output")

    # Templates are sourced from the active StartupOS workspace templates folder
    templates_dir = os.path.join(active_startup_os_root, "templates", instance_type)

    if not os.path.exists(questions_path):
        raise FileNotFoundError(f"Missing strategic source of truth: {questions_path}")
    if not os.path.exists(templates_dir):
        raise FileNotFoundError(f"Missing template folder: {templates_dir}")

    # 1. Parse Strategic questions
    q_data = parse_questions_md(questions_path)

    # Calculate fallback dynamic trading name from camelCase folder
    trading_name = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', instance_name).strip()

    # Pre-populate base replacement dictionary with all parsed question fields
    replacements = {
        "trading_name": trading_name,
        "company_name": f"{trading_name} (Pty) Ltd",
        "full_name": q_data.get("full_name", trading_name),
        "primary_base": q_data.get("primary_base", "Pending"),
        "life_purpose": q_data.get("life_purpose", "Pending"),
        "wellness_focus": q_data.get("wellness_focus", "Pending"),
        "key_relationships": q_data.get("key_relationships", "Pending"),
    }

    # Merge all questions into replacements
    for key, val in q_data.items():
        replacements[key] = val

    # 2. Integrate Backwards-Compatible Compliance PDF Sourcing
    if instance_type == "business":
        if not monorepo_root:
            # Attempt default path relative to standard desktop workspace
            monorepo_root = "C:\\Users\\sinya\\Desktop\\RokctAI\\Monorepo"
        
        compliance_dir = os.path.join(monorepo_root, "Compliance", instance_name)
        trademark_dir = os.path.join(monorepo_root, "trademark", instance_name)

        # Parse compliance documents from monorepo
        comp_data = parse_compliance_pdfs_standalone(compliance_dir, instance_name, primary_base=replacements.get("primary_base"))
        tm_data = parse_trademark_pdfs_standalone(trademark_dir)

        # Inject compliance fields
        for key, val in comp_data.items():
            if val:
                replacements[key] = val

        # Handle trademarks dynamic line injection
        tm_lines = []
        for tm in tm_data:
            line = f'"{tm["mark"]}" | App {tm["application_number"]} | Filed: {tm["application_date"]} | Class {tm["international_class"]} ({tm["nature"]}) | Status: {tm["status"]}'
            tm_lines.append(line)
        
        replacements["trademarks_details"] = "  • " + "\n  • ".join(tm_lines) if tm_lines else "  • No registered trademarks filed under CIPC."

        # 3. Dynamic Financial Outlook Calculations
        y1 = q_data.get("projected_year_1", "R1.0M revenue | R200k Net Profit | Phase 1 launch.")
        y2 = q_data.get("projected_year_2", "R3.0M revenue | R800k Net Profit | Phase 2 scaling.")
        y3 = q_data.get("projected_year_3", "R8.0M revenue | R2.5M Net Profit | National expansion.")

        historical_2024 = q_data.get("historical_turnover_2024", "R0 (Pre-revenue)")
        historical_2025 = q_data.get("historical_turnover_2025", "R0 (Pre-revenue)")
        historical_2026_ytd = q_data.get("historical_turnover_2026_ytd", "R0 (Pre-revenue)")

        # Summary Block Generation
        fin_summary = f"""*   **Year 1 Projections**: {y1}
*   **Year 2 Projections**: {y2}
*   **Year 3 Projections**: {y3}
*   **Historical Base**: 2024: {historical_2024} | 2025: {historical_2025} | 2026 YTD: {historical_2026_ytd}"""
        
        # Grid block for Lean Canvas Markdown Table
        y1_rev = y1.split('|')[0].strip() if '|' in y1 else y1
        y2_rev = y2.split('|')[0].strip() if '|' in y2 else y2
        y3_rev = y3.split('|')[0].strip() if '|' in y3 else y3

        fin_grid_rev = f"• **Year 1**: {y1_rev}<br>• **Year 2**: {y2_rev}<br>• **Year 3**: {y3_rev}"

        replacements["fin_summary"] = fin_summary
        replacements["fin_grid_rev"] = fin_grid_rev

    # Ensure all missing keys in replacements defaults to an empty string to avoid rendering issues
    # Scan template files to find placeholder tags
    template_files = glob.glob(os.path.join(templates_dir, "*.md"))
    all_placeholders = set()
    for t_file in template_files:
        with open(t_file, 'r', encoding='utf-8') as f:
            content = f.read()
        found = re.findall(r"\{\{([a-zA-Z0-9_]+)\}\}", content)
        all_placeholders.update(found)

    for p_holder in all_placeholders:
        replacements.setdefault(p_holder, f"Pending — update questions.md for '{p_holder}'")

    # 4. Process Rendering & Write Output
    os.makedirs(output_dir, exist_ok=True)
    
    for t_file in template_files:
        filename = os.path.basename(t_file)
        with open(t_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Step A: Placeholder substitution
        rendered_content = content
        for key, val in replacements.items():
            rendered_content = rendered_content.replace(f"{{{{{key}}}}}", str(val))

        # Step B: Inject ROKCT Protocol Document Version Control Block
        version_block = """---

> [!IMPORTANT]
> **Document Version Control**:
> *   **Version**: `1.0.0` (Venture-Grade Release)
> *   **Last Updated**: `2026-05-22`
> *   **Security ID**: `sinyage.1aedb8` (POPIA Segregated)

"""
        # Place version block after primary title rule (only standalone lines containing '---')
        lines = rendered_content.split("\n")
        split_idx = -1
        for idx, l in enumerate(lines):
            if l.strip() == "---":
                split_idx = idx
                break

        if split_idx != -1:
            lines[split_idx] = version_block.strip()
            rendered_content = "\n".join(lines)
        else:
            if len(lines) >= 2 and lines[0].startswith("#") and lines[1].startswith("##"):
                rendered_content = lines[0] + "\n" + lines[1] + "\n\n" + version_block + "\n".join(lines[2:])
            else:
                rendered_content = version_block + rendered_content

        # Step C: Inject Bidirectional Dependencies Footers
        footer_links = FOOTER_MAPS.get(instance_type, {}).get(filename)
        if footer_links:
            footer_block = "\n\n---\n\n## Strategic Document Mappings & Dependencies\n\n"
            footer_block += "> [!NOTE]\n"
            footer_block += "> **Bidirectional Strategic Alignment Map**:\n"
            for link_file, link_desc, link_title in footer_links:
                footer_block += f"> *   **[{link_title}]({link_file})**: {link_desc}\n"
            
            rendered_content += footer_block

        # Write rendered file
        out_path = os.path.join(output_dir, filename)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(rendered_content)
        
        print(f"  Generated compiled file: {filename}")

    print(f"[Success] Successfully completed compilation! Output files are staged in: {output_dir}")
