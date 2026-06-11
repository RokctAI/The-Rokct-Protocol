# Licensed under the MIT License.
# Copyright 2024 RokctAI

import os
import re
import sys
import base64
import argparse
import hashlib
from pathlib import Path
from dotenv import load_dotenv
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

# --- Encryption core (formerly crypto_utils.py) ---

def encrypt_pii(plain_text, key_b64):
    """Encrypts PII using AES-256-GCM."""
    if not key_b64:
        raise ValueError("Encryption key is missing.")

    key = base64.b64decode(key_b64)
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(plain_text.encode('utf-8'))

    # We store as: nonce:tag:ciphertext
    combined = base64.b64encode(cipher.nonce + tag + ciphertext).decode('utf-8')
    return combined

def decrypt_pii(encrypted_blob, key_b64):
    """Decrypts PII using AES-256-GCM."""
    if not key_b64:
        raise ValueError("Encryption key is missing.")

    key = base64.b64decode(key_b64)
    data = base64.b64decode(encrypted_blob)

    # Extract components
    nonce = data[:16]
    tag = data[16:32]
    ciphertext = data[32:]

    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    plain_text = cipher.decrypt_and_verify(ciphertext, tag)
    return plain_text.decode('utf-8')

# --- Privacy process core (for job cards) ---

JOB_DIR = Path('.rokct/agent/jobs/pending')
EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

