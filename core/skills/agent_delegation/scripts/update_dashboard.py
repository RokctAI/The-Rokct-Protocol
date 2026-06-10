# Licensed under the MIT License.
# Copyright 2024 RokctAI

import os
import re
import json
from pathlib import Path
from datetime import datetime, timedelta

# Ported from opportunities: Adapt for 'factory' book jobs context
def update_readme_stats():
    """Calculates book stats and updates the main README.md and generates data for dashboard."""
    print("📊 Updating Job Dashboard & Data...")

    project_root = Path(__file__).parent.parent.parent.parent.parent
    readme_path = project_root / 'README.md'
    docs_dir = project_root / 'docs'
    docs_dir.mkdir(exist_ok=True)

    # 1. Calculate Stats and Gather Data
    stats = {
        'Poetry': {'total': 0, 'published': 0, 'new': 0},
        'Fiction': {'total': 0, 'published': 0, 'new': 0},
        'Short Story': {'total': 0, 'published': 0, 'new': 0},
        'Children': {'total': 0, 'published': 0, 'new': 0}
    }

    all_jobs = []

    dirs = {
        'Poetry': Path('.rokct/types/poetry'),
        'Fiction': Path('.rokct/types/fiction'),
        'Short Story': Path('.rokct/types/short_story'),
        'Children': Path('.rokct/types/children')
    }

    week_ago = datetime.now() - timedelta(days=7)

    job_pending_dir = Path('.rokct/agent/jobs/pending')
    if job_pending_dir.exists():
        for f in job_pending_dir.glob('*.md'):
            if f.name == 'template.md': continue

            with open(f, 'r', encoding='utf-8') as content:
                text = content.read()

                # Simple parsing for frontmatter
                type_match = re.search(r'type:\s*(.*)', text)
                job_type = type_match.group(1).strip().capitalize() if type_match else "Unknown"
                if job_type == "Short_story": job_type = "Short Story"

                if job_type in stats:
                    stats[job_type]['total'] += 1

                    is_published = "status: published" in text.lower()
                    if is_published:
                        stats[job_type]['published'] += 1

                    is_new = datetime.fromtimestamp(f.stat().st_mtime) > week_ago
                    if is_new:
                        stats[job_type]['new'] += 1

                    all_jobs.append({
                        'id': f.stem,
                        'category': job_type,
                        'published': is_published,
                        'new': is_new
                    })

    # 2. Export JSON for dashboard
    data_output = {
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'stats': stats,
        'jobs': all_jobs
    }

    with open(docs_dir / 'data.json', 'w', encoding='utf-8') as f:
        json.dump(data_output, f, indent=2)
    print(f"📄 Exported {len(all_jobs)} jobs to docs/data.json")

    # 3. Format Dashboard for README
    if readme_path.exists():
        total_jobs = sum(s['total'] for s in stats.values())
        total_published = sum(s['published'] for s in stats.values())
        total_new = sum(s['new'] for s in stats.values())
        progress_pct = (total_published / total_jobs * 100) if total_jobs > 0 else 0

        dashboard = f"""
## 🚀 Factory Status Dashboard
*Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*

| Genre | Total Jobs | New (7d) | Published | Health |
| :--- | :--- | :--- | :--- | :--- |
| 🎭 **Poetry** | {stats['Poetry']['total']} | {stats['Poetry']['new']} | {stats['Poetry']['published']} | { '🟢' if stats['Poetry']['total'] == stats['Poetry']['published'] and stats['Poetry']['total'] > 0 else '🟡' } |
| 📚 **Fiction** | {stats['Fiction']['total']} | {stats['Fiction']['new']} | {stats['Fiction']['published']} | { '🟢' if stats['Fiction']['total'] == stats['Fiction']['published'] and stats['Fiction']['total'] > 0 else '🟡' } |
| 📖 **Short Story** | {stats['Short Story']['total']} | {stats['Short Story']['new']} | {stats['Short Story']['published']} | { '🟢' if stats['Short Story']['total'] == stats['Short Story']['published'] and stats['Short Story']['total'] > 0 else '🟡' } |
| 👶 **Children** | {stats['Children']['total']} | {stats['Children']['new']} | {stats['Children']['published']} | { '🟢' if stats['Children']['total'] == stats['Children']['published'] and stats['Children']['total'] > 0 else '🟡' } |

**Overall Progress**: `{progress_pct:.1f}%` Published | `+{total_new}` New Jobs This Week
"""

        with open(readme_path, 'r', encoding='utf-8') as f:
            readme_content = f.read()

        marker_start = "## 🚀 Factory Status Dashboard"
        if marker_start in readme_content:
            pattern = re.compile(rf"{marker_start}.*?(?=\n## )", re.DOTALL)
            if not pattern.search(readme_content):
                 pattern = re.compile(rf"{marker_start}.*", re.DOTALL)
            new_content = pattern.sub(dashboard.strip(), readme_content)
        else:
            # Append after the first paragraph
            parts = readme_content.split('\n\n', 1)
            if len(parts) > 1:
                new_content = parts[0] + "\n\n" + dashboard.strip() + "\n\n" + parts[1]
            else:
                new_content = readme_content + "\n\n" + dashboard.strip()

        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("✅ README Dashboard Updated.")

if __name__ == "__main__":
    update_readme_stats()
