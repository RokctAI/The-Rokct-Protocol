import os
import re

def parse_questions_md(filepath):
    """
    Parses a local markdown questions.md file for StartupOS.
    Maps arbitrary question headers like '*   **Label**: ...' to answered strings
    nested under '*   **Answer**: ...'.
    """
    answers = {}
    if not os.path.exists(filepath):
        return answers
        
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        lines = [line.strip() for line in content.split('\n')]
        for i, line in enumerate(lines):
            # Matches '*   **Question Label**: ...' or '-   **Question Label**:'
            q_match = re.match(r"\*\s+\*\*([^*]+)\*\*:\s*(.*)", line)
            if q_match:
                q_label = q_match.group(1).strip()
                # Canonicalize key: lowercase, alpha-numeric, underscores
                canonical_key = re.sub(r"[^a-z0-9_]+", "_", q_label.lower()).strip("_")
                
                # Scan next 2 lines for '*   **Answer**:' or '-   **Answer**:'
                ans_found = None
                for offset in range(1, 3):
                    if i + offset < len(lines):
                        next_line = lines[i + offset]
                        a_match = re.match(r"(?:\*|-)\s+\*\*Answer\*\*:\s*(.*)", next_line)
                        if a_match:
                            ans_found = a_match.group(1).strip()
                            break
                            
                if ans_found and not ans_found.lower().startswith("pending"):
                    answers[canonical_key] = ans_found
    except Exception as e:
        print(f"Error parsing questions.md: {e}")
        
    return answers
