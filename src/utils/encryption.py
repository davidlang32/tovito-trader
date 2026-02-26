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

Key Rotation:
    - New encryptions use versioned format: v1:<ciphertext>
    - Old unversioned ciphertext (v0) is supported for backward compatibility
    - Set ENCRYPTION_LEGACY_KEYS (comma-separated) in .env for old keys
    - Decrypt tries current key first, then each legacy key in order
    - Use scripts/setup/rotate_encryption_key.py to re-encrypt all fields
"""

import os
import logging
from typing import Optional, List
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Current ciphertext version prefix
CIPHERTEXT_VERSION = "v1"


class FieldEncryptor:
    """
    Symmetric field-level encryption using Fernet.

    Supports key rotation via versioned ciphertext and legacy keys.
    Reads the encryption key from the ENCRYPTION_KEY environment variable.
    Legacy keys for decryption come from ENCRYPTION_LEGACY_KEYS (comma-separated).
    """

    def __init__(self, key: Optional[str] = None,
                 legacy_keys: Optional[List[str]] = None):
        """
        Initialize the encryptor.

        Args:
            key: Base64-encoded Fernet key. If None, reads from
                 ENCRYPTION_KEY env var.
            legacy_keys: List of old Fernet keys for decrypting data
                         encrypted with previous keys. If None, reads
                         from ENCRYPTION_LEGACY_KEYS env var (comma-separated).

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

        # Build list of legacy Fernet instances for key rotation
        self._legacy_fernets = []
        if legacy_keys is None:
            legacy_env = os.getenv('ENCRYPTION_LEGACY_KEYS', '')
            legacy_keys = [k.strip() for k in legacy_env.split(',') if k.strip()]

        for i, lk in enumerate(legacy_keys):
            try:
                lk_bytes = lk.encode() if isinstance(lk, str) else lk
                self._legacy_fernets.append(Fernet(lk_bytes))
            except Exception as e:
                logger.warning("Invalid legacy key at index %d: %s", i, e)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.

        Returns versioned ciphertext in format: v1:<base64_token>

        Args:
            plaintext: The string to encrypt

        Returns:
            Versioned ciphertext string (safe for DB storage)

        Raises:
            ValueError: If plaintext is None or empty
        """
        if plaintext is None:
            raise ValueError("Cannot encrypt None value")
        if not isinstance(plaintext, str):
            plaintext = str(plaintext)

        token = self._fernet.encrypt(plaintext.encode('utf-8'))
        return f"{CIPHERTEXT_VERSION}:{token.decode('utf-8')}"

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt a ciphertext string.

        Supports both versioned (v1:...) and unversioned (legacy) formats.
        Tries current key first, then each legacy key in order.

        Args:
            ciphertext: Ciphertext from encrypt() (versioned or unversioned)

        Returns:
            Original plaintext string

        Raises:
            ValueError: If decryption fails with all available keys
        """
        if ciphertext is None:
            raise ValueError("Cannot decrypt None value")

        # Strip version prefix if present
        raw_token = ciphertext
        if ':' in ciphertext:
            prefix, remainder = ciphertext.split(':', 1)
            if prefix in ('v1',):
                raw_token = remainder

        # Try current key first
        try:
            plaintext = self._fernet.decrypt(raw_token.encode('utf-8'))
            return plaintext.decode('utf-8')
        except InvalidToken:
            pass

        # Try each legacy key
        for legacy_fernet in self._legacy_fernets:
            try:
                plaintext = legacy_fernet.decrypt(raw_token.encode('utf-8'))
                return plaintext.decode('utf-8')
            except InvalidToken:
                continue

        raise ValueError(
            "Decryption failed -- wrong key or corrupted ciphertext. "
            "Tried current key and %d legacy key(s)." % len(self._legacy_fernets)
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

    @property
    def has_legacy_keys(self) -> bool:
        """Return True if legacy keys are configured for rotation support."""
        return len(self._legacy_fernets) > 0

    @property
    def legacy_key_count(self) -> int:
        """Return the number of configured legacy keys."""
        return len(self._legacy_fernets)

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

        Recognizes both versioned (v1:gAAAAA...) and unversioned
        (gAAAAA...) formats. This is a best-effort check, not
        cryptographic verification.

        Returns:
            True if the value appears to be encrypted
        """
        if not value or len(value) < 50:
            return False
        # Versioned format: v1:gAAAAA...
        if value.startswith('v1:'):
            return value[3:].startswith('gAAAAA')
        # Legacy unversioned format: gAAAAA...
        return value.startswith('gAAAAA')


# Convenience: module-level encryptor instance (lazy-loaded)
_default_encryptor = None


def get_encryptor() -> FieldEncryptor:
    """
    Get the default FieldEncryptor instance.

    Lazy-loads from ENCRYPTION_KEY and ENCRYPTION_LEGACY_KEYS env vars
    on first call. Raises ValueError if ENCRYPTION_KEY is not set.
    """
    global _default_encryptor
    if _default_encryptor is None:
        _default_encryptor = FieldEncryptor()
    return _default_encryptor


def reset_encryptor():
    """Reset the cached encryptor instance.

    Call after changing ENCRYPTION_KEY env var (e.g., in tests).
    """
    global _default_encryptor
    _default_encryptor = None


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
    print("IMPORTANT: Back up this key separately -- data is")
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
    print(f"  Format:  versioned ({CIPHERTEXT_VERSION}: prefix)")
