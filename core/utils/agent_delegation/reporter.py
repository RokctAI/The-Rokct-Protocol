# Licensed under the MIT License.
# Copyright 2024 RokctAI

import os
import re
import sys
import json
import argparse
import requests
from pathlib import Path
from datetime import datetime, timedelta

# --- Audit Logs (formerly update_audit_logs.py) ---

def update_audit_logs():
    """Ensures book job directories have up-to-date audit logs."""
    print("📝 Updating Job Audit Logs...")

    dirs = {
        'books/drafts': 'LIVING',
        'books/published': 'STATIC'
    }

    for dir_path, mode in dirs.items():
        directory = Path(dir_path)
        if not directory.exists(): continue

        log_path = directory / 'job_audit_log.md'

        total_jobs = 0
        published_jobs = 0

        # Scan subdirectories for books
        for book_dir in directory.iterdir():
            if book_dir.is_dir() and not book_dir.name.startswith('_'):
                total_jobs += 1
                metadata_file = book_dir / 'metadata.md'
                if metadata_file.exists():
                    with open(metadata_file, 'r', encoding='utf-8') as content:
                        text = content.read()
                        if "status: published" in text.lower():
                            published_jobs += 1

        log_content = f"""# Job Audit Log: {dir_path.split('/')[-1].capitalize()}

| Directory | Mode | Status | Last Audit Date | Published Jobs | Total Jobs |
| :--- | :--- | :--- | :--- | :--- | :--- |
| {dir_path}/ | {mode} | { 'COMPLETE' if published_jobs == total_jobs and total_jobs > 0 else 'IN_PROGRESS' } | {datetime.now().strftime('%Y-%m-%d')} | {published_jobs} | {total_jobs} |

## Recent Changes
- Automated audit log update: {datetime.now().strftime('%Y-%m-%d %H:%M')}
- Published: {published_jobs}/{total_jobs} ({ (published_jobs/total_jobs*100) if total_jobs > 0 else 0 :.1f}%)
"""
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(log_content)
        print(f"✅ Updated audit log for {dir_path}")

# --- Health checks (formerly check_health.py) ---

def check_link_health():
    """Scans book jobs for broken links."""
    print("🔍 Starting Global Job Link Health Check...")

    # Target book draft directories
    directories = [Path('books/drafts')]
    broken_count = 0
    checked_count = 0

    for directory in directories:
        if not directory.exists(): continue
        print(f"📂 Auditing {directory.name}...")

        # Scan all markdown files in book subdirectories
        for md_file in directory.rglob('*.md'):
            if md_file.name in ['template.md', 'metadata.md']:
                continue

            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Pattern to find URLs in markdown links [text](url) or standing alone
            links = re.findall(r'\(https?://[^\s\)]+\)|https?://[^\s\n\)]+', content)

            file_broken = False
            for link in links:
                url = link.strip('() ')

                checked_count += 1
                try:
                    # Use a short timeout and allow redirects
                    response = requests.head(url, timeout=15, allow_redirects=True)
                    # 403 Forbidden is often a bot block, so we only flag >= 404
                    if response.status_code >= 404:
                        print(f"❌ Broken Link in {md_file.name}: {url} (Status: {response.status_code})")
                        file_broken = True
                        broken_count += 1
                except:
                    # Connection errors are flagged for steward review
                    print(f"⚠️ Connection Error in {md_file.name}: {url}")
                    file_broken = True
                    broken_count += 1

            if file_broken:
                if "Status: BROKEN" not in content and "Verification Status: BROKEN" not in content:
                    updated = content.replace("Status: ACTIVE", "Status: BROKEN")
                    updated = updated.replace("Verification Status: VERIFIED", "Verification Status: BROKEN")
                    updated = updated.replace("Verification Status: IN_PROGRESS", "Verification Status: BROKEN")
                    with open(md_file, 'w', encoding='utf-8') as f:
                        f.write(updated)

    print(f"🏁 Health check complete. Checked {checked_count} links. Found {broken_count} issues.")

# --- Dashboard generation (formerly update_dashboard.py) ---

def update_readme_stats():
    """Calculates book stats and updates the main README.md and generates data for dashboard."""
    print("📊 Updating Job Dashboard & Data...")

    project_root = Path(__file__).parent.parent.parent.parent.parent
    readme_path = project_root / 'README.md'
    docs_dir = project_root / 'docs'
    docs_dir.mkdir(exist_ok=True)

    stats = {
        'Poetry': {'total': 0, 'published': 0, 'new': 0},
        'Fiction': {'total': 0, 'published': 0, 'new': 0},
        'Short Story': {'total': 0, 'published': 0, 'new': 0},
        'Children': {'total': 0, 'published': 0, 'new': 0}
    }

    all_jobs = []
    week_ago = datetime.now() - timedelta(days=7)

    job_pending_dir = Path('.rokct/agent/jobs/pending')
    if job_pending_dir.exists():
        for f in job_pending_dir.glob('*.md'):
            if f.name == 'template.md': continue

            with open(f, 'r', encoding='utf-8') as content:
                text = content.read()

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

    data_output = {
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'stats': stats,
        'jobs': all_jobs
    }

    with open(docs_dir / 'data.json', 'w', encoding='utf-8') as f:
        json.dump(data_output, f, indent=2)
    print(f"📄 Exported {len(all_jobs)} jobs to docs/data.json")

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
            parts = readme_content.split('\n\n', 1)
            if len(parts) > 1:
                new_content = parts[0] + "\n\n" + dashboard.strip() + "\n\n" + parts[1]
            else:
                new_content = readme_content + "\n\n" + dashboard.strip()

        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("✅ README Dashboard Updated.")

# --- CLI entrypoint ---

def main():
    parser = argparse.ArgumentParser(description="Audit & Reporter Tools.")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Health command
    subparsers.add_parser("health", help="Check link health on job drafts")

    # Audit command
    subparsers.add_parser("audit", help="Update book job audit logs")

    # Dashboard command
    subparsers.add_parser("dashboard", help="Update readme statistics and dashboard data")

    args = parser.parse_args()

    if args.command == "health":
        check_link_health()
    elif args.command == "audit":
        update_audit_logs()
    elif args.command == "dashboard":
        update_readme_stats()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
