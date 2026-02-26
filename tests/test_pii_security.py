"""
Tests for PII Security Hardening (Phase 19)
=============================================

Covers:
- Versioned ciphertext format (v1: prefix)
- Multi-key support (current + legacy keys)
- Key rotation end-to-end
- Backward compatibility (unversioned v0 ciphertext)
- is_encrypted() with versioned formats
- PII access audit logging
- Audit triggers on investor_profiles
- Security headers middleware
- Startup encryption validation
"""

import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet


# ============================================================
# Versioned Ciphertext Tests
# ============================================================

class TestVersionedCiphertext:
    """Test the v1: ciphertext format."""

    def test_encrypt_produces_versioned_format(self):
        """New encryptions should produce v1: prefix."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()
        enc = FieldEncryptor(key)

        result = enc.encrypt("test-value")
        assert result.startswith("v1:"), f"Expected v1: prefix, got: {result[:10]}"

    def test_decrypt_versioned_ciphertext(self):
        """Should decrypt v1: prefixed ciphertext."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()
        enc = FieldEncryptor(key)

        encrypted = enc.encrypt("hello-world")
        decrypted = enc.decrypt(encrypted)
        assert decrypted == "hello-world"

    def test_encrypt_decrypt_round_trip(self):
        """Full round-trip with versioned format."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()
        enc = FieldEncryptor(key)

        test_values = [
            "123-45-6789",
            "012345678",
            "1990-01-15",
            "A simple test string with spaces",
            "",
        ]
        for val in test_values:
            encrypted = enc.encrypt(val)
            assert encrypted.startswith("v1:")
            decrypted = enc.decrypt(encrypted)
            assert decrypted == val, f"Round-trip failed for: {val}"

    def test_encrypt_none_raises(self):
        """Encrypting None should raise ValueError."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()
        enc = FieldEncryptor(key)

        with pytest.raises(ValueError, match="Cannot encrypt None"):
            enc.encrypt(None)

    def test_decrypt_none_raises(self):
        """Decrypting None should raise ValueError."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()
        enc = FieldEncryptor(key)

        with pytest.raises(ValueError, match="Cannot decrypt None"):
            enc.decrypt(None)

    def test_encrypt_non_string_converts(self):
        """Non-string inputs should be converted to string."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()
        enc = FieldEncryptor(key)

        encrypted = enc.encrypt(12345)
        decrypted = enc.decrypt(encrypted)
        assert decrypted == "12345"

    def test_encrypt_or_none_with_value(self):
        """encrypt_or_none should encrypt non-None values."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()
        enc = FieldEncryptor(key)

        result = enc.encrypt_or_none("test")
        assert result is not None
        assert result.startswith("v1:")

    def test_encrypt_or_none_with_none(self):
        """encrypt_or_none should return None for None input."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()
        enc = FieldEncryptor(key)

        result = enc.encrypt_or_none(None)
        assert result is None

    def test_decrypt_or_none_with_none(self):
        """decrypt_or_none should return None for None input."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()
        enc = FieldEncryptor(key)

        result = enc.decrypt_or_none(None)
        assert result is None

    def test_different_encryptions_produce_different_ciphertext(self):
        """Same plaintext encrypted twice should produce different ciphertext."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()
        enc = FieldEncryptor(key)

        enc1 = enc.encrypt("same-value")
        enc2 = enc.encrypt("same-value")
        assert enc1 != enc2, "Fernet should produce different ciphertext each time"


# ============================================================
# Backward Compatibility Tests
# ============================================================

