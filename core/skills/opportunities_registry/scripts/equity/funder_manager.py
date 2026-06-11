import os
import re
import sys
from datetime import date
from pathlib import Path

class FunderManager:
    def __init__(self, registry_path='01_equity/'):
        self.registry_path = Path(registry_path)
        self.existing_orgs = self._load_existing_orgs()
        self.template = """---
# Equity Opportunity: {Organization}

## Quick Stats
- **Organization**: {Organization}
- **Funder Type**: {Funder Type}
- **Funding Type**: {Funding Type}
- **Industry**: {Industry}
- **Territory**: {Territory}
- **Country**: {Country}
- **Website**: {Website}

## Contact
- **Contact Person**: {Contact Person}
- **LinkedIn**: {LinkedIn}
- **Phone**: {Phone}

## Source
- **Source / Verification**: {Source}
- **Notes**: {Notes}

## Audit & Status
- **Status**: ACTIVE
- **Verification Status**: {Verification Status}
- **Last Verified**: {Last Verified}
---
"""

    def _load_existing_orgs(self):
        orgs = set()
        if not self.registry_path.exists():
            return orgs

        # Regex to match the Organization field in markdown
        org_regex = re.compile(r"^\s*-?\s*\*\*Organization\*\*:\s*(.*)", re.IGNORECASE | re.MULTILINE)

        for file in self.registry_path.glob("*.md"):
            if file.name in ['template.md', 'registry_audit_log.md', 'readme.md']:
                continue
            try:
                content = file.read_text()
                match = org_regex.search(content)
                if match:
                    name = match.group(1).strip().strip('[]').lower()
                    orgs.add(name)
            except Exception:
                pass
        return orgs

    def is_duplicate(self, name):
        name_clean = name.strip().lower()
        if name_clean in self.existing_orgs:
            return True

        # Check filename variant
        filename = self.generate_filename(name)
        if (self.registry_path / filename).exists():
            return True

        return False

    def generate_filename(self, name):
        # Convert to snake_case, remove special chars
        fname = name.lower()

        # Replace spaces (including non-breaking spaces) with underscores
        fname = re.sub(r'\s+', '_', fname)

        # Strip out characters that are invalid on Windows: ? : * " < > | \
        fname = re.sub(r'[?:*"<>|\\]', '', fname)

        # Other replacements from original logic
        fname = fname.replace("'", "").replace("&", "and").replace(".", "").replace("-", "_")

        if not fname.endswith(".md"):
            fname += ".md"
        return fname

    def create_funder_file(self, data):
        if "Last Verified" not in data:
            data["Last Verified"] = str(date.today())
        if "Status" not in data:
            data["Status"] = "ACTIVE"
        if "Verification Status" not in data:
            data["Verification Status"] = "UNVERIFIED"
        if "Phone" not in data:
            data["Phone"] = ""
        if "Notes" not in data:
            data["Notes"] = ""

        content = self.template.format(**data)
        filename = self.generate_filename(data["Organization"])
        filepath = self.registry_path / filename

        with open(filepath, 'w') as f:
            f.write(content)
        return filepath

if __name__ == "__main__":
    manager = FunderManager()
    if len(sys.argv) > 2 and sys.argv[1] == "check":
        print(manager.is_duplicate(sys.argv[2]))
