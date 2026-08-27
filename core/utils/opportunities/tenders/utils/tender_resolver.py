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

# Licensed under the MIT License.
# Copyright 2024 ROKCT INTELLIGENCE (PTY) LTD
# compliance-ignore-file: structural-special-dirs
# These scripts live under .rokct/ ONLY at runtime: initiate.py fetches
# this canonical copy from The-Rokct-Protocol into .rokct/skills/ at the
# start of a workflow run, and end_protocol.py deletes it at the end.
# Nothing here is committed under .rokct/ in this repo (that path is
# gitignored) - this IS the checked-in source, at its permanent,
# allowed location.

from pathlib import Path


def resolve_card_path(tender_dir, tender_id):
    """Finds the tender card by checking first 03_tenders/{tender_id}/{tender_id}.md then 03_tenders/{tender_id}.md."""
    tender_dir = Path(tender_dir)

    # 1. Check folder structure: 03_tenders/{tender_id}/{tender_id}.md
    folder_card = tender_dir / tender_id / f"{tender_id}.md"
    if folder_card.exists():
        return folder_card

    # 2. Check flat structure: 03_tenders/{tender_id}.md
    flat_card = tender_dir / f"{tender_id}.md"
    if flat_card.exists():
        return flat_card

    return None


def resolve_write_path(tender_dir, tender_id):
    """Determines where to write a new or updated tender card."""
    tender_dir = Path(tender_dir)

    # If folder 03_tenders/{tender_id}/ exists return 03_tenders/{tender_id}/{tender_id}.md
    if (tender_dir / tender_id).is_dir():
        return tender_dir / tender_id / f"{tender_id}.md"

    # otherwise return 03_tenders/{tender_id}.md
    return tender_dir / f"{tender_id}.md"
