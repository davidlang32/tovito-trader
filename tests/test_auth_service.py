"""
Tests for Authentication Service
==================================

Tests the investor portal auth service functions:
- Email verification (initiate + complete)
- Password validation and hashing
- Login with lockout tracking
- Password reset flow

Uses a dedicated test database with auth-compatible schema.
"""

import os
import sys
import sqlite3
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from pathlib import Path

# Add project root for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from apps.investor_portal.api.services.auth_service import (
    validate_password,
    hash_password,
    verify_password,
    generate_token,
    initiate_verification,
    complete_verification,
    authenticate_user,
    initiate_password_reset,
    complete_password_reset,
    VERIFICATION_TOKEN_HOURS,
    RESET_TOKEN_HOURS,
    MAX_FAILED_ATTEMPTS,
    LOCKOUT_MINUTES,
)


# ============================================================
# Test Database Fixture
# ============================================================

def _create_auth_test_db(db_path):
    """Create a test database with auth-compatible schema."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Investors table (matches production schema column names)
    conn.execute("""
        CREATE TABLE investors (
            investor_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            status TEXT NOT NULL DEFAULT 'Active',
            initial_capital REAL NOT NULL DEFAULT 0,
            join_date TEXT NOT NULL,
            current_shares REAL NOT NULL DEFAULT 0,
            net_investment REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Auth table (matches production schema)
    conn.execute("""
        CREATE TABLE investor_auth (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investor_id TEXT NOT NULL UNIQUE,
            password_hash TEXT,
            email_verified INTEGER DEFAULT 0,
            verification_token TEXT,
            verification_token_expires TIMESTAMP,
            reset_token TEXT,
            reset_token_expires TIMESTAMP,
            last_login TIMESTAMP,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (investor_id) REFERENCES investors(investor_id)
        )
    """)
    conn.execute("CREATE INDEX idx_auth_investor ON investor_auth(investor_id)")
    conn.execute("CREATE INDEX idx_auth_verify ON investor_auth(verification_token)")
    conn.execute("CREATE INDEX idx_auth_reset ON investor_auth(reset_token)")

    # Insert test investors
    conn.execute("""
        INSERT INTO investors (investor_id, name, email, status, join_date)
        VALUES ('20260101-01A', 'Active Investor', 'active@test.com', 'Active', '2026-01-01')
    """)
    conn.execute("""
        INSERT INTO investors (investor_id, name, email, status, join_date)
        VALUES ('20260101-02A', 'Closed Investor', 'closed@test.com', 'Closed', '2026-01-01')
    """)
    conn.execute("""
        INSERT INTO investors (investor_id, name, email, status, join_date)
        VALUES ('20260101-03A', 'Another Active', 'another@test.com', 'Active', '2026-01-15')
    """)

    conn.commit()
    return conn


@pytest.fixture
def auth_db(tmp_path):
    """Create a temporary auth test database and patch get_connection."""
    db_path = tmp_path / "test_auth.db"
    conn = _create_auth_test_db(str(db_path))
    conn.close()

    def mock_get_connection():
        c = sqlite3.connect(str(db_path))
        c.row_factory = sqlite3.Row
        return c

    with patch(
        "apps.investor_portal.api.services.auth_service.get_connection",
        mock_get_connection
    ):
        yield db_path


# ============================================================
# Password Validation Tests
# ============================================================

class TestValidatePassword:
    """Test password validation rules."""

    def test_valid_password(self):
        is_valid, msg = validate_password("SecurePass1!")
        assert is_valid is True

    def test_too_short(self):
        is_valid, msg = validate_password("Aa1!")
        assert is_valid is False
        assert "8" in msg.lower() or "character" in msg.lower()

    def test_too_long(self):
        # bcrypt max is 72 bytes
        is_valid, msg = validate_password("A" * 73 + "a1!")
        assert is_valid is False

    def test_no_uppercase(self):
        is_valid, msg = validate_password("lowercase1!")
        assert is_valid is False
        assert "uppercase" in msg.lower()

    def test_no_lowercase(self):
        is_valid, msg = validate_password("UPPERCASE1!")
        assert is_valid is False
        assert "lowercase" in msg.lower()

    def test_no_digit(self):
        is_valid, msg = validate_password("NoDigitHere!")
        assert is_valid is False
        assert "number" in msg.lower() or "digit" in msg.lower()

    def test_no_special(self):
        is_valid, msg = validate_password("NoSpecial1A")
        assert is_valid is False
        assert "special" in msg.lower()

    def test_boundary_length_8(self):
        """Exactly 8 characters should pass if all rules met."""
        is_valid, _ = validate_password("Abcde1!x")
        assert is_valid is True

    def test_boundary_length_72(self):
        """Exactly 72 characters should pass."""
        pwd = "Aa1!" + "x" * 68  # 72 chars total
        is_valid, _ = validate_password(pwd)
        assert is_valid is True


# ============================================================
# Password Hashing Tests
# ============================================================

class TestPasswordHashing:
    """Test bcrypt password hashing."""

    def test_hash_and_verify(self):
        password = "TestPassword1!"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("CorrectPass1!")
        assert verify_password("WrongPass1!", hashed) is False

    def test_hash_is_unique(self):
        """Different calls should produce different hashes (different salts)."""
        h1 = hash_password("SamePass1!")
        h2 = hash_password("SamePass1!")
        assert h1 != h2  # Different salts


# ============================================================
# Token Generation Tests
# ============================================================

class TestTokenGeneration:
    """Test secure token generation."""

    def test_token_is_string(self):
        token = generate_token()
        assert isinstance(token, str)
        assert len(token) > 20

    def test_tokens_are_unique(self):
        t1 = generate_token()
        t2 = generate_token()
        assert t1 != t2


# ============================================================
# Initiate Verification Tests
# ============================================================

class TestInitiateVerification:
    """Test the initiate_verification flow."""

    def test_valid_email(self, auth_db):
        success, message, data = initiate_verification("active@test.com")
        assert success is True
        assert data is not None
        assert data["investor_id"] == "20260101-01A"
        assert data["name"] == "Active Investor"
        assert data["email"] == "active@test.com"
        assert "token" in data
        assert len(data["token"]) > 20

    def test_unknown_email(self, auth_db):
        success, message, data = initiate_verification("unknown@test.com")
        assert success is False
        assert "not found" in message.lower()
        assert data is None

    def test_inactive_investor(self, auth_db):
        success, message, data = initiate_verification("closed@test.com")
        assert success is False
        assert "not active" in message.lower()
        assert data is None

    def test_already_set_up(self, auth_db):
        # First, set up the account
        success, _, data = initiate_verification("active@test.com")
        assert success is True
        complete_verification(data["token"], "SecurePass1!")

        # Try to initiate again
        success, message, _ = initiate_verification("active@test.com")
        assert success is False
        assert "already set up" in message.lower()

    def test_replaces_old_token(self, auth_db):
        # First initiation
        _, _, data1 = initiate_verification("active@test.com")
        token1 = data1["token"]

        # Second initiation (replaces token)
        _, _, data2 = initiate_verification("active@test.com")
        token2 = data2["token"]

        assert token1 != token2

        # Old token should be invalid now
        conn = sqlite3.connect(str(auth_db))
        row = conn.execute(
            "SELECT verification_token FROM investor_auth WHERE investor_id = '20260101-01A'"
        ).fetchone()
        conn.close()
        assert row[0] == token2

    def test_stores_token_in_db(self, auth_db):
        success, _, data = initiate_verification("active@test.com")
        assert success is True

        conn = sqlite3.connect(str(auth_db))
        row = conn.execute(
            "SELECT verification_token, verification_token_expires FROM investor_auth WHERE investor_id = '20260101-01A'"
        ).fetchone()
        conn.close()

        assert row[0] == data["token"]
        assert row[1] is not None  # Expiration set


# ============================================================
# Complete Verification Tests
# ============================================================

class TestCompleteVerification:
    """Test the complete_verification flow."""

    def test_valid_token_and_password(self, auth_db):
        # Initiate first
        _, _, data = initiate_verification("active@test.com")
        token = data["token"]

        # Complete verification
        success, message, result = complete_verification(token, "SecurePass1!")
        assert success is True
        assert result["investor_id"] == "20260101-01A"
        assert result["name"] == "Active Investor"

        # Verify DB state
        conn = sqlite3.connect(str(auth_db))
        row = conn.execute(
            "SELECT email_verified, password_hash, verification_token FROM investor_auth WHERE investor_id = '20260101-01A'"
        ).fetchone()
        conn.close()

        assert row[0] == 1  # email_verified
        assert row[1] is not None  # password_hash set
        assert row[2] is None  # token cleared

    def test_invalid_token(self, auth_db):
        success, message, _ = complete_verification("garbage-token-xyz", "SecurePass1!")
        assert success is False
        assert "invalid" in message.lower() or "expired" in message.lower()

    def test_expired_token(self, auth_db):
        # Initiate to create auth record
        _, _, data = initiate_verification("active@test.com")
        token = data["token"]

        # Manually expire the token
        conn = sqlite3.connect(str(auth_db))
        expired = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        conn.execute(
            "UPDATE investor_auth SET verification_token_expires = ? WHERE investor_id = '20260101-01A'",
            (expired,)
        )
        conn.commit()
        conn.close()

        success, message, _ = complete_verification(token, "SecurePass1!")
        assert success is False
        assert "expired" in message.lower()

    def test_weak_password_rejected(self, auth_db):
        _, _, data = initiate_verification("active@test.com")
        token = data["token"]

        # Too short
        success, message, _ = complete_verification(token, "short")
        assert success is False
        assert "password" in message.lower()

    def test_password_no_special_char(self, auth_db):
        _, _, data = initiate_verification("active@test.com")
        token = data["token"]

        success, message, _ = complete_verification(token, "NoSpecial1A")
        assert success is False


# ============================================================
# Authentication Tests
# ============================================================

class TestAuthentication:
    """Test the authenticate_user flow."""

    def _setup_verified_account(self, auth_db, email="active@test.com", password="SecurePass1!"):
        """Helper: create a fully verified account."""
        _, _, data = initiate_verification(email)
        complete_verification(data["token"], password)

    def test_successful_login(self, auth_db):
        self._setup_verified_account(auth_db)
        success, message, data = authenticate_user("active@test.com", "SecurePass1!")
        assert success is True
        assert data["investor_id"] == "20260101-01A"
        assert data["name"] == "Active Investor"

    def test_wrong_password(self, auth_db):
        self._setup_verified_account(auth_db)
        success, message, _ = authenticate_user("active@test.com", "WrongPass1!")
        assert success is False
        assert "invalid" in message.lower() or "attempts remaining" in message.lower()

    def test_failed_attempts_increment(self, auth_db):
        self._setup_verified_account(auth_db)

        # First failure
        authenticate_user("active@test.com", "WrongPass1!")

        conn = sqlite3.connect(str(auth_db))
        row = conn.execute(
            "SELECT failed_attempts FROM investor_auth WHERE investor_id = '20260101-01A'"
        ).fetchone()
        conn.close()
        assert row[0] == 1

    def test_account_lockout(self, auth_db):
        self._setup_verified_account(auth_db)

        # Fail MAX_FAILED_ATTEMPTS times
        for i in range(MAX_FAILED_ATTEMPTS):
            authenticate_user("active@test.com", "WrongPass1!")

        # Next attempt should be locked
        success, message, _ = authenticate_user("active@test.com", "SecurePass1!")
        assert success is False
        assert "locked" in message.lower()

    def test_lockout_expires(self, auth_db):
        self._setup_verified_account(auth_db)

        # Lock the account
        for _ in range(MAX_FAILED_ATTEMPTS):
            authenticate_user("active@test.com", "WrongPass1!")

        # Manually set lockout to the past
        conn = sqlite3.connect(str(auth_db))
        past = (datetime.utcnow() - timedelta(minutes=1)).isoformat()
        conn.execute(
            "UPDATE investor_auth SET locked_until = ? WHERE investor_id = '20260101-01A'",
            (past,)
        )
        conn.commit()
        conn.close()

        # Should be able to login now (lockout expired)
        success, _, _ = authenticate_user("active@test.com", "SecurePass1!")
        assert success is True

    def test_not_set_up(self, auth_db):
        """Unverified account should not be able to login."""
        success, message, _ = authenticate_user("active@test.com", "SomePass1!")
        assert success is False
        assert "not set up" in message.lower() or "invalid" in message.lower()

    def test_unknown_email(self, auth_db):
        success, message, _ = authenticate_user("nobody@test.com", "Pass1!")
        assert success is False
        assert "invalid" in message.lower()

    def test_successful_login_resets_failed_attempts(self, auth_db):
        self._setup_verified_account(auth_db)

        # Fail a couple times
        authenticate_user("active@test.com", "WrongPass1!")
        authenticate_user("active@test.com", "WrongPass1!")

        # Successful login
        authenticate_user("active@test.com", "SecurePass1!")

        conn = sqlite3.connect(str(auth_db))
        row = conn.execute(
            "SELECT failed_attempts FROM investor_auth WHERE investor_id = '20260101-01A'"
        ).fetchone()
        conn.close()
        assert row[0] == 0


# ============================================================
# Password Reset Flow Tests
# ============================================================

class TestPasswordReset:
    """Test the password reset flow."""

    def _setup_verified_account(self, auth_db, email="active@test.com", password="SecurePass1!"):
        """Helper: create a fully verified account."""
        _, _, data = initiate_verification(email)
        complete_verification(data["token"], password)

    def test_initiate_reset_valid(self, auth_db):
        self._setup_verified_account(auth_db)
        success, message, data = initiate_password_reset("active@test.com")
        assert success is True
        assert data is not None
        assert "token" in data

    def test_initiate_reset_unknown_email(self, auth_db):
        # Should return success (no email enumeration)
        success, message, data = initiate_password_reset("nobody@test.com")
        assert success is True
        assert data is None  # No token generated

    def test_initiate_reset_not_set_up(self, auth_db):
        # Unverified account
        success, message, data = initiate_password_reset("active@test.com")
        assert success is False
        assert "not set up" in message.lower()

    def test_complete_reset(self, auth_db):
        self._setup_verified_account(auth_db)

        # Initiate reset
        _, _, data = initiate_password_reset("active@test.com")
        token = data["token"]

        # Complete reset with new password
        success, message = complete_password_reset(token, "NewSecure2@")
        assert success is True

        # Login with new password
        success, _, _ = authenticate_user("active@test.com", "NewSecure2@")
        assert success is True

        # Old password should fail
        success, _, _ = authenticate_user("active@test.com", "SecurePass1!")
        assert success is False

    def test_complete_reset_clears_lockout(self, auth_db):
        self._setup_verified_account(auth_db)

        # Lock the account
        for _ in range(MAX_FAILED_ATTEMPTS):
            authenticate_user("active@test.com", "WrongPass1!")

        # Reset password
        _, _, data = initiate_password_reset("active@test.com")
        complete_password_reset(data["token"], "NewSecure2@")

        # Should be able to login (lockout cleared)
        success, _, _ = authenticate_user("active@test.com", "NewSecure2@")
        assert success is True


# ============================================================
# Full Flow Integration Tests
# ============================================================

class TestFullFlow:
    """End-to-end flow tests."""

    def test_complete_registration_flow(self, auth_db):
        """Initiate -> verify -> login: full happy path."""
        # Step 1: Initiate
        success, _, data = initiate_verification("another@test.com")
        assert success is True
        token = data["token"]

        # Step 2: Verify and set password
        success, _, result = complete_verification(token, "MySecure1@pass")
        assert success is True
        assert result["investor_id"] == "20260101-03A"

        # Step 3: Login
        success, _, login_data = authenticate_user("another@test.com", "MySecure1@pass")
        assert success is True
        assert login_data["name"] == "Another Active"

    def test_registration_then_reset_flow(self, auth_db):
        """Full registration followed by password reset."""
        # Register
        _, _, data = initiate_verification("active@test.com")
        complete_verification(data["token"], "FirstPass1!")

        # Login works
        success, _, _ = authenticate_user("active@test.com", "FirstPass1!")
        assert success is True

        # Reset password
        _, _, reset_data = initiate_password_reset("active@test.com")
        complete_password_reset(reset_data["token"], "SecondPass2@")

        # New password works
        success, _, _ = authenticate_user("active@test.com", "SecondPass2@")
        assert success is True

        # Old password fails
        success, _, _ = authenticate_user("active@test.com", "FirstPass1!")
        assert success is False
