# Licensed under the MIT License.
# Copyright 2024 RokctAI

import os
import re
import hashlib
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
from crypto_utils import encrypt_pii

# Ported from opportunities: Adapt for 'factory' book jobs context
# Configuration
JOB_DIR = Path('.rokct/agent/jobs/pending')
EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

def load_key():
    """Find and load encryption key from monorepo environment."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(script_dir))))
    env_path = os.path.join(project_root, ".env", "production.env")

    if os.path.exists(env_path):
        load_dotenv(env_path)
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if "EMAIL_ENCRYPTION_KEY=" in line:
                    return line.replace("export ", "").strip().split("=", 1)[1].strip("'\" ")

    return os.getenv('EMAIL_ENCRYPTION_KEY')

def process_privacy(check_only=False):
    """Enforces encryption-based privacy for job cards."""
    if not JOB_DIR.exists():
        return True

    encryption_key = load_key()
    if not encryption_key and not check_only:
        print("❌ Error: EMAIL_ENCRYPTION_KEY not found. Cannot encrypt.")
        return False

    violations = []
    processed_count = 0

    print(f"🔐 {'Checking' if check_only else 'Applying'} PII Encryption Privacy...")

    for card_file in JOB_DIR.glob('*.md'):
        filename = card_file.name
        with open(card_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. Detection Logic
        found_emails = re.findall(EMAIL_REGEX, content)
        has_plaintext_email = any(e for e in found_emails if e.lower() != "email@example.com")

        if has_plaintext_email:
            if check_only:
                violations.append(f"❌ Unencrypted PII in: {filename}")
                continue

            # 2. Encryption Logic
            # Note: This logic assumes a specific PII field in the job card if applicable.
            # In factory context, we protect any email found in the card.
            for email in found_emails:
                if email.lower() == "email@example.com": continue
                encrypted_blob = encrypt_pii(email, encryption_key)
                content = content.replace(email, f"[REDACTED] (Encrypted: {encrypted_blob})")

            with open(card_file, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"🔒 Encrypted PII in: {filename}")
            processed_count += 1

    if check_only:
        if violations:
            print("\n".join(violations))
            print("\n🚨 PRIVACY CHECK FAILED: Plaintext PII detected.")
            return False
        print("✅ Privacy check passed. All PII is encrypted.")
        return True

    print(f"✅ Encryption sync complete. {processed_count} files secured.")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enforce encryption-based privacy.")
    parser.add_argument("--check", action="store_true", help="Check for plaintext without modifying.")
    args = parser.parse_args()

    success = process_privacy(check_only=args.check)
    if not success:
        sys.exit(1)
