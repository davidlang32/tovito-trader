"""
Tests for the field-level encryption module.

Covers:
- Encrypt/decrypt round-trip
- Different keys produce different ciphertext
- Invalid key raises error
- None handling
- Encrypted value detection heuristic
"""

import pytest
from cryptography.fernet import Fernet

from src.utils.encryption import FieldEncryptor


@pytest.fixture
def test_key():
    """Generate a fresh Fernet key for testing."""
    return Fernet.generate_key().decode('utf-8')


@pytest.fixture
def encryptor(test_key):
    """Create a FieldEncryptor with a test key."""
    return FieldEncryptor(key=test_key)


class TestEncryptDecrypt:
    """Tests for basic encrypt/decrypt operations."""

    def test_round_trip_ssn(self, encryptor):
        """Encrypting then decrypting should return the original SSN."""
        original = "123-45-6789"
        encrypted = encryptor.encrypt(original)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == original

    def test_round_trip_bank_account(self, encryptor):
        """Encrypting then decrypting should return the original bank account."""
        original = "1234567890"
        encrypted = encryptor.encrypt(original)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == original

    def test_round_trip_unicode(self, encryptor):
        """Should handle unicode characters correctly."""
        original = "Test Name with Special: and numbers 12345"
        encrypted = encryptor.encrypt(original)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == original

    def test_encrypted_value_differs_from_original(self, encryptor):
        """Encrypted value should not be the same as the original."""
        original = "123-45-6789"
        encrypted = encryptor.encrypt(original)
        assert encrypted != original

    def test_encrypting_same_value_twice_produces_different_output(self, encryptor):
        """Fernet includes a timestamp — same input produces different ciphertext."""
        original = "123-45-6789"
        enc1 = encryptor.encrypt(original)
        enc2 = encryptor.encrypt(original)
        # Both should decrypt to the same value
        assert encryptor.decrypt(enc1) == original
        assert encryptor.decrypt(enc2) == original
        # But ciphertext should differ (due to Fernet's random IV)
        assert enc1 != enc2


class TestKeyManagement:
    """Tests for encryption key handling."""

    def test_different_key_produces_different_ciphertext(self):
        """Different keys should produce different encrypted output."""
        key1 = Fernet.generate_key().decode('utf-8')
        key2 = Fernet.generate_key().decode('utf-8')
        enc1 = FieldEncryptor(key=key1)
        enc2 = FieldEncryptor(key=key2)

        original = "123-45-6789"
        ct1 = enc1.encrypt(original)
        ct2 = enc2.encrypt(original)

        # Should not be able to decrypt with wrong key
        with pytest.raises(ValueError, match="Decryption failed"):
            enc2.decrypt(ct1)

        with pytest.raises(ValueError, match="Decryption failed"):
            enc1.decrypt(ct2)

    def test_invalid_key_raises_error(self):
        """An invalid key should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid encryption key"):
            FieldEncryptor(key="not-a-valid-fernet-key")

    def test_no_key_raises_error(self, monkeypatch):
        """Missing key should raise ValueError."""
        monkeypatch.delenv('ENCRYPTION_KEY', raising=False)
        with pytest.raises(ValueError, match="No encryption key available"):
            FieldEncryptor(key=None)

    def test_generate_key_produces_valid_key(self):
        """Generated keys should work for encryption/decryption."""
        key = FieldEncryptor.generate_key()
        enc = FieldEncryptor(key=key)

        original = "test-value"
        encrypted = enc.encrypt(original)
        decrypted = enc.decrypt(encrypted)
        assert decrypted == original


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_encrypt_none_raises_error(self, encryptor):
        """Encrypting None should raise ValueError."""
        with pytest.raises(ValueError, match="Cannot encrypt None"):
            encryptor.encrypt(None)

    def test_decrypt_none_raises_error(self, encryptor):
        """Decrypting None should raise ValueError."""
        with pytest.raises(ValueError, match="Cannot decrypt None"):
            encryptor.decrypt(None)

    def test_encrypt_or_none_with_value(self, encryptor):
        """encrypt_or_none should encrypt non-None values."""
        result = encryptor.encrypt_or_none("test")
        assert result is not None
        assert encryptor.decrypt(result) == "test"

    def test_encrypt_or_none_with_none(self, encryptor):
        """encrypt_or_none should return None for None input."""
        result = encryptor.encrypt_or_none(None)
        assert result is None

    def test_decrypt_or_none_with_none(self, encryptor):
        """decrypt_or_none should return None for None input."""
        result = encryptor.decrypt_or_none(None)
        assert result is None

    def test_decrypt_corrupted_data(self, encryptor):
        """Decrypting corrupted ciphertext should raise ValueError."""
        with pytest.raises(ValueError, match="Decryption failed"):
            encryptor.decrypt("this-is-not-valid-ciphertext")

    def test_is_encrypted_heuristic(self, encryptor):
        """is_encrypted should detect Fernet-like tokens."""
        encrypted = encryptor.encrypt("test")
        assert FieldEncryptor.is_encrypted(encrypted) is True
        assert FieldEncryptor.is_encrypted("plain text") is False
        assert FieldEncryptor.is_encrypted("") is False
        assert FieldEncryptor.is_encrypted("short") is False
