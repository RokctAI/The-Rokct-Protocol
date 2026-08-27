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

# compliance-ignore-file: structural-special-dirs
# These scripts live under .rokct/ ONLY at runtime: initiate.py fetches
# this canonical copy from The-Rokct-Protocol into .rokct/skills/ at the
# start of a workflow run, and end_protocol.py deletes it at the end.
# Nothing here is committed under .rokct/ in this repo (that path is
# gitignored) - this IS the checked-in source, at its permanent,
# allowed location.
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

# --- Non-funder heading filter -------------------------------------------
#
# The equity sync scrapes listicle/directory pages whose <h2>/<h3> headings
# are mostly firm names — but also navigation and FAQ section labels
# ("Contents", "See also", "60% off", "What is a venture capital firm?").
# Those must never become funder cards. The heuristics below are deliberately
# conservative: when in doubt a card IS created (a human can delete it), but
# obvious section/FAQ/promo headings are rejected at parse and creation time.

# Question-word starts: "What is...", "How do I...", "Can I raise...".
# Matched against the first whole word only, so "Canaan Partners" passes.
_INTERROGATIVE_STARTS = {
    "what",
    "why",
    "how",
    "who",
    "where",
    "when",
    "can",
    "is",
    "do",
}

# Well-known page-section labels. Matched exactly, or as a leading phrase
# followed by a separator or a space ("Methodology — how we keep this list
# current", "Quick facts about US startup investment").
_SECTION_HEADINGS = (
    "contents",
    "table of contents",
    "references",
    "see also",
    "related posts",
    "methodology",
    "quick facts",
    "useful resources",
    "faq",
    "frequently asked questions",
)


def is_junk_heading(name):
    """True when a scraped heading is clearly NOT a funder name.

    Conservative on purpose: only patterns that no real firm name uses
    (questions, section labels, percent-off promos, dollar amounts) are
    rejected; anything plausible is allowed through.
    """
    raw = str(name).strip()
    if not raw:
        return True

    # Questions are FAQ entries, never firm names.
    if raw.rstrip().endswith("?"):
        return True

    norm = re.sub(r"\s+", " ", raw.lower()).strip(" .!—–-:")

    words = norm.split(" ", 1)
    if words and words[0] in _INTERROGATIVE_STARTS:
        return True

    for section in _SECTION_HEADINGS:
        if norm == section or norm.startswith(section + " "):
            return True

    # Promo/stat headings: "60% off", "$1B raised", "raised $1+ billion".
    if re.match(r"^\d+\s*%", raw):
        return True
    if "$" in raw:
        return True

    return False


def load_denylist(base_dir):
    """Slugs (card filenames without .md) that must never be (re)created.

    Reads the optional consumer-repo file .rokct/agent/equity_denylist.json:
    a JSON list of slugs, or an object with a "slugs" list. Missing or
    malformed files yield an empty denylist — the sync must never crash on
    an optional config file.
    """
    path = Path(base_dir) / ".rokct" / "agent" / "equity_denylist.json"
    try:
        if not path.is_file():
            return set()
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    if isinstance(data, dict):
        data = data.get("slugs", [])
    if not isinstance(data, list):
        return set()
    slugs = set()
    for entry in data:
        slug = str(entry).strip().lower()
        if slug.endswith(".md"):
            slug = slug[:-3]
        if slug:
            slugs.add(slug)
    return slugs


class FunderManager:
    def __init__(self, registry_path="01_equity/"):
        self.registry_path = Path(registry_path)
        self.existing_orgs = self._load_existing_orgs()
        # Consumer-repo denylist lives next to the registry, at
        # <repo-root>/.rokct/agent/equity_denylist.json.
        self.denylist = load_denylist(self.registry_path.resolve().parent)
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
- **Data Completeness**: {Data Completeness}
- **Last Verified**: {Last Verified}
---
"""

    def _load_existing_orgs(self):
        orgs = set()
        if not self.registry_path.exists():
            return orgs

        # Regex to match the Organization field in markdown
        org_regex = re.compile(
            r"^\s*-?\s*\*\*Organization\*\*:\s*(.*)", re.IGNORECASE | re.MULTILINE
        )

        for file in self.registry_path.glob("*.md"):
            if file.name in ["template.md", "registry_audit_log.md", "readme.md"]:
                continue
            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
                match = org_regex.search(content)
                if match:
                    name = match.group(1).strip().strip("[]").lower()
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

    def slug_for(self, name):
        """The card slug for a name: its generated filename without .md."""
        return self.generate_filename(name)[: -len(".md")]

    def is_denylisted(self, name):
        """True when the name's slug is in the consumer repo's denylist."""
        return self.slug_for(name) in self.denylist

    def generate_filename(self, name):
        # Convert to snake_case, remove special chars
        fname = name.lower()

        # Replace spaces (including non-breaking spaces) with underscores
        fname = re.sub(r"\s+", "_", fname)

        # Strip out characters that are invalid on Windows: ? : * " < > | \
        fname = re.sub(r'[?:*"<>|\\]', "", fname)

        # Other replacements from original logic
        fname = (
            fname.replace("'", "")
            .replace("&", "and")
            .replace(".", "")
            .replace("-", "_")
        )

        if not fname.endswith(".md"):
            fname += ".md"
        return fname

    def create_funder_file(self, data):
        # Hard denylist guard: slugs listed in the consumer repo's
        # .rokct/agent/equity_denylist.json are never (re)created, no matter
        # which code path asked for the card.
        org_name = str(data.get("Organization", ""))
        if self.is_denylisted(org_name):
            raise ValueError(
                f"Refusing to create denylisted funder card: {org_name!r} "
                f"(slug {self.slug_for(org_name)!r})"
            )

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

        # Data completeness: bulk-synced cards default whole fields to
        # "Unspecified"; mark them visibly so they don't read like researched
        # cards. Required: organization, funding type, website (source link).
        missing = []
        for field in ("Organization", "Funding Type", "Website"):
            value = str(data.get(field, "")).strip()
            if not value or value.lower() == "unspecified":
                missing.append(field.lower())
        data["Data Completeness"] = (
            f"INCOMPLETE — missing: {', '.join(missing)}" if missing else "COMPLETE"
        )

        content = self.template.format(**data)
        filename = self.generate_filename(data["Organization"])
        filepath = self.registry_path / filename

        # Verified-status guard: never overwrite an existing card a human has
        # marked VERIFIED with a freshly synced (UNVERIFIED) template. A
        # verified card only loses that status through an explicit manual
        # edit, not an automated refresh.
        if filepath.exists():
            try:
                existing = filepath.read_text(encoding="utf-8")
            except Exception:
                existing = ""
            if re.search(r"Verification Status\*\*:\s*VERIFIED", existing):
                return filepath

        # Atomic replace: write a sibling temp file and rename it into
        # place so a crash mid-write can never leave a truncated card.
        tmp_path = filepath.with_name(filepath.name + f".tmp{os.getpid()}")
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.replace(tmp_path, filepath)
        return filepath


if __name__ == "__main__":
    manager = FunderManager()
    if len(sys.argv) > 2 and sys.argv[1] == "check":
        print(manager.is_duplicate(sys.argv[2]))