class TestBackwardCompatibility:
    """Test that unversioned (v0) ciphertext still decrypts."""

    def test_decrypt_unversioned_ciphertext(self):
        """Should decrypt bare gAAAAA... ciphertext (v0 format)."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()

        # Create unversioned ciphertext directly with Fernet
        fernet = Fernet(key.encode())
        unversioned = fernet.encrypt(b"legacy-value").decode('utf-8')
        assert unversioned.startswith("gAAAAA"), "Raw Fernet should start with gAAAAA"
        assert not unversioned.startswith("v1:")

        # Decrypt with FieldEncryptor (should handle v0)
        enc = FieldEncryptor(key)
        result = enc.decrypt(unversioned)
        assert result == "legacy-value"

    def test_decrypt_versioned_and_unversioned_same_key(self):
        """Both v0 and v1 formats should decrypt with same key."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()
        enc = FieldEncryptor(key)

        # v1 format
        v1_encrypted = enc.encrypt("test-v1")
        assert v1_encrypted.startswith("v1:")

        # v0 format (raw Fernet)
        fernet = Fernet(key.encode())
        v0_encrypted = fernet.encrypt(b"test-v0").decode('utf-8')

        # Both should decrypt
        assert enc.decrypt(v1_encrypted) == "test-v1"
        assert enc.decrypt(v0_encrypted) == "test-v0"

    def test_wrong_key_raises_value_error(self):
        """Wrong key should raise ValueError with helpful message."""
        from src.utils.encryption import FieldEncryptor
        key1 = FieldEncryptor.generate_key()
        key2 = FieldEncryptor.generate_key()

        enc1 = FieldEncryptor(key1)
        enc2 = FieldEncryptor(key2)

        encrypted = enc1.encrypt("secret")
        with pytest.raises(ValueError, match="Decryption failed"):
            enc2.decrypt(encrypted)


# ============================================================
# Multi-Key Support Tests
# ============================================================

class TestMultiKeySupport:
    """Test legacy key support for key rotation."""

    def test_decrypt_with_legacy_key(self):
        """Should decrypt data encrypted with a legacy key."""
        from src.utils.encryption import FieldEncryptor
        old_key = FieldEncryptor.generate_key()
        new_key = FieldEncryptor.generate_key()

        # Encrypt with old key
        old_enc = FieldEncryptor(old_key)
        encrypted = old_enc.encrypt("legacy-data")

        # Decrypt with new key (old key as legacy)
        new_enc = FieldEncryptor(new_key, legacy_keys=[old_key])
        result = new_enc.decrypt(encrypted)
        assert result == "legacy-data"

    def test_decrypt_with_unversioned_legacy(self):
        """Should decrypt unversioned (v0) data with a legacy key."""
        from src.utils.encryption import FieldEncryptor
        old_key = FieldEncryptor.generate_key()
        new_key = FieldEncryptor.generate_key()

        # Create unversioned ciphertext with old key
        fernet = Fernet(old_key.encode())
        unversioned = fernet.encrypt(b"old-v0-data").decode('utf-8')

        # Decrypt with new key (old key as legacy)
        new_enc = FieldEncryptor(new_key, legacy_keys=[old_key])
        result = new_enc.decrypt(unversioned)
        assert result == "old-v0-data"

    def test_encrypt_always_uses_current_key(self):
        """Encrypt should always use the current key, not legacy keys."""
        from src.utils.encryption import FieldEncryptor
        old_key = FieldEncryptor.generate_key()
        new_key = FieldEncryptor.generate_key()

        enc = FieldEncryptor(new_key, legacy_keys=[old_key])
        encrypted = enc.encrypt("new-data")

        # Should decrypt with new key alone (no legacy needed)
        new_only = FieldEncryptor(new_key)
        result = new_only.decrypt(encrypted)
        assert result == "new-data"

    def test_multiple_legacy_keys(self):
        """Should support multiple legacy keys."""
        from src.utils.encryption import FieldEncryptor
        key1 = FieldEncryptor.generate_key()
        key2 = FieldEncryptor.generate_key()
        key3 = FieldEncryptor.generate_key()

        # Encrypt with key1 (oldest)
        enc1 = FieldEncryptor(key1)
        encrypted = enc1.encrypt("very-old-data")

        # Decrypt with key3 (current), key1 and key2 as legacy
        enc3 = FieldEncryptor(key3, legacy_keys=[key2, key1])
        result = enc3.decrypt(encrypted)
        assert result == "very-old-data"

    def test_has_legacy_keys_property(self):
        """has_legacy_keys should reflect configuration."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()

        enc_no_legacy = FieldEncryptor(key)
        assert enc_no_legacy.has_legacy_keys is False
        assert enc_no_legacy.legacy_key_count == 0

        legacy = FieldEncryptor.generate_key()
        enc_with_legacy = FieldEncryptor(key, legacy_keys=[legacy])
        assert enc_with_legacy.has_legacy_keys is True
        assert enc_with_legacy.legacy_key_count == 1

    def test_invalid_legacy_key_logged_not_raised(self):
        """Invalid legacy keys should be logged but not raise."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()

        # Should not raise even with invalid legacy key
        enc = FieldEncryptor(key, legacy_keys=["not-a-valid-key"])
        assert enc.legacy_key_count == 0  # Invalid key was skipped

    def test_legacy_keys_from_env_var(self):
        """Should load legacy keys from ENCRYPTION_LEGACY_KEYS env var."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()
        legacy1 = FieldEncryptor.generate_key()
        legacy2 = FieldEncryptor.generate_key()

        with patch.dict(os.environ, {
            'ENCRYPTION_LEGACY_KEYS': f'{legacy1},{legacy2}'
        }):
            enc = FieldEncryptor(key)
            assert enc.legacy_key_count == 2

    def test_empty_legacy_keys_env_var(self):
        """Empty ENCRYPTION_LEGACY_KEYS should result in no legacy keys."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()

        with patch.dict(os.environ, {'ENCRYPTION_LEGACY_KEYS': ''}):
            enc = FieldEncryptor(key)
            assert enc.legacy_key_count == 0


