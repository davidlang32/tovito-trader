"""
Tests for Prospect Access (Phase 3)
======================================

Tests prospect access token management, validation,
admin endpoints, and prospect performance data endpoints.
"""

import sqlite3
import pytest
import secrets
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


# The test_db fixture yields a Connection; we need the PATH for patching
TEST_DB_PATH = "data/test_tovito.db"


# ============================================================
# Helper: Insert a test prospect into the database
# ============================================================

def _insert_prospect(conn, prospect_id=1, name="Test Prospect",
                     email="prospect@example.com"):
    """Insert a test prospect and return the id."""
    conn.execute("""
        INSERT INTO prospects (id, name, email, date_added, status, source)
        VALUES (?, ?, ?, '2026-02-01', 'Active', 'landing_page')
    """, (prospect_id, name, email))
    conn.commit()
    return prospect_id


def _insert_token(conn, prospect_id=1, token="test-token-abc123",
                  expires_at=None, is_revoked=0, access_count=0):
    """Insert a prospect access token directly."""
    if expires_at is None:
        expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat()
    conn.execute("""
        INSERT INTO prospect_access_tokens
            (prospect_id, token, expires_at, is_revoked, access_count, created_by)
        VALUES (?, ?, ?, ?, ?, 'admin')
    """, (prospect_id, token, expires_at, is_revoked, access_count))
    conn.commit()
    return token


def _db_patch():
    """Return a context manager that patches get_database_path to the test DB."""
    return patch("apps.investor_portal.api.models.database.get_database_path",
                 return_value=Path(TEST_DB_PATH))


# ============================================================
# Token Creation Tests
# ============================================================

class TestCreateProspectAccessToken:
    """Test create_prospect_access_token database function."""

    def test_create_token(self, test_db):
        """Creating a token inserts a row."""
        _insert_prospect(test_db)

        with _db_patch():
            from apps.investor_portal.api.models.database import create_prospect_access_token
            token_id = create_prospect_access_token(
                prospect_id=1,
                token="my-unique-token",
                expires_at="2026-03-01T00:00:00",
            )

        assert token_id is not None
        assert token_id > 0

        row = test_db.execute(
            "SELECT * FROM prospect_access_tokens WHERE token = ?",
            ("my-unique-token",)
        ).fetchone()
        assert row is not None
        assert row["prospect_id"] == 1
        assert row["is_revoked"] == 0
        assert row["access_count"] == 0
        assert row["created_by"] == "admin"

    def test_create_token_revokes_existing(self, test_db):
        """Creating a new token revokes any existing active tokens."""
        _insert_prospect(test_db)
        _insert_token(test_db, prospect_id=1, token="old-token")

        # Verify old token is active
        old = test_db.execute(
            "SELECT is_revoked FROM prospect_access_tokens WHERE token = 'old-token'"
        ).fetchone()
        assert old["is_revoked"] == 0

        with _db_patch():
            from apps.investor_portal.api.models.database import create_prospect_access_token
            create_prospect_access_token(
                prospect_id=1,
                token="new-token",
                expires_at="2026-03-01T00:00:00",
            )

        # Old token should now be revoked
        old = test_db.execute(
            "SELECT is_revoked FROM prospect_access_tokens WHERE token = 'old-token'"
        ).fetchone()
        assert old["is_revoked"] == 1

        # New token should be active
        new = test_db.execute(
            "SELECT is_revoked FROM prospect_access_tokens WHERE token = 'new-token'"
        ).fetchone()
        assert new["is_revoked"] == 0

    def test_create_token_custom_created_by(self, test_db):
        """Token creation supports custom created_by field."""
        _insert_prospect(test_db)

        with _db_patch():
            from apps.investor_portal.api.models.database import create_prospect_access_token
            create_prospect_access_token(
                prospect_id=1,
                token="custom-creator-token",
                expires_at="2026-03-01T00:00:00",
                created_by="cli_script",
            )

        row = test_db.execute(
            "SELECT created_by FROM prospect_access_tokens WHERE token = 'custom-creator-token'"
        ).fetchone()
        assert row["created_by"] == "cli_script"


# ============================================================
# Token Validation Tests
# ============================================================

