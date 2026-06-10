# Licensed under the MIT License.
# Copyright 2024 RokctAI

import os
import re
from pathlib import Path
import difflib

def is_duplicate_theme(new_theme, existing_themes_path, threshold=0.8):
    if not os.path.exists(existing_themes_path):
        return False, ""

    with open(existing_themes_path, 'r', encoding='utf-8') as f:
        existing_themes = [line.strip() for line in f.readlines() if line.strip()]

    for existing in existing_themes:
        similarity = difflib.SequenceMatcher(None, new_theme.lower(), existing.lower()).ratio()
        if similarity >= threshold:
            return True, existing

    return False, ""

# Ported from opportunities: Adapt for 'factory' book jobs context
def update_classifications():
    """Generates classification reference files for factory books."""
    print("🏷️ Updating Factory Classifications...")

    config_dir = Path('.rokct/config/classifications')
    config_dir.mkdir(parents=True, exist_ok=True)

    job_dir = Path('.rokct/agent/jobs/pending')
    themes = set()
    genres = set()

    if job_dir.exists():
        for f in job_dir.glob('*.md'):
            if f.name == 'template.md': continue
            with open(f, 'r') as content:
                text = content.read()
                theme_match = re.search(r'theme:\s*(.*)', text)
                if theme_match: themes.add(theme_match.group(1).strip())

                genre_match = re.search(r'type:\s*(.*)', text)
                if genre_match: genres.add(genre_match.group(1).strip())

    save_list(config_dir / 'factory_themes.txt', themes)
    save_list(config_dir / 'factory_genres.txt', genres)

def save_list(path, items):
    clean_items = sorted(list(set([i.strip() for i in items if i.strip()])))
    with open(path, 'w') as f:
        f.write('\n'.join(clean_items))
    print(f"✅ Saved {path.name} ({len(clean_items)} entries)")

if __name__ == "__main__":
    update_classifications()
