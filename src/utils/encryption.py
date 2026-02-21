"""
Application-level Field Encryption
====================================
Uses Fernet (symmetric, AES-128-CBC) for encrypting sensitive PII fields
at the application level before storing in the database.

Fields encrypted: SSN, tax ID, bank routing number, bank account number,
date of birth.

Usage:
    from src.utils.encryption import FieldEncryptor

    enc = FieldEncryptor()  # Reads ENCRYPTION_KEY from .env
    ciphertext = enc.encrypt("123-45-6789")
    plaintext = enc.decrypt(ciphertext)

Key Management:
    - Generate key once: FieldEncryptor.generate_key()
    - Store in .env as ENCRYPTION_KEY=...
    - NEVER commit the key to version control
    - Back up the key separately — data is unrecoverable without it
"""

import os
import logging
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class FieldEncryptor:
    """
    Symmetric field-level encryption using Fernet.

    Reads the encryption key from the ENCRYPTION_KEY environment variable.
    If no key is provided, one can be generated with generate_key().
    """

    def __init__(self, key: Optional[str] = None):
        """
        Initialize the encryptor.

        Args:
            key: Base64-encoded Fernet key. If None, reads from
                 ENCRYPTION_KEY env var.

        Raises:
            ValueError: If no key is available
        """
        self._key = key or os.getenv('ENCRYPTION_KEY')

        if not self._key:
            raise ValueError(
                "No encryption key available. Set ENCRYPTION_KEY in .env "
                "or pass a key to FieldEncryptor(). Generate one with "
                "FieldEncryptor.generate_key()"
            )

        try:
            self._fernet = Fernet(self._key.encode() if isinstance(self._key, str) else self._key)
        except Exception as e:
            raise ValueError(f"Invalid encryption key: {e}")

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.

        Args:
            plaintext: The string to encrypt

        Returns:
            Base64-encoded ciphertext string (safe for DB storage)

        Raises:
            ValueError: If plaintext is None or empty
        """
        if plaintext is None:
            raise ValueError("Cannot encrypt None value")
        if not isinstance(plaintext, str):
            plaintext = str(plaintext)

        token = self._fernet.encrypt(plaintext.encode('utf-8'))
        return token.decode('utf-8')

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt a ciphertext string.

        Args:
            ciphertext: Base64-encoded ciphertext from encrypt()

        Returns:
            Original plaintext string

        Raises:
            ValueError: If decryption fails (wrong key or corrupted data)
        """
        if ciphertext is None:
            raise ValueError("Cannot decrypt None value")

        try:
            plaintext = self._fernet.decrypt(ciphertext.encode('utf-8'))
            return plaintext.decode('utf-8')
        except InvalidToken:
            raise ValueError(
                "Decryption failed — wrong key or corrupted ciphertext"
            )

    def encrypt_or_none(self, plaintext: Optional[str]) -> Optional[str]:
        """
        Encrypt a value, returning None if input is None.

        Convenience method for optional fields.
        """
        if plaintext is None:
            return None
        return self.encrypt(plaintext)

    def decrypt_or_none(self, ciphertext: Optional[str]) -> Optional[str]:
        """
        Decrypt a value, returning None if input is None.

        Convenience method for optional fields.
        """
        if ciphertext is None:
            return None
        return self.decrypt(ciphertext)

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key.

        Run once and store the result in your .env file:
            ENCRYPTION_KEY=<generated_key>

        Returns:
            Base64-encoded key string
        """
        key = Fernet.generate_key()
        return key.decode('utf-8')

    @staticmethod
    def is_encrypted(value: str) -> bool:
        """
        Heuristic check if a value looks like Fernet ciphertext.

        Fernet tokens are base64-encoded and start with 'gAAAAA'.
        This is a best-effort check, not cryptographic verification.

        Returns:
            True if the value appears to be encrypted
        """
        if not value or len(value) < 50:
            return False
        return value.startswith('gAAAAA')


# Convenience: module-level encryptor instance (lazy-loaded)
_default_encryptor = None


def get_encryptor() -> FieldEncryptor:
    """
    Get the default FieldEncryptor instance.

    Lazy-loads from ENCRYPTION_KEY env var on first call.
    Raises ValueError if ENCRYPTION_KEY is not set.
    """
    global _default_encryptor
    if _default_encryptor is None:
        _default_encryptor = FieldEncryptor()
    return _default_encryptor


if __name__ == "__main__":
    """Generate a new encryption key when run directly."""
    key = FieldEncryptor.generate_key()
    print("=" * 60)
    print("NEW ENCRYPTION KEY GENERATED")
    print("=" * 60)
    print()
    print(f"  ENCRYPTION_KEY={key}")
    print()
    print("Add this to your .env file.")
    print("IMPORTANT: Back up this key separately — data is")
    print("unrecoverable without it!")
    print()

    # Test round-trip
    enc = FieldEncryptor(key)
    test_value = "123-45-6789"
    encrypted = enc.encrypt(test_value)
    decrypted = enc.decrypt(encrypted)

    print("Verification:")
    print(f"  Original:  {test_value}")
    print(f"  Encrypted: {encrypted[:40]}...")
    print(f"  Decrypted: {decrypted}")
    print(f"  Match: {'YES' if decrypted == test_value else 'NO'}")
