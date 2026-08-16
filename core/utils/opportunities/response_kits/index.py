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