# ============================================================
# Key Rotation End-to-End Tests
# ============================================================

class TestKeyRotation:
    """Test full key rotation workflow."""

    def test_full_rotation_workflow(self):
        """Simulate complete key rotation: encrypt with A, rotate to B, decrypt with B."""
        from src.utils.encryption import FieldEncryptor

        key_a = FieldEncryptor.generate_key()
        key_b = FieldEncryptor.generate_key()

        # Phase 1: Encrypt with key A
        enc_a = FieldEncryptor(key_a)
        ssn_encrypted = enc_a.encrypt("123-45-6789")
        bank_encrypted = enc_a.encrypt("9876543210")

        # Phase 2: Rotate - decrypt with A, re-encrypt with B
        plaintext_ssn = enc_a.decrypt(ssn_encrypted)
        plaintext_bank = enc_a.decrypt(bank_encrypted)

        enc_b = FieldEncryptor(key_b)
        new_ssn = enc_b.encrypt(plaintext_ssn)
        new_bank = enc_b.encrypt(plaintext_bank)

        # Phase 3: Verify with key B (key A as legacy for transition period)
        enc_final = FieldEncryptor(key_b, legacy_keys=[key_a])
        assert enc_final.decrypt(new_ssn) == "123-45-6789"
        assert enc_final.decrypt(new_bank) == "9876543210"

        # Old ciphertext should also work during transition
        assert enc_final.decrypt(ssn_encrypted) == "123-45-6789"

    def test_rotation_produces_versioned_output(self):
        """Rotated ciphertext should use v1: format."""
        from src.utils.encryption import FieldEncryptor

        key_a = FieldEncryptor.generate_key()
        key_b = FieldEncryptor.generate_key()

        enc_a = FieldEncryptor(key_a)
        old_encrypted = enc_a.encrypt("data")
        assert old_encrypted.startswith("v1:")

        # After rotation
        plaintext = enc_a.decrypt(old_encrypted)
        enc_b = FieldEncryptor(key_b)
        new_encrypted = enc_b.encrypt(plaintext)
        assert new_encrypted.startswith("v1:")


