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

# Licensed under the MIT License.
# compliance-ignore-file: structural-special-dirs
# These scripts live under .rokct/ ONLY at runtime: initiate.py fetches
# this canonical copy from The-Rokct-Protocol into .rokct/skills/ at the
# start of a workflow run, and end_protocol.py deletes it at the end.
# Nothing here is committed under .rokct/ in this repo (that path is
# gitignored) - this IS the checked-in source, at its permanent,
# allowed location.
import os, re
from pathlib import Path


def generate():
    print("[Response Kits] Checking for verified tenders...")
    tenders_dir = Path("03_tenders")
    responses_dir = Path("responses")
    if not tenders_dir.exists():
        return
    for f in tenders_dir.glob("ocds-*.md"):
        with open(f, "r", encoding="utf-8") as content:
            text = content.read()
            if "Verification Status: VERIFIED" in text or "Status: VERIFIED" in text:
                title = (
                    re.search(r"# Tender Opportunity:\s*(.+)", text).group(1).strip()
                )
                tid = (
                    re.search(r"-\s+\*\*Tender Number\*\*:\s*(.+)", text)
                    .group(1)
                    .strip()
                )
                kit_dir = responses_dir / f"{tid}_kit"
                if not kit_dir.exists():
                    kit_dir.mkdir(parents=True, exist_ok=True)
                    with open(kit_dir / "proposal_draft.md", "w") as p:
                        p.write(
                            f"# Proposal for {title}\n\n## Opportunity {tid}\n- [ ] Draft Response"
                        )
                    print(f"  [+] Created Kit for {tid}")


if __name__ == "__main__":
    generate()
