import os
import re
import shutil
from pathlib import Path
from core.compiler import compile_instance, resolve_workspace_root

def _parse_instance_details(filepath):
    """Helper to extract instance_type and instance_name from a questions.md path."""
    normalized_path = Path(filepath).resolve()
    parts = normalized_path.parts
    if "instances" in parts:
        idx = parts.index("instances")
        if idx + 2 < len(parts):
            return parts[idx + 1].lower(), parts[idx + 2]
    # Regex fallback
    match = re.search(r"instances[/\\](business|life)[/\\]([^/\\]+)", str(filepath), re.IGNORECASE)
    if match:
        return match.group(1).lower(), match.group(2)
    return None, None


def update_profile_answer(filepath, question_label, new_answer):
    """
    Programmatically updates the answer to a specific strategic question in questions.md.
    Preserves all file headers, spacing, and formatting.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Profile questions file not found: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    updated = False
    
    # Locate the target question line
    for idx, line in enumerate(lines):
        q_match = re.match(r"\*\s+\*\*([^*]+)\*\*:\s*(.*)", line)
        if q_match:
            q_label = q_match.group(1).strip()
            # Compare canonicalized labels
            c_target = re.sub(r"[^a-z0-9_]+", "_", question_label.lower()).strip("_")
            c_current = re.sub(r"[^a-z0-9_]+", "_", q_label.lower()).strip("_")
            
            if c_target == c_current:
                # Scan subsequent lines for the Answer pattern
                for offset in range(1, 3):
                    if idx + offset < len(lines):
                        next_line = lines[idx + offset]
                        a_match = re.match(r"(\s*(?:\*|-)\s+\*\*Answer\*\*:\s*)(.*)", next_line)
                        if a_match:
                            prefix = a_match.group(1)
                            # Replace with the new answer line preserving indentation
                            lines[idx + offset] = f"{prefix}{new_answer}"
                            updated = True
                            break
            if updated:
                break

    if not updated:
        raise ValueError(f"Could not find question label '{question_label}' in {filepath}")

    # Write changes back
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    # Auto-compile downstream deliverables to keep CV/Obituary in sync
    try:
        inst_type, inst_name = _parse_instance_details(filepath)
        if inst_type and inst_name:
            compile_instance(instance_type=inst_type, instance_name=inst_name)
    except Exception as e:
        print(f"[Warning] Bridge auto-compilation failed: {e}")
        
    return True


def auto_provision_profile(instance_type, instance_name, primary_base=None, key_relationships=None):
    """
    Dynamically provisions a new Business or Life strategic profile with default questions template.
    If 'business', sets up business questions and folder.
    If 'life', sets up personal life questions and folder.
    """
    # Dynamic workspace lookup for active instances
    active_startup_os_root = resolve_workspace_root()
    
    instance_dir = os.path.join(active_startup_os_root, "instances", instance_type, instance_name)
    os.makedirs(instance_dir, exist_ok=True)
    
    questions_path = os.path.join(instance_dir, "questions.md")
    
    # If the file already exists, don't overwrite it
    if os.path.exists(questions_path):
        return questions_path

    # Clean display trading name
    display_name = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', instance_name).strip()

    if instance_type == "business":
        template_content = f"""# Business Strategic Questions: {display_name}

This file is the Single Source of Truth (SSOT) for {display_name}'s strategic, operational, and compliance variables.

---

## 1. Venture Identity & Foundations
*   **Trading Name**: What is the primary commercial brand or trading name?
    *   **Answer**: {display_name}
*   **Primary Base**: What is your primary geographical base of operations?
    *   **Answer**: {primary_base if primary_base else "Cape Town, South Africa"}
*   **Core Value Proposition**: What is your product or service's unique value statement?
    *   **Answer**: Pending — dynamic startup values and unique technical IP.
*   **Customer Segments**: Who are the primary target users and demographic segments?
    *   **Answer**: Emerging corporate leaders, developers, and local merchant segments.

---

## 2. Operations & Power Resilience
*   **Power Continuity Strategy**: How does your venture manage regional load shedding or grid failure?
    *   **Answer**: Off-grid hybrid solar array with active battery storage bank.

---

## 3. Financial Projections
*   **Projected Year 1**: What is the target Year 1 revenue and profit projection?
    *   **Answer**: R1.5M revenue | R300k Net Profit | MVP launch and scaling.
*   **Projected Year 2**: What is the target Year 2 revenue and profit projection?
    *   **Answer**: R4.0M revenue | R1.2M Net Profit | Regional expansion.
*   **Projected Year 3**: What is the target Year 3 revenue and profit projection?
    *   **Answer**: R10.0M revenue | R3.5M Net Profit | Platform licensing.
"""
    else:
        # Life Profile
        template_content = f"""# Life Strategic Questions: {display_name}

This file is the Single Source of Truth (SSOT) for {display_name}'s life development and tactical growth variables.

---

## 1. Personal Identity & Focus
*   **Full Name**: What is your full name?
    *   **Answer**: {display_name}
*   **Primary Base**: What is your primary geographical base of operations?
    *   **Answer**: {primary_base if primary_base else "Cape Town, South Africa"}
*   **Life Purpose**: What is your high-level core mission or purpose statement?
    *   **Answer**: Pending — write a core purpose or dynamic mission statement here.
*   **Wellness Focus**: What is your primary wellness or biological high-performance goal?
    *   **Answer**: Restore daily sleep depth and improve physical energy compound metrics.

---

## 2. Relationships & Stewardship
*   **Key Relationships**: Who are the primary partners, confidants, or trustees in your life?
    *   **Answer**: {key_relationships if key_relationships else "Immediate family and key professional mentors."}
*   **Legacy Vision**: What is the key long-term stewardship goal?
    *   **Answer**: Establish a generational legacy, write evergreen blueprints, and protect family assets.

---

## 3. Venture & Career Integration
*   **Business Ownership**: Do you own a registered business or run a side hustle?
    *   **Answer**: Pending — specify registered companies or active side hustles here.
"""

    with open(questions_path, 'w', encoding='utf-8') as f:
        f.write(template_content)
        
    return questions_path


def log_ambient_milestone(filepath, category, entry_text):
    """
    Appends a conversational milestone/achievement logged by the Hermes agent.
    If the section doesn't exist, appends it dynamically to the questions.md profile.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Target questions file not found: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Append to the legacy or personal identity section
    clean_entry = entry_text.strip()
    
    # We can either append to a dedicated milestone list or inside the answer sections.
    # For now, let's append a log line at the end of the file or in a dedicated "Logged Wins" log
    log_header = "\n\n## 4. Conversational Milestone Log (Living Ledger)\n"
    
    if "## 4. Conversational Milestone Log" not in content:
        content += log_header
        
    import datetime
    today = datetime.date.today().strftime("%Y-%m-%d")
    content += f"\n*   **[{today}] ({category})**: {clean_entry}"

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    # Auto-compile downstream deliverables to keep CV/Obituary in sync
    try:
        inst_type, inst_name = _parse_instance_details(filepath)
        if inst_type and inst_name:
            compile_instance(instance_type=inst_type, instance_name=inst_name)
    except Exception as e:
        print(f"[Warning] Bridge auto-compilation failed: {e}")
        
    return True