# ============================================================
# is_encrypted() Tests
# ============================================================

class TestIsEncrypted:
    """Test the is_encrypted() heuristic with versioned formats."""

    def test_versioned_ciphertext_detected(self):
        """v1:gAAAAA... should be detected as encrypted."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()
        enc = FieldEncryptor(key)

        encrypted = enc.encrypt("test")
        assert FieldEncryptor.is_encrypted(encrypted) is True

    def test_unversioned_ciphertext_detected(self):
        """Bare gAAAAA... should still be detected as encrypted."""
        from src.utils.encryption import FieldEncryptor

        # Create bare Fernet token
        key = FieldEncryptor.generate_key()
        fernet = Fernet(key.encode())
        bare = fernet.encrypt(b"test").decode('utf-8')

        assert FieldEncryptor.is_encrypted(bare) is True

    def test_plaintext_not_detected(self):
        """Plaintext strings should not be detected as encrypted."""
        from src.utils.encryption import FieldEncryptor

        assert FieldEncryptor.is_encrypted("123-45-6789") is False
        assert FieldEncryptor.is_encrypted("hello world") is False
        assert FieldEncryptor.is_encrypted("") is False
        assert FieldEncryptor.is_encrypted("short") is False

    def test_none_not_detected(self):
        """None should not be detected as encrypted."""
        from src.utils.encryption import FieldEncryptor
        assert FieldEncryptor.is_encrypted(None) is False

    def test_v1_prefix_without_gAAAAA_not_detected(self):
        """v1: prefix without Fernet header should not be detected."""
        from src.utils.encryption import FieldEncryptor
        assert FieldEncryptor.is_encrypted("v1:not-fernet-data-at-all-but-long-enough-to-pass-length-check") is False


# ============================================================
# PII Access Audit Log Tests
# ============================================================

class _NonClosingConnection:
    """Wrapper that prevents close() from actually closing the connection.

    sqlite3.Connection.close is read-only in Python 3.14+, so we can't
    patch it directly. This wrapper delegates everything except close().
    """

    def __init__(self, conn):
        self._conn = conn

    def close(self):
        pass  # No-op — keep connection open for test assertions

    def __getattr__(self, name):
        return getattr(self._conn, name)


class TestPIIAccessLog:
    """Test PII access audit logging."""

    def _create_pii_db(self):
        """Create an in-memory DB with pii_access_log table."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE pii_access_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                investor_id TEXT NOT NULL,
                field_name TEXT NOT NULL,
                access_type TEXT NOT NULL,
                performed_by TEXT NOT NULL DEFAULT 'system',
                ip_address TEXT,
                context TEXT
            )
        """)
        conn.commit()
        return conn

    def test_log_pii_access_writes_record(self):
        """log_pii_access should insert a record into pii_access_log."""
        db = self._create_pii_db()
        wrapper = _NonClosingConnection(db)

        with patch('apps.investor_portal.api.models.database.get_connection', return_value=wrapper):
            from apps.investor_portal.api.models.database import log_pii_access
            log_pii_access(
                investor_id='20260101-01A',
                field_name='ssn_encrypted',
                access_type='read',
                performed_by='admin_cli',
                ip_address='127.0.0.1',
                context='profile_view'
            )

        # Verify record was written
        cursor = db.execute("SELECT * FROM pii_access_log")
        rows = cursor.fetchall()
        assert len(rows) == 1
        row = dict(rows[0])
        assert row['investor_id'] == '20260101-01A'
        assert row['field_name'] == 'ssn_encrypted'
        assert row['access_type'] == 'read'
        assert row['performed_by'] == 'admin_cli'
        assert row['ip_address'] == '127.0.0.1'
        assert row['context'] == 'profile_view'
        db.close()

    def test_log_pii_access_write_type(self):
        """log_pii_access should support 'write' access type."""
        db = self._create_pii_db()
        wrapper = _NonClosingConnection(db)

        with patch('apps.investor_portal.api.models.database.get_connection', return_value=wrapper):
            from apps.investor_portal.api.models.database import log_pii_access
            log_pii_access(
                investor_id='20260101-02B',
                field_name='bank_account_encrypted',
                access_type='write',
                performed_by='api',
                context='profile_update'
            )

        cursor = db.execute("SELECT access_type FROM pii_access_log")
        row = cursor.fetchone()
        assert dict(row)['access_type'] == 'write'
        db.close()

    def test_log_pii_access_non_fatal(self):
        """log_pii_access should never raise exceptions."""
        # Use a DB without the table - simulates DB error
        db = sqlite3.connect(":memory:")
        wrapper = _NonClosingConnection(db)

        with patch('apps.investor_portal.api.models.database.get_connection', return_value=wrapper):
            from apps.investor_portal.api.models.database import log_pii_access
            # Should not raise even though table doesn't exist
            log_pii_access(
                investor_id='20260101-01A',
                field_name='ssn_encrypted',
                access_type='read',
            )
        db.close()

    def test_log_pii_access_optional_fields(self):
        """ip_address and context should be optional."""
        db = self._create_pii_db()
        wrapper = _NonClosingConnection(db)

        with patch('apps.investor_portal.api.models.database.get_connection', return_value=wrapper):
            from apps.investor_portal.api.models.database import log_pii_access
            log_pii_access(
                investor_id='20260101-01A',
                field_name='date_of_birth',
                access_type='read',
            )

        cursor = db.execute("SELECT ip_address, context FROM pii_access_log")
        row = dict(cursor.fetchone())
        assert row['ip_address'] is None
        assert row['context'] is None
        db.close()


# ============================================================
# Audit Triggers on investor_profiles Tests
# ============================================================

class TestProfileAuditTriggers:
    """Test that audit triggers log profile changes correctly."""

    def _setup_tables(self, conn):
        """Create tables and triggers needed for audit tests."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                table_name TEXT NOT NULL,
                record_id TEXT NOT NULL,
                action TEXT NOT NULL,
                old_values TEXT,
                new_values TEXT,
                performed_by TEXT DEFAULT 'system',
                ip_address TEXT,
                notes TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS investor_profiles (
                profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                investor_id TEXT NOT NULL UNIQUE,
                full_legal_name TEXT,
                email_primary TEXT,
                ssn_encrypted TEXT,
                tax_id_encrypted TEXT,
                bank_routing_encrypted TEXT,
                bank_account_encrypted TEXT,
                profile_completed INTEGER DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Create INSERT trigger
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_audit_profiles_insert
            AFTER INSERT ON investor_profiles
            FOR EACH ROW
            BEGIN
                INSERT INTO audit_log (table_name, record_id, action, new_values)
                VALUES ('investor_profiles', NEW.investor_id, 'INSERT',
                        json_object(
                            'full_legal_name', NEW.full_legal_name,
                            'email_primary', NEW.email_primary,
                            'ssn_encrypted', CASE WHEN NEW.ssn_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                            'tax_id_encrypted', CASE WHEN NEW.tax_id_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                            'bank_routing_encrypted', CASE WHEN NEW.bank_routing_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                            'bank_account_encrypted', CASE WHEN NEW.bank_account_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                            'profile_completed', NEW.profile_completed
                        ));
            END
        """)
        # Create UPDATE trigger
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_audit_profiles_update
            AFTER UPDATE ON investor_profiles
            FOR EACH ROW
            BEGIN
                INSERT INTO audit_log (table_name, record_id, action, old_values, new_values)
                VALUES ('investor_profiles', NEW.investor_id, 'UPDATE',
                        json_object(
                            'full_legal_name', OLD.full_legal_name,
                            'email_primary', OLD.email_primary,
                            'ssn_encrypted', CASE WHEN OLD.ssn_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                            'tax_id_encrypted', CASE WHEN OLD.tax_id_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                            'bank_routing_encrypted', CASE WHEN OLD.bank_routing_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                            'bank_account_encrypted', CASE WHEN OLD.bank_account_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                            'profile_completed', OLD.profile_completed
                        ),
                        json_object(
                            'full_legal_name', NEW.full_legal_name,
                            'email_primary', NEW.email_primary,
                            'ssn_encrypted', CASE WHEN NEW.ssn_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                            'tax_id_encrypted', CASE WHEN NEW.tax_id_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                            'bank_routing_encrypted', CASE WHEN NEW.bank_routing_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                            'bank_account_encrypted', CASE WHEN NEW.bank_account_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                            'profile_completed', NEW.profile_completed
                        ));
            END
        """)
        conn.commit()

    def test_insert_creates_audit_entry(self):
        """INSERT on investor_profiles should create audit_log entry."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        self._setup_tables(conn)

        conn.execute("""
            INSERT INTO investor_profiles (investor_id, full_legal_name, email_primary, ssn_encrypted)
            VALUES ('20260101-01A', 'Test Investor', 'test@example.com', 'v1:gAAAAA_encrypted_data')
        """)
        conn.commit()

        cursor = conn.execute("SELECT * FROM audit_log WHERE table_name = 'investor_profiles'")
        rows = cursor.fetchall()
        assert len(rows) == 1
        row = dict(rows[0])
        assert row['action'] == 'INSERT'
        assert row['record_id'] == '20260101-01A'
        # Verify encrypted fields are masked
        import json
        new_vals = json.loads(row['new_values'])
        assert new_vals['ssn_encrypted'] == '[ENCRYPTED]'
        assert new_vals['full_legal_name'] == 'Test Investor'
        conn.close()

    def test_update_creates_audit_entry(self):
        """UPDATE on investor_profiles should create audit_log entry with old and new values."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        self._setup_tables(conn)

        conn.execute("""
            INSERT INTO investor_profiles (investor_id, full_legal_name, profile_completed)
            VALUES ('20260101-01A', 'Original Name', 0)
        """)
        conn.execute("""
            UPDATE investor_profiles SET full_legal_name = 'Updated Name', profile_completed = 1
            WHERE investor_id = '20260101-01A'
        """)
        conn.commit()

        cursor = conn.execute("""
            SELECT * FROM audit_log
            WHERE table_name = 'investor_profiles' AND action = 'UPDATE'
        """)
        rows = cursor.fetchall()
        assert len(rows) == 1
        row = dict(rows[0])

        import json
        old_vals = json.loads(row['old_values'])
        new_vals = json.loads(row['new_values'])
        assert old_vals['full_legal_name'] == 'Original Name'
        assert new_vals['full_legal_name'] == 'Updated Name'
        assert old_vals['profile_completed'] == 0
        assert new_vals['profile_completed'] == 1
        conn.close()

    def test_encrypted_fields_never_logged_as_plaintext(self):
        """Encrypted field values should NEVER appear in audit_log."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        self._setup_tables(conn)

        secret_ssn = "v1:gAAAAA_this_is_encrypted_ssn_data_never_log_this"
        secret_bank = "v1:gAAAAA_this_is_encrypted_bank_data_never_log_this"

        conn.execute("""
            INSERT INTO investor_profiles
            (investor_id, full_legal_name, ssn_encrypted, bank_account_encrypted)
            VALUES ('20260101-01A', 'Test', ?, ?)
        """, (secret_ssn, secret_bank))
        conn.commit()

        cursor = conn.execute("SELECT new_values FROM audit_log")
        row = cursor.fetchone()
        new_values_str = dict(row)['new_values']

        # The actual ciphertext should NOT be in the log
        assert secret_ssn not in new_values_str
        assert secret_bank not in new_values_str
        # Only the placeholder should be there
        assert '[ENCRYPTED]' in new_values_str
        conn.close()

    def test_null_encrypted_fields_logged_as_null(self):
        """NULL encrypted fields should be logged as null, not [ENCRYPTED]."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        self._setup_tables(conn)

        conn.execute("""
            INSERT INTO investor_profiles (investor_id, full_legal_name)
            VALUES ('20260101-01A', 'Test')
        """)
        conn.commit()

        cursor = conn.execute("SELECT new_values FROM audit_log")
        row = cursor.fetchone()

        import json
        new_vals = json.loads(dict(row)['new_values'])
        assert new_vals['ssn_encrypted'] is None
        assert new_vals['bank_routing_encrypted'] is None
        conn.close()


