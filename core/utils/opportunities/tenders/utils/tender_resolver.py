# Licensed under the MIT License.
# Copyright 2024 RokctAI

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
