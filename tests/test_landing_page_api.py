"""
Tests for the public landing page API endpoints.

Tests cover:
- get_teaser_stats() database function
- create_prospect() database function
- Prospect email verification flow
- Public API endpoint behavior (no auth required)
- Input validation and rate limiting
- Email enumeration prevention
"""

import pytest
import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# Test database path (matches conftest.py)
TEST_DB_PATH = "data/test_tovito.db"


# ============================================================
# get_teaser_stats() Database Function Tests
# ============================================================

class TestGetTeaserStats:
    """Tests for the get_teaser_stats() database function."""

    def test_teaser_stats_with_data(self, populated_db):
        """Normal case: returns correct stats from populated database."""
        with patch("apps.investor_portal.api.models.database.get_database_path") as mock_path:
            mock_path.return_value = TEST_DB_PATH
            from apps.investor_portal.api.models.database import get_teaser_stats

            stats = get_teaser_stats()

            assert "since_inception_pct" in stats
            assert "inception_date" in stats
            assert "total_investors" in stats
            assert "trading_days" in stats
            assert "as_of_date" in stats

            # Populated db has 4 active investors
            assert stats["total_investors"] == 4
            # Populated db has 5 NAV entries
            assert stats["trading_days"] == 5
            # Inception date is first NAV date
            assert stats["inception_date"] == "2026-01-01"
            # As-of date is last NAV date
            assert stats["as_of_date"] == "2026-01-05"
            # Since inception should be positive (NAV went from 38000 to 40000)
            assert stats["since_inception_pct"] > 0

    def test_teaser_stats_empty_database(self, test_db):
        """Empty database returns safe defaults."""
        with patch("apps.investor_portal.api.models.database.get_database_path") as mock_path:
            mock_path.return_value = TEST_DB_PATH
            from apps.investor_portal.api.models.database import get_teaser_stats

            stats = get_teaser_stats()

            assert stats["since_inception_pct"] == 0.0
            assert stats["total_investors"] == 0
            assert stats["trading_days"] == 0

    def test_teaser_stats_does_not_expose_portfolio_value(self, populated_db):
        """Verify the response does NOT contain sensitive data."""
        with patch("apps.investor_portal.api.models.database.get_database_path") as mock_path:
            mock_path.return_value = TEST_DB_PATH
            from apps.investor_portal.api.models.database import get_teaser_stats

            stats = get_teaser_stats()

            # These fields must NEVER be in the public response
            assert "total_portfolio_value" not in stats
            assert "nav_per_share" not in stats
            assert "current_nav" not in stats
            assert "total_shares" not in stats

    def test_teaser_stats_single_day(self, test_db):
        """Edge case: only one NAV entry."""
        now = datetime.now().isoformat()
        test_db.execute("""
            INSERT INTO daily_nav (date, nav_per_share, total_portfolio_value,
                                   total_shares, daily_change_dollars, daily_change_percent, created_at)
            VALUES ('2026-01-01', 1.0, 10000, 10000, 0, 0, ?)
        """, (now,))
        test_db.commit()

        with patch("apps.investor_portal.api.models.database.get_database_path") as mock_path:
            mock_path.return_value = TEST_DB_PATH
            from apps.investor_portal.api.models.database import get_teaser_stats

            stats = get_teaser_stats()

            assert stats["trading_days"] == 1
            assert stats["since_inception_pct"] == 0.0  # Same start and end NAV
            assert stats["inception_date"] == "2026-01-01"
            assert stats["as_of_date"] == "2026-01-01"


# ============================================================
# create_prospect() Database Function Tests
# ============================================================