def load_key():
    """Find and load encryption key from monorepo environment."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Check multiple directory depths to find env file in workspaces
    for parent_depth in range(2, 6):
        parts = [script_dir] + ['..'] * parent_depth + ['.env', 'production.env']
        env_path = os.path.abspath(os.path.join(*parts))
        if os.path.exists(env_path):
            load_dotenv(env_path)
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if "EMAIL_ENCRYPTION_KEY=" in line:
                        return line.replace("export ", "").strip().split("=", 1)[1].strip("'\" ")
            break

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

    print(f"🔐 {'Checking' if check_only else 'Applying'} PII Encryption Privacy for job cards...")

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

# --- Privacy process for opportunities recipients ---

REC_DIR = Path('.rokct/recipients')

def process_recipients(check_only=False):
    """Enforces encryption-based privacy & anonymization for recipient cards."""
    if not REC_DIR.exists():
        return True

    encryption_key = load_key()
    if not encryption_key and not check_only:
        print("❌ Error: EMAIL_ENCRYPTION_KEY not found. Cannot encrypt.")
        return False

    violations = []
    processed_count = 0

    print(f"🔐 {'Checking' if check_only else 'Applying'} Recipient Encryption Privacy & Anonymization...")

    for card_file in REC_DIR.glob('*.md'):
        filename = card_file.name
        with open(card_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. Detection Logic
        has_raw_email_filename = bool(re.search(EMAIL_REGEX, filename))
        found_emails = re.findall(EMAIL_REGEX, content)
        has_plaintext_email = any(e for e in found_emails if e.lower() != "email@example.com")
        is_anonymous_filename = bool(re.match(r'^user_[a-f0-9]{12}\.md$', filename))

        if has_raw_email_filename or has_plaintext_email or not is_anonymous_filename:
            if check_only:
                violations.append(f"❌ Unencrypted PII in: {filename}")
                continue

            # 2. Encryption Logic
            email_match = re.search(r'-\s+\*\*Email\*\*:\s*(.+)$', content, re.MULTILINE)
            name_match = re.search(r'-\s+\*\*Full Name\*\*:\s*(.+)$', content, re.MULTILINE)

            if not email_match or not name_match:
                print(f"⚠️ Skipping {filename}: Missing mandatory Email or Full Name fields.")
                continue

            email = email_match.group(1).strip()
            full_name = name_match.group(1).strip()

            if email == "email@example.com": continue

            # Encrypt
            encrypted_blob = encrypt_pii(email, encryption_key)

            # Role Encryption Logic
            role_match = re.search(r'-\s+\*\*Role\*\*:\s*(.+)$', content, re.MULTILINE)
            role_encrypted_blob = ""
            display_role = "user"

            if role_match:
                raw_role = role_match.group(1).strip()
                if "." in raw_role and "@" in raw_role:
                    role_encrypted_blob = encrypt_pii(raw_role, encryption_key)
                    display_role = raw_role.split(".")[-1] # e.g., admin
                else:
                    display_role = raw_role

            # Generate anonymous identifier for filename
            display_hash = hashlib.sha256(email.lower().strip().encode()).hexdigest()[:12]
            sub_id = hashlib.sha256(f"{full_name}{email}".encode()).hexdigest()[:16]

            # Update Content
            new_content = content.replace(f"Full Name**: {full_name}", f"Full Name**: [REDACTED]")
            new_content = new_content.replace(f"Email**: {email}", f"Email**: [REDACTED]\n- **email_encrypted**: {encrypted_blob}")

            if role_match:
                role_line = f"Role**: {display_role}"
                if role_encrypted_blob:
                    role_line += f"\n- **role_encrypted**: {role_encrypted_blob}"
                new_content = new_content.replace(f"Role**: {role_match.group(1).strip()}", role_line)

            new_content = new_content.replace(f"Subscription ID**: [Leave blank, will be hashed]", f"Subscription ID**: {sub_id}")

            # Anonymize File
            new_filename = f"user_{display_hash}.md"
            new_path = REC_DIR / new_filename

            with open(new_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            if filename != new_filename:
                os.remove(card_file)

            print(f"🔒 Encrypted & Anonymized: {filename} -> {new_filename}")
            processed_count += 1

    if check_only:
        if violations:
            print("\n".join(violations))
            print("\n🚨 PRIVACY CHECK FAILED: Plaintext PII detected.")
            return False
        print("✅ Privacy check passed. All emails are encrypted.")
        return True

    print(f"✅ Encryption sync complete. {processed_count} files secured.")
    return True

# --- CLI entrypoint ---

def main():
    parser = argparse.ArgumentParser(description="Privacy & Cryptography Manager.")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Sync/apply PII encryption to cards")
    sync_parser.add_argument("--check", action="store_true", help="Only check for plaintext without modifying")
    sync_parser.add_argument("--target", default="jobs", choices=["jobs", "recipients"], help="Target data type to sync")

    # Encrypt command
    enc_parser = subparsers.add_parser("encrypt", help="Encrypt text")
    enc_parser.add_argument("--text", required=True, help="Text to encrypt")
    enc_parser.add_argument("--key", help="Base64 encoded AES key")

    # Decrypt command
    dec_parser = subparsers.add_parser("decrypt", help="Decrypt text")
    dec_parser.add_argument("--blob", required=True, help="Base64 encoded encrypted blob")
    dec_parser.add_argument("--key", help="Base64 encoded AES key")

    args = parser.parse_args()

    if args.command == "sync":
        if args.target == "recipients":
            success = process_recipients(check_only=args.check)
        else:
            success = process_privacy(check_only=args.check)
        if not success:
            sys.exit(1)
    elif args.command == "encrypt":
        key = args.key or load_key()
        if not key:
            print("Error: EMAIL_ENCRYPTION_KEY not resolved.", file=sys.stderr)
            sys.exit(1)
        print(encrypt_pii(args.text, key))
    elif args.command == "decrypt":
        key = args.key or load_key()
        if not key:
            print("Error: EMAIL_ENCRYPTION_KEY not resolved.", file=sys.stderr)
            sys.exit(1)
        print(decrypt_pii(args.blob, key))
    else:
        # Backward compatibility with standalone crypto_utils quick test when called without args
        test_key = base64.b64encode(get_random_bytes(32)).decode()
        test_data = "PII Data"
        encrypted = encrypt_pii(test_data, test_key)
        decrypted = decrypt_pii(encrypted, test_key)
        print(f"Original: {test_data}")
        print(f"Encrypted: {encrypted}")
        print(f"Decrypted: {decrypted}")
        assert test_data == decrypted
        print("✅ Privacy & Crypto Utils Test Passed")

if __name__ == "__main__":
    main()
