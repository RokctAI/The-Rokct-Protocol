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

# Copyright 2024 ROKCT INTELLIGENCE (PTY) LTD
# compliance-ignore-file: structural-special-dirs
# These scripts live under .rokct/ ONLY at runtime: initiate.py fetches
# this canonical copy from The-Rokct-Protocol into .rokct/skills/ at the
# start of a workflow run, and end_protocol.py deletes it at the end.
# Nothing here is committed under .rokct/ in this repo (that path is
# gitignored) - this IS the checked-in source, at its permanent,
# allowed location.

import re
from pathlib import Path
from healers import heal_equity_flags

# --- THE GOLDEN DEFAULTS ---
DEFAULT_AI_BLOCK = """- [ ] Review Tender Documents | 1
- [ ] Prepare Initial Response | 3"""

# Boilerplate the extractor writes when it can't pull anything specific out
# of a tender's PDF (tenders/enrichment/extract_requirements.py,
# generate_actionable_tasks fallback). It differs from DEFAULT_AI_BLOCK, so
# the scan used to count these cards as ADVANCED forever instead of queueing
# them for another enrichment pass.
EXTRACTOR_FALLBACK_BLOCK = """- [ ] Analyze Tender Documents for specific requirements | 1
- [ ] Identify Mandatory Compliance items | 2
- [ ] Prepare Initial Response Proposal | 3"""

# Every checklist body that means "no real enrichment happened yet".
FALLBACK_AI_BLOCKS = (DEFAULT_AI_BLOCK, EXTRACTOR_FALLBACK_BLOCK)


def _normalize_checklist(block):
    """Reduce a checklist block to its task lines for fallback comparison.

    Strips checkbox markers (ticked or not), bullet dashes and surrounding
    whitespace so a hand-ticked box or re-rendered card still matches its
    fallback signature.
    """
    lines = []
    for line in block.splitlines():
        line = re.sub(r"^\s*-\s*\[[ xX]?\]\s*", "", line.strip())
        line = line.strip("- ").strip()
        if line:
            lines.append(line)
    return tuple(lines)


_FALLBACK_SIGNATURES = {_normalize_checklist(b) for b in FALLBACK_AI_BLOCKS}


def is_fallback_checklist(tasks):
    """True when a card's AI Checklist is known generic boilerplate.

    Such a card was never really enriched — the writer (tenders/index.py) or
    the extractor's no-data fallback stamped placeholder tasks — so the scan
    must requeue it instead of counting it as done.
    """
    return _normalize_checklist(tasks) in _FALLBACK_SIGNATURES


# --- THE WHITELIST (Only aggregate these for the JSON) ---
# We use 'Flag' instead of 'Country' for more deterministic counting
INTERESTING_KEYS = [
    "Category",
    "Tender Type",
    "Province",
    "Institution",  # Tenders
    "Industry",
    "Territory",
    "Funder Type",
    "Funding Type",
    "Flag",  # Equity
    "Focus Area",  # Grants
    "Multinational Company",
    "Investment / Funding Type",
    "Application Status",  # EEIP
]


def scan_registry(name, path, base_dir):
    """Scans a directory with Multi-Tag splitting and ISO Flag aggregation."""
    total = 0
    verified = 0
    incomplete = 0
    stats_aggregation = {}
    advanced_tenders = {}
    todo_list = []

    if not path.exists():
        return 0, 0, 0, {}, {}, []

    for file in path.rglob("*.md"):
        fname = file.name.lower()
        if (
            fname in ["template.md", "readme.md", "registry_audit_log.md"]
            or fname.startswith("registry_")
            or fname.endswith("_content.md")
        ):
            continue

        total += 1
        try:
            with open(file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

                # 1. Healing Step
                if name == "Equity":
                    content = heal_equity_flags(file, content)

                # 2. Verification Logic
                is_active = re.search(r"-\s+\*\*Status\*\*:\s*ACTIVE", content, re.I)
                is_verified = re.search(
                    r"Verification Status\*\*:\s*VERIFIED", content, re.I
                )
                has_date = re.search(
                    r"-\s+\*\*Last Verified\*\*:\s*\d{4}-\d{2}-\d{2}", content, re.I
                )

                # Strict verification for Equity/Grants (must have VERIFIED status)
                # Tenders are verified if active and have a date (legacy logic)
                is_v = False
                if name == "Tenders":
                    is_v = is_active or is_verified or has_date
                else:
                    is_v = is_verified

                if is_v:
                    verified += 1

                # Cards the writers marked as missing required fields
                # (title / closing date / amount / source link).
                if re.search(r"Data Completeness\*\*:\s*INCOMPLETE", content, re.I):
                    incomplete += 1

                # 3. Multi-Tag Metadata Extraction (Only for Verified Entries)
                if is_v:
                    stat_matches = re.finditer(
                        r"-\s+\*\*(?P<key>.*?)\*\*:\s*(?P<val>.*)", content
                    )
                    for m in stat_matches:
                        key = m.group("key").strip()
                        val = m.group("val").strip()

                        if key in INTERESTING_KEYS:
                            if key not in stats_aggregation:
                                stats_aggregation[key] = {}

                            # Split by slash for multi-tag support
                            tags = (
                                [t.strip() for t in val.split("/")]
                                if "/" in val
                                else [val]
                            )

                            for tag in tags:
                                if tag:  # Don't count empty tags
                                    stats_aggregation[key][tag] = (
                                        stats_aggregation[key].get(tag, 0) + 1
                                    )

                # 4. Tender AI Logic
                if name == "Tenders":
                    match = re.search(
                        r"## AI Checklist \(Jules\)[\s\S]*?-->\s*([\s\S]*)$", content
                    )
                    if match:
                        current_tasks = match.group(1).strip()
                        if (
                            not is_fallback_checklist(current_tasks)
                            and len(current_tasks) > 10
                        ):
                            advanced_tenders[file.stem] = {
                                "enrichment": "ADVANCED",
                                "tasks": [
                                    t.strip("- [ ]").strip()
                                    for t in current_tasks.splitlines()
                                    if t.strip()
                                ],
                            }
                        else:
                            todo_list.append(str(file.relative_to(base_dir)))

                # 5. Equity / Grants / EEIP Unverified Logic
                if name in ["Equity", "Grants", "EEIP"]:
                    if (
                        "Verification Status**: UNVERIFIED" in content
                        or "Verification Status**: IN_PROGRESS" in content
                    ):
                        todo_list.append(str(file.relative_to(base_dir)))

        except Exception:
            continue

    return total, verified, incomplete, stats_aggregation, advanced_tenders, todo_list