class TestCreateProspect:
    """Tests for the create_prospect() database function."""

    def test_create_prospect_success(self, test_db):
        """Normal insert creates a prospect row."""
        with patch("apps.investor_portal.api.models.database.get_database_path") as mock_path:
            mock_path.return_value = TEST_DB_PATH
            from apps.investor_portal.api.models.database import create_prospect

            result = create_prospect(
                name="John Smith",
                email="john@example.com",
                phone="555-1234",
                message="Interested in investing",
            )

            assert result["success"] is True
            assert result["is_duplicate"] is False
            assert result["prospect_id"] is not None

            # Verify row exists in database
            cursor = test_db.cursor()
            cursor.execute("SELECT * FROM prospects WHERE email = ?", ("john@example.com",))
            row = cursor.fetchone()
            assert row is not None
            assert row["name"] == "John Smith"
            assert row["phone"] == "555-1234"
            assert row["source"] == "landing_page"
            assert row["notes"] == "Interested in investing"

    def test_create_prospect_duplicate_email(self, test_db):
        """Duplicate email returns is_duplicate=True without error."""
        with patch("apps.investor_portal.api.models.database.get_database_path") as mock_path:
            mock_path.return_value = TEST_DB_PATH
            from apps.investor_portal.api.models.database import create_prospect

            # First insert
            result1 = create_prospect(name="John", email="john@example.com")
            assert result1["is_duplicate"] is False

            # Second insert with same email
            result2 = create_prospect(name="John Again", email="john@example.com")
            assert result2["success"] is True
            assert result2["is_duplicate"] is True
            assert result2["prospect_id"] == result1["prospect_id"]
            assert result2["email_verified"] == 0

    def test_create_prospect_minimal_fields(self, test_db):
        """Only name and email (phone/message null)."""
        with patch("apps.investor_portal.api.models.database.get_database_path") as mock_path:
            mock_path.return_value = TEST_DB_PATH
            from apps.investor_portal.api.models.database import create_prospect

            result = create_prospect(name="Jane", email="jane@example.com")

            assert result["success"] is True

            cursor = test_db.cursor()
            cursor.execute("SELECT * FROM prospects WHERE email = ?", ("jane@example.com",))
            row = cursor.fetchone()
            assert row["phone"] is None
            assert row["notes"] is None

    def test_create_prospect_source_tag(self, test_db):
        """Source field is set correctly."""
        with patch("apps.investor_portal.api.models.database.get_database_path") as mock_path:
            mock_path.return_value = TEST_DB_PATH
            from apps.investor_portal.api.models.database import create_prospect

            # Default source
            create_prospect(name="A", email="a@example.com")
            cursor = test_db.cursor()
            cursor.execute("SELECT source FROM prospects WHERE email = ?", ("a@example.com",))
            assert cursor.fetchone()["source"] == "landing_page"

            # Custom source
            create_prospect(name="B", email="b@example.com", source="referral")
            cursor.execute("SELECT source FROM prospects WHERE email = ?", ("b@example.com",))
            assert cursor.fetchone()["source"] == "referral"

    def test_create_prospect_special_characters(self, test_db):
        """Name with special characters stored safely (parameterized queries)."""
        with patch("apps.investor_portal.api.models.database.get_database_path") as mock_path:
            mock_path.return_value = TEST_DB_PATH
            from apps.investor_portal.api.models.database import create_prospect

            # SQL injection attempt in name
            result = create_prospect(
                name="Robert'); DROP TABLE prospects;--",
                email="bobby@tables.com",
                message="<script>alert('xss')</script>",
            )

            assert result["success"] is True

            cursor = test_db.cursor()
            cursor.execute("SELECT name, notes FROM prospects WHERE email = ?", ("bobby@tables.com",))
            row = cursor.fetchone()
            # Data should be stored as-is (raw text, not executed)
            assert row["name"] == "Robert'); DROP TABLE prospects;--"
            assert row["notes"] == "<script>alert('xss')</script>"

            # Table still exists
            cursor.execute("SELECT COUNT(*) as cnt FROM prospects")
            assert cursor.fetchone()["cnt"] >= 1


# ============================================================
# Public API Router Tests
# ============================================================

class TestPublicTeaserStatsEndpoint:
    """Tests for GET /public/teaser-stats endpoint."""

    def test_no_auth_required(self, populated_db):
        """Endpoint returns 200 without any authentication."""
        with patch("apps.investor_portal.api.models.database.get_database_path") as mock_path:
            mock_path.return_value = TEST_DB_PATH
            from apps.investor_portal.api.routes.public import teaser_stats
            import asyncio

            # Call the endpoint directly (no auth dependency)
            result = asyncio.run(teaser_stats())
            assert result.since_inception_pct is not None
            assert result.total_investors >= 0
            assert result.trading_days >= 0


