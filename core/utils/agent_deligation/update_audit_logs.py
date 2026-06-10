# Licensed under the MIT License.
# Copyright 2024 RokctAI

import os
import re
from pathlib import Path
from datetime import datetime

# Ported from opportunities: Adapt for 'factory' book jobs context
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

if __name__ == "__main__":
    update_audit_logs()
