# Licensed under the MIT License.
# Copyright 2024 RokctAI

import base64
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

# Ported from opportunities: Handles PII encryption for book card data
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

if __name__ == "__main__":
    # Quick Test
    test_key = base64.b64encode(get_random_bytes(32)).decode()
    test_data = "PII Data"
    encrypted = encrypt_pii(test_data, test_key)
    decrypted = decrypt_pii(encrypted, test_key)
    print(f"Original: {test_data}")
    print(f"Encrypted: {encrypted}")
    print(f"Decrypted: {decrypted}")
    assert test_data == decrypted
    print("✅ Crypto Utils Test Passed")