class TestPublicInquiryEndpoint:
    """Tests for POST /public/inquiry endpoint."""

    def test_inquiry_success(self, test_db):
        """Valid inquiry returns success."""
        with patch("apps.investor_portal.api.models.database.get_database_path") as mock_path:
            mock_path.return_value = TEST_DB_PATH

            from apps.investor_portal.api.routes.public import submit_inquiry, InquiryRequest, _inquiry_rate_limit
            import asyncio

            # Clear rate limit state
            _inquiry_rate_limit.clear()

            request = InquiryRequest(
                name="Test User",
                email="test@example.com",
                phone="555-0000",
                message="Interested",
            )

            mock_request = MagicMock()
            mock_request.client.host = "127.0.0.1"

            mock_bg = MagicMock()

            result = asyncio.run(
                submit_inquiry(request, mock_request, mock_bg)
            )

            assert result.success is True
            assert "thank you" in result.message.lower()

    def test_inquiry_duplicate_email_same_response(self, test_db):
        """Duplicate email returns same success message (email enumeration safe)."""
        with patch("apps.investor_portal.api.models.database.get_database_path") as mock_path:
            mock_path.return_value = TEST_DB_PATH

            from apps.investor_portal.api.routes.public import submit_inquiry, InquiryRequest, _inquiry_rate_limit
            import asyncio

            _inquiry_rate_limit.clear()

            request = InquiryRequest(name="User A", email="same@example.com")

            mock_request = MagicMock()
            mock_request.client.host = "127.0.0.2"

            mock_bg = MagicMock()

            # First submission
            result1 = asyncio.run(
                submit_inquiry(request, mock_request, mock_bg)
            )

            # Second submission (duplicate)
            result2 = asyncio.run(
                submit_inquiry(request, mock_request, mock_bg)
            )

            # Both should succeed with the same message
            assert result1.success is True
            assert result2.success is True
            assert result1.message == result2.message

    def test_inquiry_sends_verification_email(self, test_db):
        """New prospect submission sends verification email (not confirmation)."""
        with patch("apps.investor_portal.api.models.database.get_database_path") as mock_path:
            mock_path.return_value = TEST_DB_PATH

            from apps.investor_portal.api.routes.public import submit_inquiry, InquiryRequest, _inquiry_rate_limit
            import asyncio

            _inquiry_rate_limit.clear()

            request = InquiryRequest(name="New User", email="new@example.com")

            mock_request = MagicMock()
            mock_request.client.host = "127.0.0.3"

            # First submission — should add 1 background task (verification email)
            mock_bg1 = MagicMock()
            asyncio.run(
                submit_inquiry(request, mock_request, mock_bg1)
            )
            assert mock_bg1.add_task.call_count == 1  # verification email only

    def test_inquiry_resends_verification_for_unverified_duplicate(self, test_db):
        """Duplicate email that is not yet verified gets verification resent."""
        with patch("apps.investor_portal.api.models.database.get_database_path") as mock_path:
            mock_path.return_value = TEST_DB_PATH

            from apps.investor_portal.api.routes.public import submit_inquiry, InquiryRequest, _inquiry_rate_limit
            import asyncio

            _inquiry_rate_limit.clear()

            request = InquiryRequest(name="Repeat User", email="repeat@example.com")

            mock_request = MagicMock()
            mock_request.client.host = "127.0.0.4"

            # First submission
            mock_bg1 = MagicMock()
            asyncio.run(submit_inquiry(request, mock_request, mock_bg1))
            assert mock_bg1.add_task.call_count == 1

            # Second submission (duplicate, not verified) — should resend verification
            mock_bg2 = MagicMock()
            asyncio.run(submit_inquiry(request, mock_request, mock_bg2))
            assert mock_bg2.add_task.call_count == 1  # resend verification


# ============================================================
# Rate Limiting Tests
# ============================================================

class TestRateLimiting:
    """Tests for the inquiry rate limiter."""

    def test_rate_limit_allows_under_threshold(self):
        """Requests under the limit are allowed."""
        from apps.investor_portal.api.routes.public import _check_rate_limit, _inquiry_rate_limit

        _inquiry_rate_limit.clear()

        # First 5 requests should be allowed
        for i in range(5):
            assert _check_rate_limit("10.0.0.1") is True

    def test_rate_limit_blocks_over_threshold(self):
        """Sixth request from same IP is blocked."""
        from apps.investor_portal.api.routes.public import _check_rate_limit, _inquiry_rate_limit

        _inquiry_rate_limit.clear()

        # Exhaust the limit
        for i in range(5):
            _check_rate_limit("10.0.0.2")

        # 6th should be blocked
        assert _check_rate_limit("10.0.0.2") is False

    def test_rate_limit_per_ip(self):
        """Different IPs have independent limits."""
        from apps.investor_portal.api.routes.public import _check_rate_limit, _inquiry_rate_limit

        _inquiry_rate_limit.clear()

        # Exhaust limit for IP A
        for i in range(5):
            _check_rate_limit("10.0.0.3")
        assert _check_rate_limit("10.0.0.3") is False

        # IP B should still be allowed
        assert _check_rate_limit("10.0.0.4") is True


# ============================================================
# Input Validation Tests (Pydantic Model)
# ============================================================