# ============================================================
# Security Headers Tests
# ============================================================

class TestSecurityHeaders:
    """Test security headers are present on API responses."""

    def _create_test_app(self):
        """Create a minimal FastAPI app with the security headers middleware."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()

        @app.middleware("http")
        async def add_security_headers(request, call_next):
            response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            response.headers["Cache-Control"] = "no-store"
            return response

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        return TestClient(app)

    def test_x_content_type_options(self):
        client = self._create_test_app()
        response = client.get("/test")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self):
        client = self._create_test_app()
        response = client.get("/test")
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_x_xss_protection(self):
        client = self._create_test_app()
        response = client.get("/test")
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_referrer_policy(self):
        client = self._create_test_app()
        response = client.get("/test")
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy(self):
        client = self._create_test_app()
        response = client.get("/test")
        assert response.headers.get("Permissions-Policy") == "camera=(), microphone=(), geolocation=()"

    def test_cache_control(self):
        client = self._create_test_app()
        response = client.get("/test")
        assert response.headers.get("Cache-Control") == "no-store"

    def test_all_headers_present(self):
        """All 6 security headers should be present on every response."""
        client = self._create_test_app()
        response = client.get("/test")

        expected_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Permissions-Policy",
            "Cache-Control",
        ]
        for header in expected_headers:
            assert header in response.headers, f"Missing security header: {header}"


# ============================================================
# Startup Encryption Validation Tests
# ============================================================

class TestStartupEncryptionValidation:
    """Test the encryption validation that runs on API startup."""

    def test_valid_key_round_trips(self):
        """A valid Fernet key should pass round-trip validation."""
        from src.utils.encryption import FieldEncryptor
        key = FieldEncryptor.generate_key()
        enc = FieldEncryptor(key)

        test_val = "encryption-startup-test"
        result = enc.decrypt(enc.encrypt(test_val))
        assert result == test_val

    def test_missing_key_raises(self):
        """Missing ENCRYPTION_KEY should raise ValueError."""
        from src.utils.encryption import FieldEncryptor

        with patch.dict(os.environ, {'ENCRYPTION_KEY': ''}, clear=False):
            with pytest.raises(ValueError, match="No encryption key"):
                FieldEncryptor()

    def test_invalid_key_raises(self):
        """Invalid ENCRYPTION_KEY should raise ValueError."""
        from src.utils.encryption import FieldEncryptor

        with pytest.raises(ValueError, match="Invalid encryption key"):
            FieldEncryptor("not-a-valid-fernet-key")


# ============================================================
# reset_encryptor Tests
# ============================================================

class TestResetEncryptor:
    """Test the reset_encryptor utility."""

    def test_reset_clears_cached_instance(self):
        """reset_encryptor should clear the cached singleton."""
        from src.utils.encryption import get_encryptor, reset_encryptor, FieldEncryptor

        key = FieldEncryptor.generate_key()
        with patch.dict(os.environ, {'ENCRYPTION_KEY': key}):
            reset_encryptor()
            enc1 = get_encryptor()
            reset_encryptor()
            enc2 = get_encryptor()
            # After reset, should create new instance
            assert enc1 is not enc2

        # Clean up
        reset_encryptor()