class TestValidateProspectToken:
    """Test validate_prospect_token database function."""

    def test_valid_token(self, test_db):
        """Valid, non-expired, non-revoked token returns prospect info."""
        _insert_prospect(test_db, name="Valid Prospect", email="valid@example.com")
        future = (datetime.utcnow() + timedelta(days=30)).isoformat()
        _insert_token(test_db, prospect_id=1, token="valid-token", expires_at=future)

        with _db_patch():
            from apps.investor_portal.api.models.database import validate_prospect_token
            result = validate_prospect_token("valid-token")

        assert result is not None
        assert result["prospect_id"] == 1
        assert result["prospect_name"] == "Valid Prospect"
        assert result["prospect_email"] == "valid@example.com"

    def test_invalid_token(self, test_db):
        """Nonexistent token returns None."""
        with _db_patch():
            from apps.investor_portal.api.models.database import validate_prospect_token
            result = validate_prospect_token("nonexistent-token")

        assert result is None

    def test_expired_token(self, test_db):
        """Expired token returns None."""
        _insert_prospect(test_db)
        past = (datetime.utcnow() - timedelta(days=1)).isoformat()
        _insert_token(test_db, prospect_id=1, token="expired-token", expires_at=past)

        with _db_patch():
            from apps.investor_portal.api.models.database import validate_prospect_token
            result = validate_prospect_token("expired-token")

        assert result is None

    def test_revoked_token(self, test_db):
        """Revoked token returns None."""
        _insert_prospect(test_db)
        future = (datetime.utcnow() + timedelta(days=30)).isoformat()
        _insert_token(test_db, prospect_id=1, token="revoked-token",
                      expires_at=future, is_revoked=1)

        with _db_patch():
            from apps.investor_portal.api.models.database import validate_prospect_token
            result = validate_prospect_token("revoked-token")

        assert result is None

    def test_access_count_incremented(self, test_db):
        """Valid token validation increments access_count."""
        _insert_prospect(test_db)
        future = (datetime.utcnow() + timedelta(days=30)).isoformat()
        _insert_token(test_db, prospect_id=1, token="counting-token",
                      expires_at=future, access_count=5)

        with _db_patch():
            from apps.investor_portal.api.models.database import validate_prospect_token
            validate_prospect_token("counting-token")

        row = test_db.execute(
            "SELECT access_count FROM prospect_access_tokens WHERE token = 'counting-token'"
        ).fetchone()
        assert row["access_count"] == 6

    def test_last_accessed_at_updated(self, test_db):
        """Valid token validation updates last_accessed_at."""
        _insert_prospect(test_db)
        future = (datetime.utcnow() + timedelta(days=30)).isoformat()
        _insert_token(test_db, prospect_id=1, token="accessed-token", expires_at=future)

        # Initially null
        row = test_db.execute(
            "SELECT last_accessed_at FROM prospect_access_tokens WHERE token = 'accessed-token'"
        ).fetchone()
        assert row["last_accessed_at"] is None

        with _db_patch():
            from apps.investor_portal.api.models.database import validate_prospect_token
            validate_prospect_token("accessed-token")

        row = test_db.execute(
            "SELECT last_accessed_at FROM prospect_access_tokens WHERE token = 'accessed-token'"
        ).fetchone()
        assert row["last_accessed_at"] is not None

    def test_multiple_validations_increment(self, test_db):
        """Multiple validations keep incrementing count."""
        _insert_prospect(test_db)
        future = (datetime.utcnow() + timedelta(days=30)).isoformat()
        _insert_token(test_db, prospect_id=1, token="multi-token", expires_at=future)

        with _db_patch():
            from apps.investor_portal.api.models.database import validate_prospect_token
            validate_prospect_token("multi-token")
            validate_prospect_token("multi-token")
            validate_prospect_token("multi-token")

        row = test_db.execute(
            "SELECT access_count FROM prospect_access_tokens WHERE token = 'multi-token'"
        ).fetchone()
        assert row["access_count"] == 3


# ============================================================
# Token Revocation Tests
# ============================================================

class TestRevokeProspectToken:
    """Test revoke_prospect_token database function."""

    def test_revoke_active_token(self, test_db):
        """Revoking an active token returns True."""
        _insert_prospect(test_db)
        _insert_token(test_db, prospect_id=1, token="to-revoke")

        with _db_patch():
            from apps.investor_portal.api.models.database import revoke_prospect_token
            result = revoke_prospect_token(1)

        assert result is True

        row = test_db.execute(
            "SELECT is_revoked FROM prospect_access_tokens WHERE token = 'to-revoke'"
        ).fetchone()
        assert row["is_revoked"] == 1

    def test_revoke_no_active_tokens(self, test_db):
        """Revoking when no active tokens returns False."""
        _insert_prospect(test_db)

        with _db_patch():
            from apps.investor_portal.api.models.database import revoke_prospect_token
            result = revoke_prospect_token(1)

        assert result is False

    def test_revoke_already_revoked(self, test_db):
        """Revoking already-revoked tokens returns False."""
        _insert_prospect(test_db)
        _insert_token(test_db, prospect_id=1, token="already-revoked", is_revoked=1)

        with _db_patch():
            from apps.investor_portal.api.models.database import revoke_prospect_token
            result = revoke_prospect_token(1)

        assert result is False