class TestInquiryValidation:
    """Tests for InquiryRequest Pydantic validation."""

    def test_valid_full_request(self):
        """All fields provided and valid."""
        from apps.investor_portal.api.routes.public import InquiryRequest

        req = InquiryRequest(
            name="John Smith",
            email="john@example.com",
            phone="555-1234",
            message="Interested in the fund",
        )
        assert req.name == "John Smith"
        assert req.email == "john@example.com"

    def test_valid_minimal_request(self):
        """Only required fields (name + email)."""
        from apps.investor_portal.api.routes.public import InquiryRequest

        req = InquiryRequest(name="Jane", email="jane@example.com")
        assert req.phone is None
        assert req.message is None

    def test_missing_name_raises(self):
        """Missing name raises validation error."""
        from apps.investor_portal.api.routes.public import InquiryRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            InquiryRequest(email="test@example.com")

    def test_missing_email_raises(self):
        """Missing email raises validation error."""
        from apps.investor_portal.api.routes.public import InquiryRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            InquiryRequest(name="Test")

    def test_invalid_email_raises(self):
        """Invalid email format raises validation error."""
        from apps.investor_portal.api.routes.public import InquiryRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            InquiryRequest(name="Test", email="not-an-email")

    def test_name_too_long_raises(self):
        """Name over 100 characters raises validation error."""
        from apps.investor_portal.api.routes.public import InquiryRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            InquiryRequest(name="A" * 101, email="test@example.com")

    def test_message_too_long_raises(self):
        """Message over 1000 characters raises validation error."""
        from apps.investor_portal.api.routes.public import InquiryRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            InquiryRequest(name="Test", email="test@example.com", message="A" * 1001)


# ============================================================
# Prospect Email Verification — Database Function Tests
# ============================================================

def _db_patch():
    """Helper to patch get_database_path for test DB."""
    return patch(
        "apps.investor_portal.api.models.database.get_database_path",
        return_value=Path(TEST_DB_PATH),
    )


def _insert_prospect(test_db, name="Test User", email="test@verify.com",
                      phone="555-0000", notes="Test notes"):
    """Helper to insert a prospect directly into the test DB."""
    test_db.execute("""
        INSERT INTO prospects (name, email, phone, date_added, status, source, notes,
                               created_at, updated_at)
        VALUES (?, ?, ?, date('now'), 'Active', 'test', ?, datetime('now'), datetime('now'))
    """, (name, email, phone, notes))
    test_db.commit()
    cursor = test_db.execute("SELECT id FROM prospects WHERE email = ?", (email,))
    return cursor.fetchone()["id"]


class TestStoreProspectVerificationToken:
    """Tests for store_prospect_verification_token() database function."""

    def test_store_token_success(self, test_db):
        """Token stored successfully on existing prospect."""
        prospect_id = _insert_prospect(test_db)
        expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()

        with _db_patch():
            from apps.investor_portal.api.models.database import store_prospect_verification_token

            result = store_prospect_verification_token(prospect_id, "test-token-123", expires)
            assert result is True

            # Verify token is stored
            cursor = test_db.execute(
                "SELECT verification_token, verification_token_expires FROM prospects WHERE id = ?",
                (prospect_id,)
            )
            row = cursor.fetchone()
            assert row["verification_token"] == "test-token-123"
            assert row["verification_token_expires"] == expires

    def test_store_token_nonexistent_prospect(self, test_db):
        """Returns False for nonexistent prospect ID."""
        expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()

        with _db_patch():
            from apps.investor_portal.api.models.database import store_prospect_verification_token

            result = store_prospect_verification_token(99999, "token-xxx", expires)
            assert result is False

    def test_store_token_overwrites_previous(self, test_db):
        """Storing a new token replaces the old one."""
        prospect_id = _insert_prospect(test_db)
        expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()

        with _db_patch():
            from apps.investor_portal.api.models.database import store_prospect_verification_token

            store_prospect_verification_token(prospect_id, "old-token", expires)
            store_prospect_verification_token(prospect_id, "new-token", expires)

            cursor = test_db.execute(
                "SELECT verification_token FROM prospects WHERE id = ?",
                (prospect_id,)
            )
            assert cursor.fetchone()["verification_token"] == "new-token"


