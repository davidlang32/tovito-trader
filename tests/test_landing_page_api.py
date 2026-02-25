"""
Tests for the public landing page API endpoints.

Tests cover:
- get_teaser_stats() database function
- create_prospect() database function
- Public API endpoint behavior (no auth required)
- Input validation and rate limiting
- Email enumeration prevention
"""

import pytest
import sqlite3
import os
from datetime import datetime
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
            assert result2["prospect_id"] is None

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

    def test_inquiry_sends_emails_for_new_only(self, test_db):
        """Background emails are only sent for new prospects, not duplicates."""
        with patch("apps.investor_portal.api.models.database.get_database_path") as mock_path:
            mock_path.return_value = TEST_DB_PATH

            from apps.investor_portal.api.routes.public import submit_inquiry, InquiryRequest, _inquiry_rate_limit
            import asyncio

            _inquiry_rate_limit.clear()

            request = InquiryRequest(name="New User", email="new@example.com")

            mock_request = MagicMock()
            mock_request.client.host = "127.0.0.3"

            # First submission — should add background tasks
            mock_bg1 = MagicMock()
            asyncio.run(
                submit_inquiry(request, mock_request, mock_bg1)
            )
            assert mock_bg1.add_task.call_count == 2  # confirmation + admin notification

            # Second submission (duplicate) — should NOT add background tasks
            mock_bg2 = MagicMock()
            asyncio.run(
                submit_inquiry(request, mock_request, mock_bg2)
            )
            assert mock_bg2.add_task.call_count == 0


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