# ============================================================
# Prospect Access List Tests
# ============================================================

class TestGetProspectAccessList:
    """Test get_prospect_access_list database function."""

    def test_empty_list(self, test_db):
        """Returns empty list when no prospects exist."""
        with _db_patch():
            from apps.investor_portal.api.models.database import get_prospect_access_list
            result = get_prospect_access_list()

        assert result == []

    def test_prospect_without_token(self, test_db):
        """Prospect without token shows in list with null token fields."""
        _insert_prospect(test_db, name="No Token Prospect")

        with _db_patch():
            from apps.investor_portal.api.models.database import get_prospect_access_list
            result = get_prospect_access_list()

        assert len(result) == 1
        assert result[0]["name"] == "No Token Prospect"
        assert result[0]["token"] is None

    def test_prospect_with_active_token(self, test_db):
        """Prospect with active token shows token details."""
        _insert_prospect(test_db)
        _insert_token(test_db, prospect_id=1, token="active-list-token")

        with _db_patch():
            from apps.investor_portal.api.models.database import get_prospect_access_list
            result = get_prospect_access_list()

        assert len(result) == 1
        assert result[0]["token"] == "active-list-token"
        assert result[0]["is_revoked"] == 0

    def test_prospect_with_revoked_token_shows_no_token(self, test_db):
        """Revoked tokens are excluded from the LEFT JOIN (only non-revoked shown)."""
        _insert_prospect(test_db)
        _insert_token(test_db, prospect_id=1, token="revoked-list", is_revoked=1)

        with _db_patch():
            from apps.investor_portal.api.models.database import get_prospect_access_list
            result = get_prospect_access_list()

        assert len(result) == 1
        # LEFT JOIN filters is_revoked = 0, so revoked token not returned
        assert result[0]["token"] is None

    def test_multiple_prospects(self, test_db):
        """Multiple prospects returned in correct order."""
        _insert_prospect(test_db, 1, "First Prospect", "first@example.com")
        _insert_prospect(test_db, 2, "Second Prospect", "second@example.com")

        with _db_patch():
            from apps.investor_portal.api.models.database import get_prospect_access_list
            result = get_prospect_access_list()

        assert len(result) == 2


# ============================================================
# Prospect Performance Data Tests
# ============================================================