class TestVerifyProspectEmail:
    """Tests for verify_prospect_email() database function."""

    def test_verify_valid_token(self, test_db):
        """Valid token sets email_verified=1 and returns prospect info."""
        prospect_id = _insert_prospect(test_db, name="Valid User", email="valid@test.com",
                                        phone="555-1111", notes="Test msg")
        expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()
        test_db.execute("""
            UPDATE prospects
            SET verification_token = 'valid-token', verification_token_expires = ?
            WHERE id = ?
        """, (expires, prospect_id))
        test_db.commit()

        with _db_patch():
            from apps.investor_portal.api.models.database import verify_prospect_email

            result = verify_prospect_email("valid-token")
            assert result is not None
            assert result["id"] == prospect_id
            assert result["name"] == "Valid User"
            assert result["email"] == "valid@test.com"
            assert result["phone"] == "555-1111"
            assert result["notes"] == "Test msg"

            # Verify email_verified is set
            cursor = test_db.execute(
                "SELECT email_verified, verification_token FROM prospects WHERE id = ?",
                (prospect_id,)
            )
            row = cursor.fetchone()
            assert row["email_verified"] == 1
            assert row["verification_token"] is None  # Token cleared

    def test_verify_expired_token(self, test_db):
        """Expired token returns None."""
        prospect_id = _insert_prospect(test_db, email="expired@test.com")
        expired = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        test_db.execute("""
            UPDATE prospects
            SET verification_token = 'expired-token', verification_token_expires = ?
            WHERE id = ?
        """, (expired, prospect_id))
        test_db.commit()

        with _db_patch():
            from apps.investor_portal.api.models.database import verify_prospect_email

            result = verify_prospect_email("expired-token")
            assert result is None

    def test_verify_invalid_token(self, test_db):
        """Unknown token returns None."""
        with _db_patch():
            from apps.investor_portal.api.models.database import verify_prospect_email

            result = verify_prospect_email("nonexistent-token")
            assert result is None

    def test_verify_already_verified(self, test_db):
        """Already-verified prospect returns success (idempotent)."""
        prospect_id = _insert_prospect(test_db, email="already@test.com")
        test_db.execute("""
            UPDATE prospects
            SET email_verified = 1, verification_token = 'used-token'
            WHERE id = ?
        """, (prospect_id,))
        test_db.commit()

        with _db_patch():
            from apps.investor_portal.api.models.database import verify_prospect_email

            result = verify_prospect_email("used-token")
            assert result is not None
            assert result["email"] == "already@test.com"

    def test_verify_clears_token_fields(self, test_db):
        """After verification, token and expires are NULL."""
        prospect_id = _insert_prospect(test_db, email="clear@test.com")
        expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()
        test_db.execute("""
            UPDATE prospects
            SET verification_token = 'clear-token', verification_token_expires = ?
            WHERE id = ?
        """, (expires, prospect_id))
        test_db.commit()

        with _db_patch():
            from apps.investor_portal.api.models.database import verify_prospect_email

            verify_prospect_email("clear-token")

            cursor = test_db.execute(
                "SELECT verification_token, verification_token_expires FROM prospects WHERE id = ?",
                (prospect_id,)
            )
            row = cursor.fetchone()
            assert row["verification_token"] is None
            assert row["verification_token_expires"] is None


class TestVerifyProspectEndpoint:
    """Tests for GET /public/verify-prospect endpoint."""

    def test_verify_endpoint_success(self, test_db):
        """Valid token returns verified=True."""
        prospect_id = _insert_prospect(test_db, email="endpoint@test.com")
        expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()
        test_db.execute("""
            UPDATE prospects
            SET verification_token = 'endpoint-token', verification_token_expires = ?
            WHERE id = ?
        """, (expires, prospect_id))
        test_db.commit()

        with _db_patch():
            from apps.investor_portal.api.routes.public import verify_prospect
            import asyncio

            mock_bg = MagicMock()
            result = asyncio.run(verify_prospect("endpoint-token", mock_bg))

            assert result.verified is True
            assert "verified" in result.message.lower()

            # Should trigger confirmation + admin notification emails
            assert mock_bg.add_task.call_count == 2

    def test_verify_endpoint_invalid_token(self, test_db):
        """Invalid token returns 400."""
        with _db_patch():
            from apps.investor_portal.api.routes.public import verify_prospect
            from fastapi import HTTPException
            import asyncio

            mock_bg = MagicMock()

            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(verify_prospect("nonexistent-token-value", mock_bg))

            assert exc_info.value.status_code == 400

    def test_verify_endpoint_short_token_rejected(self, test_db):
        """Token shorter than 10 chars returns 400."""
        with _db_patch():
            from apps.investor_portal.api.routes.public import verify_prospect
            from fastapi import HTTPException
            import asyncio

            mock_bg = MagicMock()

            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(verify_prospect("short", mock_bg))

            assert exc_info.value.status_code == 400
