# Copyright (c) 2026 RokctAI
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
# Copyright 2024 RokctAI
# compliance-ignore-file: structural-special-dirs
# These scripts live under .rokct/ ONLY at runtime: initiate.py fetches
# this canonical copy from The-Rokct-Protocol into .rokct/skills/ at the
# start of a workflow run, and end_protocol.py deletes it at the end.
# Nothing here is committed under .rokct/ in this repo (that path is
# gitignored) - this IS the checked-in source, at its permanent,
# allowed location.

import re
import json
from datetime import datetime
from pathlib import Path

GLOBAL_DEFAULT_TASKS = ["Review Tender Documents", "Prepare Initial Response"]


def update_readme(readme_path, stats):
    """Injects the latest stats into the README.md dashboard."""
    if not readme_path.exists():
        return
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    rows = []
    total_all = 0
    verified_all = 0
    icons = {"Equity": "🏦", "Grants": "📜", "Tenders": "🏗️", "EEIP": "🤝"}

    for name, data in stats.items():
        total, verified, _, _, _, _ = data
        health = "🟢" if verified > (total * 0.5) else "🟡"
        rows.append(
            f"| {icons.get(name, '📁')} **{name}** | {total} | {total} | {verified} | {health} |"
        )
        total_all += total
        verified_all += verified

    dashboard_table = "\n".join(rows)
    verified_pct = (verified_all / total_all * 100) if total_all > 0 else 0

    content = re.sub(
        r"\*Last Updated:.*?\*",
        f"*Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        content,
    )
    table_pattern = r"(\| Registry \| Total \| New \(7d\) \| Verified \| Health \|\n\| :--- \| :--- \| :--- \| :--- \| :--- \|\n)([\s\S]*?)(?=\n\s*\n|\n\*\*Overall Progress\*\*)"
    content = re.sub(table_pattern, f"\\1{dashboard_table}", content)
    progress_line = f"**Overall Progress**: `{verified_pct:.1f}%` Verified | `+{total_all}` New Opportunities This Week | [🌐 View Live Dashboard](https://rokctai.github.io/Opportunities-Registry/)"
    content = re.sub(
        r"\*\*Overall Progress\*\*:.*$", progress_line, content, flags=re.MULTILINE
    )

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)


def update_audit_log(audit_path, total, verified, incomplete=0):
    """Updates the Tender-specific audit log."""
    if not audit_path.exists():
        return
    with open(audit_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    incomplete_line = f"- Incomplete (missing required fields): {incomplete}/{total}\n"
    has_incomplete_line = any(l.startswith("- Incomplete") for l in lines)

    new_lines = []
    for line in lines:
        if line.startswith("| 03_tenders/ |"):
            new_lines.append(
                f"| 03_tenders/ | LIVING | IN_PROGRESS | {datetime.now().strftime('%Y-%m-%d')} | {verified} | {total} |\n"
            )
        elif "Automated audit log update:" in line:
            new_lines.append(
                f"- Automated audit log update: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            )
        elif line.startswith("- Incomplete"):
            new_lines.append(incomplete_line)
        elif "Verified:" in line:
            pct = (verified / total * 100) if total > 0 else 0
            new_lines.append(f"- Verified: {verified}/{total} ({pct:.1f}%)\n")
            if not has_incomplete_line:
                new_lines.append(incomplete_line)
        else:
            new_lines.append(line)
    with open(audit_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def update_json_meta(meta_path, stats, advanced_data):
    """Generates a rich meta.json with full classification data."""
    meta_path.parent.mkdir(parents=True, exist_ok=True)

    # Flatten registry stats and classifications
    registry_details = {}
    for name, data in stats.items():
        total, verified, incomplete, aggregations, _, _ = data
        registry_details[name] = {
            "total": total,
            "verified": verified,
            "incomplete": incomplete,
            "classifications": aggregations,
        }

    meta_data = {
        "last_sync": datetime.now().isoformat(),
        "total_verified_all": sum(v["verified"] for v in registry_details.values()),
        "global_defaults": GLOBAL_DEFAULT_TASKS,
        "registries": registry_details,
        "advanced_enrichment": advanced_data,
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_data, f, indent=2)


def parse_tender_card(content):
    """Parses a tender markdown card into the legacy catalog dict shape.

    Mirrors the retired generate_registries.py parser field-for-field so
    the published tenders.json keeps the schema its consumers already read:
    `title` from the H1, snake_case keys from the `- **Key**: Value`
    bullets, N/A defaults for the mandatory metadata fields, `category`
    from the `### Category` section.
    """
    data = {}

    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    data["title"] = title_match.group(1).strip() if title_match else "Unknown"

    for key, val in re.findall(r"-\s+\*\*(.+?)\*\*:\s*(.*)", content):
        clean_key = key.lower().replace(" ", "_").strip("?")
        data[clean_key] = val.strip()

    for field in ["flag", "source_card", "status", "last_verified"]:
        if field not in data:
            data[field] = "N/A"

    category = "General"
    cat_match = re.search(r"### Category\n\s*(.+)", content)
    if cat_match:
        category = cat_match.group(1).strip()
    data["category"] = category

    return data


def update_json_tenders(tenders_path, tenders_dir):
    """Regenerates the published tenders.json catalog from the card corpus.

    Without this the sync only rewrote meta.json, so the published catalog
    stayed frozen at whatever snapshot the retired generator last committed
    while enrichment kept moving. Card selection matches scan_registry's
    rules (recursive, skipping templates/audit logs/extracted `_content`
    files); output is sorted by slug so an unchanged corpus produces a
    byte-identical (and therefore un-committed) file.
    """
    tenders_path.parent.mkdir(parents=True, exist_ok=True)

    items = []
    for file in tenders_dir.rglob("*.md"):
        fname = file.name.lower()
        if (
            fname
            in ["template.md", "readme.md", "registry_audit_log.md", "global_audit_log.md"]
            or fname.startswith("registry_")
            or fname.endswith("_content.md")
        ):
            continue
        try:
            with open(file, "r", encoding="utf-8", errors="ignore") as f:
                item = parse_tender_card(f.read())
            item["slug"] = file.stem
            items.append(item)
        except Exception as e:
            print(f"[Error] Failed to parse tender card {file}: {e}")

    items.sort(key=lambda item: item["slug"])
    with open(tenders_path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
    print(f"[Done] tenders.json saved ({len(items)} items).")


def save_jules_todo(
    base_dir, todo_list, filename="todo.json", title_prefix="Tender Enrichment Queue"
):
    """Saves the work list for Jules' weekly session."""
    todo_path = base_dir / ".rokct" / "agent" / filename
    todo_path.parent.mkdir(parents=True, exist_ok=True)

    # rglob() enumeration order is filesystem-dependent, not stable across
    # runs - sorting here is what keeps the queue file byte-identical (and
    # therefore un-committed) when the underlying pending set hasn't changed.
    todo_list = sorted(todo_list)
    data = {
        "title": f"{title_prefix}: {datetime.now().strftime('%Y-%m-%d')}",
        "pending_count": len(todo_list),
        "files": todo_list,
    }
    with open(todo_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[Done] {filename} saved ({len(todo_list)} items).")