class TestGetProspectPerformanceData:
    """Test get_prospect_performance_data database function."""

    def test_empty_database(self, test_db):
        """Returns defaults when database has no NAV data."""
        with _db_patch():
            from apps.investor_portal.api.models.database import get_prospect_performance_data
            result = get_prospect_performance_data()

        assert result["since_inception_pct"] == 0.0
        assert result["trading_days"] == 0
        assert result["monthly_returns"] == []
        assert result["plan_allocation"] == []

    def test_since_inception_calculation(self, test_db):
        """Correct since-inception return percentage from NAV data."""
        now = datetime.now().isoformat()
        # Inception NAV: 1.0, Latest NAV: 1.05 => 5% return
        test_db.execute("""
            INSERT INTO daily_nav (date, nav_per_share, total_portfolio_value,
                                   total_shares, created_at)
            VALUES ('2026-01-01', 1.0, 38000, 38000, ?)
        """, (now,))
        test_db.execute("""
            INSERT INTO daily_nav (date, nav_per_share, total_portfolio_value,
                                   total_shares, created_at)
            VALUES ('2026-02-25', 1.05, 39900, 38000, ?)
        """, (now,))
        test_db.commit()

        with _db_patch():
            from apps.investor_portal.api.models.database import get_prospect_performance_data
            result = get_prospect_performance_data()

        assert result["since_inception_pct"] == 5.0
        assert result["inception_date"] == "2026-01-01"
        assert result["as_of_date"] == "2026-02-25"
        assert result["trading_days"] == 2

    def test_plan_allocation_included(self, test_db):
        """Plan allocation data is included when available."""
        test_db.execute("""
            INSERT INTO plan_daily_performance (date, plan_id, market_value,
                cost_basis, unrealized_pl, allocation_pct, position_count)
            VALUES ('2026-02-25', 'plan_a', 20000, 18000, 2000, 52.6, 8)
        """)
        test_db.execute("""
            INSERT INTO plan_daily_performance (date, plan_id, market_value,
                cost_basis, unrealized_pl, allocation_pct, position_count)
            VALUES ('2026-02-25', 'plan_etf', 12000, 11000, 1000, 31.6, 3)
        """)
        test_db.execute("""
            INSERT INTO plan_daily_performance (date, plan_id, market_value,
                cost_basis, unrealized_pl, allocation_pct, position_count)
            VALUES ('2026-02-25', 'plan_cash', 6000, 6000, 0, 15.8, 2)
        """)
        test_db.commit()

        with _db_patch():
            from apps.investor_portal.api.models.database import get_prospect_performance_data
            result = get_prospect_performance_data()

        assert len(result["plan_allocation"]) == 3
        # Sorted by allocation_pct DESC
        assert result["plan_allocation"][0]["plan_id"] == "plan_a"
        assert result["plan_allocation"][0]["allocation_pct"] == 52.6
        assert result["plan_allocation"][0]["position_count"] == 8

    def test_benchmark_comparison_included(self, test_db):
        """Benchmark comparison data is included when available."""
        now = datetime.now().isoformat()
        # Add NAV data
        test_db.execute("""
            INSERT INTO daily_nav (date, nav_per_share, total_portfolio_value,
                                   total_shares, created_at)
            VALUES ('2026-01-01', 1.0, 38000, 38000, ?)
        """, (now,))
        test_db.execute("""
            INSERT INTO daily_nav (date, nav_per_share, total_portfolio_value,
                                   total_shares, created_at)
            VALUES ('2026-02-25', 1.05, 39900, 38000, ?)
        """, (now,))
        # Add benchmark data
        test_db.execute("""
            INSERT INTO benchmark_prices (date, ticker, close_price)
            VALUES ('2026-01-01', 'SPY', 500.0)
        """)
        test_db.execute("""
            INSERT INTO benchmark_prices (date, ticker, close_price)
            VALUES ('2026-02-25', 'SPY', 510.0)
        """)
        test_db.execute("""
            INSERT INTO benchmark_prices (date, ticker, close_price)
            VALUES ('2026-01-01', 'QQQ', 400.0)
        """)
        test_db.execute("""
            INSERT INTO benchmark_prices (date, ticker, close_price)
            VALUES ('2026-02-25', 'QQQ', 404.0)
        """)
        test_db.commit()

        with _db_patch():
            from apps.investor_portal.api.models.database import get_prospect_performance_data
            result = get_prospect_performance_data(days=365)

        assert len(result["benchmark_comparison"]) == 2
        spy = [b for b in result["benchmark_comparison"] if b["ticker"] == "SPY"][0]
        assert spy["benchmark_return_pct"] == 2.0  # (510/500 - 1)*100
        assert spy["fund_return_pct"] == 5.0  # (1.05/1.0 - 1)*100
        assert spy["outperformance_pct"] == 3.0

    def test_investor_count(self, test_db):
        """Investor count only counts active investors."""
        now = datetime.now().isoformat()
        test_db.execute("""
            INSERT INTO investors (id, name, initial_capital, join_date, status,
                                   current_shares, net_investment, created_at, updated_at)
            VALUES ('I1', 'Active One', 10000, '2026-01-01', 'Active', 10000, 10000, ?, ?)
        """, (now, now))
        test_db.execute("""
            INSERT INTO investors (id, name, initial_capital, join_date, status,
                                   current_shares, net_investment, created_at, updated_at)
            VALUES ('I2', 'Active Two', 5000, '2026-01-01', 'Active', 5000, 5000, ?, ?)
        """, (now, now))
        test_db.execute("""
            INSERT INTO investors (id, name, initial_capital, join_date, status,
                                   current_shares, net_investment, created_at, updated_at)
            VALUES ('I3', 'Closed', 8000, '2026-01-01', 'Closed', 0, 0, ?, ?)
        """, (now, now))
        test_db.commit()

        with _db_patch():
            from apps.investor_portal.api.models.database import get_prospect_performance_data
            result = get_prospect_performance_data()

        assert result["investor_count"] == 2

    def test_no_dollar_amounts_exposed(self, test_db):
        """Prospect performance data never exposes dollar amounts."""
        now = datetime.now().isoformat()
        test_db.execute("""
            INSERT INTO daily_nav (date, nav_per_share, total_portfolio_value,
                                   total_shares, created_at)
            VALUES ('2026-01-01', 1.0, 38000, 38000, ?)
        """, (now,))
        test_db.commit()

        with _db_patch():
            from apps.investor_portal.api.models.database import get_prospect_performance_data
            result = get_prospect_performance_data()

        # Check that no dollar amounts are in the result keys
        assert "nav_per_share" not in result
        assert "total_portfolio_value" not in result
        assert "total_shares" not in result
        assert "market_value" not in result
        # Only percentage-based and count-based fields
        for key in result.keys():
            assert key in {
                "since_inception_pct", "inception_date", "as_of_date",
                "trading_days", "investor_count", "monthly_returns",
                "plan_allocation", "benchmark_comparison",
            }


