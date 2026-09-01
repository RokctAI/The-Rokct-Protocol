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