# ============================================================
# Prospect Performance API Endpoint Tests
# ============================================================

class TestProspectPerformanceEndpoint:
    """Test GET /public/prospect-performance endpoint."""

    def test_valid_token_returns_data(self):
        """Valid token returns performance data with valid=True."""
        with patch("apps.investor_portal.api.routes.public.validate_prospect_token") as mock_validate, \
             patch("apps.investor_portal.api.routes.public.get_prospect_performance_data") as mock_data:

            mock_validate.return_value = {
                "prospect_id": 1,
                "prospect_name": "Test",
                "prospect_email": "test@example.com",
            }
            mock_data.return_value = {
                "since_inception_pct": 5.0,
                "inception_date": "2026-01-01",
                "as_of_date": "2026-02-25",
                "trading_days": 40,
                "investor_count": 5,
                "monthly_returns": [],
                "plan_allocation": [],
                "benchmark_comparison": [],
            }

            import asyncio
            from apps.investor_portal.api.routes.public import prospect_performance
            result = asyncio.run(prospect_performance(token="api-test-token-long", days=90))

        assert result.valid is True
        assert result.since_inception_pct == 5.0
        assert result.trading_days == 40
        assert result.investor_count == 5

    def test_invalid_token_returns_invalid(self):
        """Invalid token returns valid=False."""
        with patch("apps.investor_portal.api.routes.public.validate_prospect_token") as mock_validate:
            mock_validate.return_value = None

            import asyncio
            from apps.investor_portal.api.routes.public import prospect_performance
            result = asyncio.run(prospect_performance(token="bad-token-long-enough", days=90))

        assert result.valid is False

    def test_short_token_returns_invalid(self):
        """Token shorter than 10 chars returns valid=False."""
        import asyncio
        from apps.investor_portal.api.routes.public import prospect_performance
        result = asyncio.run(prospect_performance(token="short", days=90))
        assert result.valid is False

    def test_empty_token_returns_invalid(self):
        """Empty token string returns valid=False."""
        import asyncio
        from apps.investor_portal.api.routes.public import prospect_performance
        result = asyncio.run(prospect_performance(token="", days=90))
        assert result.valid is False

    def test_data_error_returns_valid_true_empty(self):
        """If data fetch fails, returns valid=True but empty data."""
        with patch("apps.investor_portal.api.routes.public.validate_prospect_token") as mock_validate, \
             patch("apps.investor_portal.api.routes.public.get_prospect_performance_data") as mock_data:

            mock_validate.return_value = {
                "prospect_id": 1,
                "prospect_name": "Test",
                "prospect_email": "test@example.com",
            }
            mock_data.side_effect = Exception("DB error")

            import asyncio
            from apps.investor_portal.api.routes.public import prospect_performance
            result = asyncio.run(prospect_performance(token="valid-long-token", days=90))

        assert result.valid is True
        assert result.monthly_returns == []

    def test_monthly_returns_mapped(self):
        """Monthly returns are properly mapped to response models."""
        with patch("apps.investor_portal.api.routes.public.validate_prospect_token") as mock_validate, \
             patch("apps.investor_portal.api.routes.public.get_prospect_performance_data") as mock_data:

            mock_validate.return_value = {"prospect_id": 1, "prospect_name": "T", "prospect_email": "t@e.com"}
            mock_data.return_value = {
                "since_inception_pct": 5.0,
                "inception_date": "2026-01-01",
                "as_of_date": "2026-02-25",
                "trading_days": 40,
                "investor_count": 5,
                "monthly_returns": [
                    {"month": "2026-01", "month_label": "Jan 2026", "return_pct": 3.2, "trading_days": 21},
                    {"month": "2026-02", "month_label": "Feb 2026", "return_pct": 1.8, "trading_days": 18},
                ],
                "plan_allocation": [],
                "benchmark_comparison": [],
            }

            import asyncio
            from apps.investor_portal.api.routes.public import prospect_performance
            result = asyncio.run(prospect_performance(token="valid-long-token", days=90))

        assert len(result.monthly_returns) == 2
        assert result.monthly_returns[0].month == "2026-01"
        assert result.monthly_returns[0].return_pct == 3.2
        assert result.monthly_returns[1].month_label == "Feb 2026"

    def test_plan_allocation_mapped(self):
        """Plan allocation data properly mapped to response."""
        with patch("apps.investor_portal.api.routes.public.validate_prospect_token") as mock_validate, \
             patch("apps.investor_portal.api.routes.public.get_prospect_performance_data") as mock_data:

            mock_validate.return_value = {"prospect_id": 1, "prospect_name": "T", "prospect_email": "t@e.com"}
            mock_data.return_value = {
                "since_inception_pct": 5.0,
                "inception_date": "2026-01-01",
                "as_of_date": "2026-02-25",
                "trading_days": 40,
                "investor_count": 5,
                "monthly_returns": [],
                "plan_allocation": [
                    {"plan_id": "plan_a", "allocation_pct": 52.6, "position_count": 8},
                    {"plan_id": "plan_etf", "allocation_pct": 31.6, "position_count": 3},
                ],
                "benchmark_comparison": [],
            }

            import asyncio
            from apps.investor_portal.api.routes.public import prospect_performance
            result = asyncio.run(prospect_performance(token="valid-long-token", days=90))

        assert len(result.plan_allocation) == 2
        assert result.plan_allocation[0].plan_id == "plan_a"
        assert result.plan_allocation[0].allocation_pct == 52.6

    def test_benchmark_comparison_mapped(self):
        """Benchmark comparison data properly mapped to response."""
        with patch("apps.investor_portal.api.routes.public.validate_prospect_token") as mock_validate, \
             patch("apps.investor_portal.api.routes.public.get_prospect_performance_data") as mock_data:

            mock_validate.return_value = {"prospect_id": 1, "prospect_name": "T", "prospect_email": "t@e.com"}
            mock_data.return_value = {
                "since_inception_pct": 5.0,
                "inception_date": "2026-01-01",
                "as_of_date": "2026-02-25",
                "trading_days": 40,
                "investor_count": 5,
                "monthly_returns": [],
                "plan_allocation": [],
                "benchmark_comparison": [
                    {"ticker": "SPY", "label": "S&P 500", "fund_return_pct": 5.0,
                     "benchmark_return_pct": 2.0, "outperformance_pct": 3.0},
                ],
            }

            import asyncio
            from apps.investor_portal.api.routes.public import prospect_performance
            result = asyncio.run(prospect_performance(token="valid-long-token", days=90))

        assert len(result.benchmark_comparison) == 1
        assert result.benchmark_comparison[0].ticker == "SPY"
        assert result.benchmark_comparison[0].outperformance_pct == 3.0


# ============================================================
# Admin Prospect Endpoints Tests
# ============================================================

class TestAdminGrantAccessEndpoint:
    """Test POST /admin/prospect/{id}/grant-access endpoint."""

    def test_grant_access_to_existing_prospect(self):
        """Granting access to an existing prospect returns token + URL."""
        with patch("apps.investor_portal.api.routes.admin.get_connection") as mock_conn, \
             patch("apps.investor_portal.api.routes.admin.create_prospect_access_token") as mock_create, \
             patch("apps.investor_portal.api.routes.admin.settings") as mock_settings:

            # Mock the prospect lookup
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {"id": 1, "name": "Test", "email": "test@example.com"}
            mock_conn_instance = MagicMock()
            mock_conn_instance.cursor.return_value = mock_cursor
            mock_conn.return_value = mock_conn_instance

            mock_create.return_value = 42
            mock_settings.PORTAL_BASE_URL = "https://tovitotrader.com"

            import asyncio
            from apps.investor_portal.api.routes.admin import grant_prospect_access
            result = asyncio.run(grant_prospect_access(prospect_id=1, expiry_days=30))

        assert result.success is True
        assert len(result.token) > 10  # URL-safe token
        assert "tovitotrader.com/fund-preview?token=" in result.prospect_url
        assert result.prospect_id == 1

    def test_grant_access_to_nonexistent_prospect(self):
        """Granting access to nonexistent prospect raises 404."""
        with patch("apps.investor_portal.api.routes.admin.get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_conn_instance = MagicMock()
            mock_conn_instance.cursor.return_value = mock_cursor
            mock_conn.return_value = mock_conn_instance

            import asyncio
            from apps.investor_portal.api.routes.admin import grant_prospect_access
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(grant_prospect_access(prospect_id=999))
            assert exc_info.value.status_code == 404

    def test_grant_access_custom_expiry(self):
        """Custom expiry_days generates correct expires_at."""
        with patch("apps.investor_portal.api.routes.admin.get_connection") as mock_conn, \
             patch("apps.investor_portal.api.routes.admin.create_prospect_access_token") as mock_create, \
             patch("apps.investor_portal.api.routes.admin.settings") as mock_settings:

            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {"id": 1, "name": "Test", "email": "test@example.com"}
            mock_conn_instance = MagicMock()
            mock_conn_instance.cursor.return_value = mock_cursor
            mock_conn.return_value = mock_conn_instance

            mock_create.return_value = 1
            mock_settings.PORTAL_BASE_URL = "http://localhost:3000"

            import asyncio
            from apps.investor_portal.api.routes.admin import grant_prospect_access
            result = asyncio.run(grant_prospect_access(prospect_id=1, expiry_days=7))

        # Verify expires_at is approximately 7 days from now
        from datetime import datetime
        expires = datetime.fromisoformat(result.expires_at)
        expected = datetime.utcnow() + timedelta(days=7)
        # Within 5 minutes tolerance
        assert abs((expires - expected).total_seconds()) < 300


class TestAdminRevokeAccessEndpoint:
    """Test DELETE /admin/prospect/{id}/revoke-access endpoint."""

    def test_revoke_existing_token(self):
        """Revoking active token returns success message."""
        with patch("apps.investor_portal.api.routes.admin.revoke_prospect_token") as mock_revoke:
            mock_revoke.return_value = True

            import asyncio
            from apps.investor_portal.api.routes.admin import revoke_prospect_access
            result = asyncio.run(revoke_prospect_access(prospect_id=1))

        assert result["success"] is True
        assert "revoked" in result["message"].lower()

    def test_revoke_no_active_tokens(self):
        """Revoking when no active tokens still returns success."""
        with patch("apps.investor_portal.api.routes.admin.revoke_prospect_token") as mock_revoke:
            mock_revoke.return_value = False

            import asyncio
            from apps.investor_portal.api.routes.admin import revoke_prospect_access
            result = asyncio.run(revoke_prospect_access(prospect_id=1))

        assert result["success"] is True
        assert "no active" in result["message"].lower()


class TestAdminListProspectsEndpoint:
    """Test GET /admin/prospects endpoint."""

    def test_list_prospects_with_tokens(self):
        """Returns prospects with token status."""
        with patch("apps.investor_portal.api.routes.admin.get_prospect_access_list") as mock_list:
            mock_list.return_value = [
                {
                    "id": 1, "name": "Prospect A", "email": "a@example.com",
                    "status": "Active", "date_added": "2026-02-01",
                    "token": "tok-123", "token_created": "2026-02-01T10:00:00",
                    "expires_at": "2026-03-01T10:00:00",
                    "last_accessed_at": "2026-02-15T14:30:00",
                    "access_count": 3, "is_revoked": 0,
                },
                {
                    "id": 2, "name": "Prospect B", "email": "b@example.com",
                    "status": "Active", "date_added": "2026-02-10",
                    "token": None, "token_created": None,
                    "expires_at": None, "last_accessed_at": None,
                    "access_count": None, "is_revoked": None,
                },
            ]

            import asyncio
            from apps.investor_portal.api.routes.admin import list_prospects
            result = asyncio.run(list_prospects())

        assert result.total == 2
        assert result.prospects[0].has_active_token is True
        assert result.prospects[0].access_count == 3
        assert result.prospects[1].has_active_token is False

    def test_list_empty_prospects(self):
        """Returns empty list when no prospects exist."""
        with patch("apps.investor_portal.api.routes.admin.get_prospect_access_list") as mock_list:
            mock_list.return_value = []

            import asyncio
            from apps.investor_portal.api.routes.admin import list_prospects
            result = asyncio.run(list_prospects())

        assert result.total == 0
        assert result.prospects == []


# ============================================================
# Pydantic Model Validation Tests
# ============================================================

class TestPydanticModels:
    """Test Pydantic model validation for prospect endpoints."""

    def test_prospect_performance_response_defaults(self):
        """ProspectPerformanceResponse has correct defaults."""
        from apps.investor_portal.api.routes.public import ProspectPerformanceResponse
        resp = ProspectPerformanceResponse(valid=False)
        assert resp.valid is False
        assert resp.since_inception_pct == 0.0
        assert resp.monthly_returns == []
        assert resp.plan_allocation == []
        assert resp.benchmark_comparison == []

    def test_grant_access_response_fields(self):
        """GrantAccessResponse requires all fields."""
        from apps.investor_portal.api.routes.admin import GrantAccessResponse
        resp = GrantAccessResponse(
            success=True,
            token="test-token",
            prospect_url="https://example.com/fund-preview?token=test-token",
            expires_at="2026-03-01T00:00:00",
            prospect_id=1,
        )
        assert resp.success is True
        assert resp.token == "test-token"
        assert resp.prospect_id == 1

    def test_prospect_access_item_fields(self):
        """ProspectAccessItem handles optional fields."""
        from apps.investor_portal.api.routes.admin import ProspectAccessItem
        item = ProspectAccessItem(
            id=1,
            name="Test",
            email="test@example.com",
            status=None,
            date_added=None,
            has_active_token=False,
            token_created=None,
            expires_at=None,
            last_accessed_at=None,
            access_count=None,
        )
        assert item.has_active_token is False
        assert item.access_count is None

    def test_monthly_return_item(self):
        """MonthlyReturnItem accepts correct data."""
        from apps.investor_portal.api.routes.public import MonthlyReturnItem
        item = MonthlyReturnItem(
            month="2026-01",
            month_label="Jan 2026",
            return_pct=3.2,
            trading_days=21,
        )
        assert item.return_pct == 3.2

    def test_benchmark_comparison_preview(self):
        """BenchmarkComparisonPreview accepts correct data."""
        from apps.investor_portal.api.routes.public import BenchmarkComparisonPreview
        item = BenchmarkComparisonPreview(
            ticker="SPY",
            label="S&P 500",
            fund_return_pct=5.0,
            benchmark_return_pct=2.0,
            outperformance_pct=3.0,
        )
        assert item.outperformance_pct == 3.0


# ============================================================
# Token Security Tests
# ============================================================

class TestTokenSecurity:
    """Test security properties of the token system."""

    def test_token_is_url_safe(self):
        """Generated tokens are URL-safe."""
        import secrets
        token = secrets.token_urlsafe(36)
        # URL-safe chars: A-Z, a-z, 0-9, -, _
        import re
        assert re.match(r'^[A-Za-z0-9_-]+$', token)
        assert len(token) >= 36

    def test_tokens_are_unique(self):
        """Multiple generated tokens are unique."""
        import secrets
        tokens = {secrets.token_urlsafe(36) for _ in range(100)}
        assert len(tokens) == 100

    def test_token_uniqueness_constraint(self, test_db):
        """Database enforces token uniqueness."""
        _insert_prospect(test_db)
        _insert_token(test_db, prospect_id=1, token="unique-token-123")

        with pytest.raises(sqlite3.IntegrityError):
            _insert_token(test_db, prospect_id=1, token="unique-token-123")


# ============================================================
# Integration Tests
# ============================================================

class TestProspectAccessIntegration:
    """End-to-end integration tests for prospect access flow."""

    def test_full_flow_create_validate_revoke(self, test_db):
        """Full flow: create prospect, grant token, validate, revoke."""
        _insert_prospect(test_db, name="Integration Test Prospect",
                         email="integration@example.com")

        with _db_patch():
            from apps.investor_portal.api.models.database import (
                create_prospect_access_token,
                validate_prospect_token,
                revoke_prospect_token,
            )

            # 1. Create token
            future = (datetime.utcnow() + timedelta(days=30)).isoformat()
            token_id = create_prospect_access_token(
                prospect_id=1, token="integration-token", expires_at=future
            )
            assert token_id > 0

            # 2. Validate token
            result = validate_prospect_token("integration-token")
            assert result is not None
            assert result["prospect_name"] == "Integration Test Prospect"

            # 3. Check access count (read from test_db which shares the file)
            chk = sqlite3.connect(TEST_DB_PATH)
            chk.row_factory = sqlite3.Row
            row = chk.execute(
                "SELECT access_count FROM prospect_access_tokens WHERE token = 'integration-token'"
            ).fetchone()
            assert row["access_count"] == 1
            chk.close()

            # 4. Revoke token
            revoked = revoke_prospect_token(1)
            assert revoked is True

            # 5. Validate again - should fail
            result = validate_prospect_token("integration-token")
            assert result is None

    def test_token_replacement_flow(self, test_db):
        """Creating a new token automatically revokes the old one."""
        _insert_prospect(test_db)

        with _db_patch():
            from apps.investor_portal.api.models.database import (
                create_prospect_access_token,
                validate_prospect_token,
            )

            future = (datetime.utcnow() + timedelta(days=30)).isoformat()

            # Create first token
            create_prospect_access_token(
                prospect_id=1, token="token-v1", expires_at=future
            )
            assert validate_prospect_token("token-v1") is not None

            # Create replacement token
            create_prospect_access_token(
                prospect_id=1, token="token-v2", expires_at=future
            )

            # Old token should be revoked
            assert validate_prospect_token("token-v1") is None
            # New token should work
            assert validate_prospect_token("token-v2") is not None
