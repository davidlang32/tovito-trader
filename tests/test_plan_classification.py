"""
Tests for Plan Classification (Phase 2)
==========================================

Tests plan classification logic, plan performance computation,
plan API endpoints, and sync integration.
"""

import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import date, timedelta


# The test_db fixture yields a Connection; we need the PATH for patching
TEST_DB_PATH = "data/test_tovito.db"


# ============================================================
# Classification Logic Tests
# ============================================================

class TestClassifyPosition:
    """Test the classify_position function."""

    def test_cash_instrument_type(self):
        """Cash instrument type always returns plan_cash."""
        from src.plans.classification import classify_position

        assert classify_position("anything", "Cash") == "plan_cash"
        assert classify_position("AAPL", "money-market") == "plan_cash"
        assert classify_position("XYZ", "Sweep") == "plan_cash"

    def test_sgov_equity(self):
        """SGOV as equity is plan_cash."""
        from src.plans.classification import classify_position

        assert classify_position("SGOV", "Equity") == "plan_cash"

    def test_bil_equity(self):
        """BIL as equity is plan_cash."""
        from src.plans.classification import classify_position

        assert classify_position("BIL", "Equity") == "plan_cash"

    def test_vmfxx(self):
        """VMFXX (money market fund) is plan_cash."""
        from src.plans.classification import classify_position

        assert classify_position("VMFXX") == "plan_cash"

    def test_spy_equity(self):
        """SPY as equity is plan_etf."""
        from src.plans.classification import classify_position

        assert classify_position("SPY", "Equity") == "plan_etf"

    def test_qqq_equity(self):
        """QQQ as equity is plan_etf."""
        from src.plans.classification import classify_position

        assert classify_position("QQQ", "Equity") == "plan_etf"

    def test_spxl_equity(self):
        """SPXL (leveraged ETF) as equity is plan_etf."""
        from src.plans.classification import classify_position

        assert classify_position("SPXL", "Equity") == "plan_etf"

    def test_tqqq_equity(self):
        """TQQQ (leveraged ETF) as equity is plan_etf."""
        from src.plans.classification import classify_position

        assert classify_position("TQQQ", "Equity") == "plan_etf"

    def test_iwm_equity(self):
        """IWM as equity is plan_etf."""
        from src.plans.classification import classify_position

        assert classify_position("IWM", "Equity") == "plan_etf"

    def test_spy_option_is_plan_a(self):
        """SPY options go to plan_a (not plan_etf)."""
        from src.plans.classification import classify_position

        assert classify_position("SPY", "Option") == "plan_a"
        assert classify_position("SPY", "Options") == "plan_a"

    def test_qqq_option_is_plan_a(self):
        """QQQ options go to plan_a."""
        from src.plans.classification import classify_position

        assert classify_position("QQQ", "Option") == "plan_a"

    def test_individual_stock_option(self):
        """Individual stock options are plan_a."""
        from src.plans.classification import classify_position

        assert classify_position("AAPL", "Option") == "plan_a"
        assert classify_position("NVDA", "Option") == "plan_a"

    def test_unknown_symbol_is_plan_a(self):
        """Unknown symbols default to plan_a."""
        from src.plans.classification import classify_position

        assert classify_position("RANDOM", "Equity") == "plan_a"
        assert classify_position("XYZ") == "plan_a"

    def test_option_symbol_with_space(self):
        """Option symbols with space (e.g., 'SPY 250321C500') use root ticker."""
        from src.plans.classification import classify_position

        # Root ticker extraction: 'SPY 250321C500' -> 'SPY'
        # But without instrument_type=Option, SPY root goes to plan_etf
        assert classify_position("SPY 250321C500") == "plan_etf"

        # With option instrument type, it goes to plan_a
        assert classify_position("SPY 250321C500", "Option") == "plan_a"

    def test_case_insensitive_symbol(self):
        """Symbols are normalized to uppercase."""
        from src.plans.classification import classify_position

        assert classify_position("sgov") == "plan_cash"
        assert classify_position("spy", "Equity") == "plan_etf"

    def test_empty_symbol(self):
        """Empty symbol returns plan_a."""
        from src.plans.classification import classify_position

        assert classify_position("") == "plan_a"
        assert classify_position("", "Equity") == "plan_a"

    def test_none_instrument_type(self):
        """None instrument_type is handled correctly."""
        from src.plans.classification import classify_position

        assert classify_position("SGOV", None) == "plan_cash"
        assert classify_position("SPY", None) == "plan_etf"
        assert classify_position("AAPL", None) == "plan_a"


class TestClassifyPositionByUnderlying:
    """Test classify_position_by_underlying for options with underlying."""

    def test_uses_underlying_symbol(self):
        """Uses underlying symbol when available."""
        from src.plans.classification import classify_position_by_underlying

        # Full option symbol with SPY underlying
        result = classify_position_by_underlying(
            symbol="SPY 250321C00500000",
            underlying_symbol="SPY",
            instrument_type="Option",
        )
        assert result == "plan_a"  # Options on SPY are plan_a

    def test_etf_underlying_equity(self):
        """ETF underlying with equity type goes to plan_etf."""
        from src.plans.classification import classify_position_by_underlying

        result = classify_position_by_underlying(
            symbol="SPY",
            underlying_symbol="SPY",
            instrument_type="Equity",
        )
        assert result == "plan_etf"

    def test_cash_underlying(self):
        """Cash underlying returns plan_cash."""
        from src.plans.classification import classify_position_by_underlying

        result = classify_position_by_underlying(
            symbol="SGOV",
            underlying_symbol="SGOV",
            instrument_type="Equity",
        )
        assert result == "plan_cash"

    def test_fallback_to_symbol(self):
        """Falls back to symbol when underlying is None."""
        from src.plans.classification import classify_position_by_underlying

        result = classify_position_by_underlying(
            symbol="SGOV",
            underlying_symbol=None,
            instrument_type="Equity",
        )
        assert result == "plan_cash"


class TestPlanMetadata:
    """Test plan metadata functions."""

    def test_plan_ids_constant(self):
        """PLAN_IDS contains exactly three plan identifiers."""
        from src.plans.classification import PLAN_IDS

        assert len(PLAN_IDS) == 3
        assert "plan_cash" in PLAN_IDS
        assert "plan_etf" in PLAN_IDS
        assert "plan_a" in PLAN_IDS

    def test_get_plan_metadata_cash(self):
        """Plan CASH metadata has correct fields."""
        from src.plans.classification import get_plan_metadata

        meta = get_plan_metadata("plan_cash")
        assert meta["name"] == "Plan CASH"
        assert "Conservative" in meta["risk_level"]

    def test_get_plan_metadata_etf(self):
        """Plan ETF metadata has correct fields."""
        from src.plans.classification import get_plan_metadata

        meta = get_plan_metadata("plan_etf")
        assert meta["name"] == "Plan ETF"
        assert "Moderate" in meta["risk_level"]

    def test_get_plan_metadata_a(self):
        """Plan A metadata has correct fields."""
        from src.plans.classification import get_plan_metadata

        meta = get_plan_metadata("plan_a")
        assert meta["name"] == "Plan A"
        assert "Aggressive" in meta["risk_level"]

    def test_get_plan_metadata_unknown(self):
        """Unknown plan_id returns fallback metadata."""
        from src.plans.classification import get_plan_metadata

        meta = get_plan_metadata("plan_xyz")
        assert meta["name"] == "plan_xyz"
        assert meta["risk_level"] == "Unknown"


# ============================================================
# Plan Performance Computation Tests
# ============================================================

class TestComputePlanPerformance:
    """Test compute_plan_performance aggregation."""

    def test_single_cash_position(self):
        """Single SGOV position aggregates to plan_cash."""
        from src.plans.classification import compute_plan_performance

        positions = [
            {
                "symbol": "SGOV",
                "instrument_type": "Equity",
                "quantity": 100,
                "market_value": 10050.0,
                "cost_basis": 10000.0,
                "unrealized_pl": 50.0,
            }
        ]
        result = compute_plan_performance(positions)

        assert "plan_cash" in result
        assert result["plan_cash"]["market_value"] == 10050.0
        assert result["plan_cash"]["cost_basis"] == 10000.0
        assert result["plan_cash"]["unrealized_pl"] == 50.0
        assert result["plan_cash"]["position_count"] == 1
        assert result["plan_cash"]["allocation_pct"] == 100.0

    def test_mixed_plans(self):
        """Multiple positions across different plans aggregate correctly."""
        from src.plans.classification import compute_plan_performance

        positions = [
            {
                "symbol": "SGOV",
                "instrument_type": "Equity",
                "quantity": 100,
                "market_value": 5000.0,
                "cost_basis": 5000.0,
                "unrealized_pl": 0.0,
            },
            {
                "symbol": "SPY",
                "instrument_type": "Equity",
                "quantity": 10,
                "market_value": 3000.0,
                "cost_basis": 2800.0,
                "unrealized_pl": 200.0,
            },
            {
                "symbol": "AAPL 250321C200",
                "underlying_symbol": "AAPL",
                "instrument_type": "Option",
                "quantity": 5,
                "market_value": 2000.0,
                "cost_basis": 1500.0,
                "unrealized_pl": 500.0,
            },
        ]
        result = compute_plan_performance(positions)

        # Total = 5000 + 3000 + 2000 = 10000
        assert "plan_cash" in result
        assert "plan_etf" in result
        assert "plan_a" in result

        assert result["plan_cash"]["market_value"] == 5000.0
        assert result["plan_cash"]["allocation_pct"] == 50.0

        assert result["plan_etf"]["market_value"] == 3000.0
        assert result["plan_etf"]["allocation_pct"] == 30.0

        assert result["plan_a"]["market_value"] == 2000.0
        assert result["plan_a"]["allocation_pct"] == 20.0

    def test_empty_positions(self):
        """Empty positions list returns empty dict."""
        from src.plans.classification import compute_plan_performance

        result = compute_plan_performance([])
        assert result == {}

    def test_zero_market_value(self):
        """Zero total market value produces 0% allocations."""
        from src.plans.classification import compute_plan_performance

        positions = [
            {
                "symbol": "SGOV",
                "instrument_type": "Equity",
                "quantity": 0,
                "market_value": 0.0,
                "cost_basis": 0.0,
                "unrealized_pl": 0.0,
            }
        ]
        result = compute_plan_performance(positions)
        assert result["plan_cash"]["allocation_pct"] == 0.0

    def test_spy_option_goes_to_plan_a(self):
        """SPY options are classified under plan_a, not plan_etf."""
        from src.plans.classification import compute_plan_performance

        positions = [
            {
                "symbol": "SPY 250321C500",
                "underlying_symbol": "SPY",
                "instrument_type": "Option",
                "quantity": 5,
                "market_value": 5000.0,
                "cost_basis": 4000.0,
                "unrealized_pl": 1000.0,
            },
            {
                "symbol": "SPY",
                "instrument_type": "Equity",
                "quantity": 10,
                "market_value": 5000.0,
                "cost_basis": 4500.0,
                "unrealized_pl": 500.0,
            },
        ]
        result = compute_plan_performance(positions)

        # SPY equity -> plan_etf, SPY option -> plan_a
        assert "plan_etf" in result
        assert "plan_a" in result
        assert result["plan_etf"]["market_value"] == 5000.0
        assert result["plan_a"]["market_value"] == 5000.0

    def test_values_are_rounded(self):
        """Financial values are rounded to 2 decimal places."""
        from src.plans.classification import compute_plan_performance

        positions = [
            {
                "symbol": "SGOV",
                "instrument_type": "Equity",
                "quantity": 1,
                "market_value": 100.333,
                "cost_basis": 99.666,
                "unrealized_pl": 0.667,
            }
        ]
        result = compute_plan_performance(positions)
        assert result["plan_cash"]["market_value"] == 100.33
        assert result["plan_cash"]["cost_basis"] == 99.67
        assert result["plan_cash"]["unrealized_pl"] == 0.67

    def test_symbols_tracked(self):
        """Position symbols are collected in the result."""
        from src.plans.classification import compute_plan_performance

        positions = [
            {
                "symbol": "SGOV",
                "instrument_type": "Equity",
                "quantity": 100,
                "market_value": 5000.0,
                "cost_basis": 5000.0,
                "unrealized_pl": 0.0,
            },
            {
                "symbol": "BIL",
                "instrument_type": "Equity",
                "quantity": 50,
                "market_value": 2500.0,
                "cost_basis": 2500.0,
                "unrealized_pl": 0.0,
            },
        ]
        result = compute_plan_performance(positions)
        assert "SGOV" in result["plan_cash"]["symbols"]
        assert "BIL" in result["plan_cash"]["symbols"]


# ============================================================
# Upsert Plan Performance Tests
# ============================================================

class TestUpsertPlanPerformance:
    """Test upsert_plan_performance database function."""

    def test_insert_plan_performance(self, test_db):
        """Insert plan performance records."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import upsert_plan_performance

            rows = [
                {
                    "date": "2026-03-01",
                    "plan_id": "plan_cash",
                    "market_value": 5000.0,
                    "cost_basis": 5000.0,
                    "unrealized_pl": 0.0,
                    "allocation_pct": 50.0,
                    "position_count": 1,
                },
                {
                    "date": "2026-03-01",
                    "plan_id": "plan_etf",
                    "market_value": 3000.0,
                    "cost_basis": 2800.0,
                    "unrealized_pl": 200.0,
                    "allocation_pct": 30.0,
                    "position_count": 2,
                },
                {
                    "date": "2026-03-01",
                    "plan_id": "plan_a",
                    "market_value": 2000.0,
                    "cost_basis": 1500.0,
                    "unrealized_pl": 500.0,
                    "allocation_pct": 20.0,
                    "position_count": 3,
                },
            ]
            count = upsert_plan_performance(rows)
            assert count == 3

            # Verify in database
            cursor = test_db.cursor()
            cursor.execute("SELECT * FROM plan_daily_performance WHERE date = '2026-03-01'")
            records = cursor.fetchall()
            assert len(records) == 3

    def test_upsert_replaces_existing(self, test_db):
        """Re-inserting same date+plan_id replaces the record."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import upsert_plan_performance

            rows = [
                {
                    "date": "2026-03-01",
                    "plan_id": "plan_cash",
                    "market_value": 5000.0,
                    "cost_basis": 5000.0,
                    "unrealized_pl": 0.0,
                    "allocation_pct": 50.0,
                    "position_count": 1,
                },
            ]
            upsert_plan_performance(rows)

            # Update values
            rows[0]["market_value"] = 6000.0
            rows[0]["allocation_pct"] = 60.0
            upsert_plan_performance(rows)

            cursor = test_db.cursor()
            cursor.execute("""
                SELECT * FROM plan_daily_performance
                WHERE date = '2026-03-01' AND plan_id = 'plan_cash'
            """)
            records = cursor.fetchall()
            assert len(records) == 1
            assert records[0]["market_value"] == 6000.0
            assert records[0]["allocation_pct"] == 60.0

    def test_empty_rows(self, test_db):
        """Empty rows list returns 0."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import upsert_plan_performance

            count = upsert_plan_performance([])
            assert count == 0


# ============================================================
# Sync Payload Tests (plan_performance in sync)
# ============================================================

class TestSyncPlanPerformance:
    """Test plan performance inclusion in sync pipeline."""

    def _seed_plan_data(self, conn):
        """Seed plan performance data in local test database."""
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO plan_daily_performance
                (date, plan_id, market_value, cost_basis, unrealized_pl,
                 allocation_pct, position_count)
            VALUES
                ('2026-03-01', 'plan_cash', 5000.0, 5000.0, 0.0, 50.0, 1),
                ('2026-03-01', 'plan_etf', 3000.0, 2800.0, 200.0, 30.0, 2),
                ('2026-03-01', 'plan_a', 2000.0, 1500.0, 500.0, 20.0, 3)
        """)
        conn.commit()

    def test_collect_plan_performance(self, test_db):
        """Collect plan performance from local database."""
        self._seed_plan_data(test_db)

        with patch("scripts.sync_to_production.DB_PATH", Path(TEST_DB_PATH)):
            from scripts.sync_to_production import collect_plan_performance

            records = collect_plan_performance("2026-03-01")
            assert len(records) == 3

            plan_ids = {r["plan_id"] for r in records}
            assert plan_ids == {"plan_cash", "plan_etf", "plan_a"}

    def test_collect_plan_performance_missing_date(self, test_db):
        """Missing date returns empty list."""
        with patch("scripts.sync_to_production.DB_PATH", Path(TEST_DB_PATH)):
            from scripts.sync_to_production import collect_plan_performance

            records = collect_plan_performance("2099-01-01")
            assert records == []

    def test_plan_performance_in_sync_payload(self, test_db):
        """Plan performance is included in build_sync_payload."""
        self._seed_plan_data(test_db)

        # Also seed NAV data so build_sync_payload has a date with data
        cursor = test_db.cursor()
        cursor.execute("""
            INSERT INTO daily_nav (date, nav_per_share, total_portfolio_value,
                                   total_shares, daily_change_dollars,
                                   daily_change_percent, created_at)
            VALUES ('2026-03-01', 10.5, 21000.0, 2000.0, 50.0, 0.24, datetime('now'))
        """)
        test_db.commit()

        with patch("scripts.sync_to_production.DB_PATH", Path(TEST_DB_PATH)):
            from scripts.sync_to_production import build_sync_payload

            payload = build_sync_payload("2026-03-01", lookback_days=0)
            assert "plan_performance" in payload
            assert len(payload["plan_performance"]) == 3


class TestSyncPayloadWithPlanPerformance:
    """Test Pydantic model validation with plan_performance."""

    def test_payload_with_plan_performance(self):
        """SyncPayload accepts plan_performance field."""
        from apps.investor_portal.api.routes.admin import SyncPayload

        payload = SyncPayload(
            plan_performance=[
                {
                    "date": "2026-03-01",
                    "plan_id": "plan_cash",
                    "market_value": 5000.0,
                    "cost_basis": 5000.0,
                    "unrealized_pl": 0.0,
                    "allocation_pct": 50.0,
                    "position_count": 1,
                },
                {
                    "date": "2026-03-01",
                    "plan_id": "plan_etf",
                    "market_value": 3000.0,
                    "cost_basis": 2800.0,
                    "unrealized_pl": 200.0,
                    "allocation_pct": 30.0,
                    "position_count": 2,
                },
            ],
        )
        assert len(payload.plan_performance) == 2
        assert payload.plan_performance[0].plan_id == "plan_cash"
        assert payload.plan_performance[1].allocation_pct == 30.0

    def test_empty_plan_performance_default(self):
        """Empty SyncPayload has empty plan_performance list."""
        from apps.investor_portal.api.routes.admin import SyncPayload

        payload = SyncPayload()
        assert payload.plan_performance == []


# ============================================================
# Plan Analysis Endpoint Tests
# ============================================================

class TestPlanAllocationEndpoint:
    """Test /analysis/plan-allocation endpoint logic."""

    def _seed_plan_data_for_api(self, conn):
        """Seed plan performance data for API tests."""
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO plan_daily_performance
                (date, plan_id, market_value, cost_basis, unrealized_pl,
                 allocation_pct, position_count)
            VALUES
                ('2026-02-25', 'plan_cash', 5000.0, 5000.0, 0.0, 50.0, 1),
                ('2026-02-25', 'plan_etf', 3000.0, 2800.0, 200.0, 30.0, 2),
                ('2026-02-25', 'plan_a', 2000.0, 1500.0, 500.0, 20.0, 3)
        """)
        conn.commit()

    def test_plan_allocation_returns_data(self, test_db):
        """Plan allocation endpoint returns plan data."""
        self._seed_plan_data_for_api(test_db)

        with patch("apps.investor_portal.api.routes.analysis.get_connection") as mock_conn:
            mock_conn.return_value = test_db

            import asyncio
            from apps.investor_portal.api.routes.analysis import get_plan_allocation

            # Mock user
            mock_user = MagicMock()
            mock_user.investor_id = "20260101-01A"

            result = asyncio.run(get_plan_allocation(user=mock_user))

            assert result.as_of_date == "2026-02-25"
            assert len(result.plans) == 3
            assert result.total_market_value == 10000.0

            plan_ids = {p.plan_id for p in result.plans}
            assert plan_ids == {"plan_cash", "plan_etf", "plan_a"}

    def test_plan_allocation_empty(self, test_db):
        """Plan allocation returns empty when no data."""
        with patch("apps.investor_portal.api.routes.analysis.get_connection") as mock_conn:
            mock_conn.return_value = test_db

            import asyncio
            from apps.investor_portal.api.routes.analysis import get_plan_allocation

            mock_user = MagicMock()
            mock_user.investor_id = "20260101-01A"

            result = asyncio.run(get_plan_allocation(user=mock_user))
            assert result.as_of_date == ""
            assert result.plans == []
            assert result.total_market_value == 0.0


class TestPlanPerformanceEndpoint:
    """Test /analysis/plan-performance endpoint logic."""

    def _seed_time_series(self, conn):
        """Seed multiple days of plan performance data."""
        cursor = conn.cursor()
        for i in range(10):
            d = (date(2026, 2, 15) + timedelta(days=i)).isoformat()
            cursor.execute("""
                INSERT INTO plan_daily_performance
                    (date, plan_id, market_value, cost_basis, unrealized_pl,
                     allocation_pct, position_count)
                VALUES
                    (?, 'plan_cash', ?, 5000.0, 0.0, 50.0, 1),
                    (?, 'plan_etf', ?, 2800.0, 200.0, 30.0, 2),
                    (?, 'plan_a', ?, 1500.0, 500.0, 20.0, 3)
            """, (d, 5000.0 + i * 10, d, 3000.0 + i * 5, d, 2000.0 + i * 20))
        conn.commit()

    def test_plan_performance_time_series(self, test_db):
        """Plan performance endpoint returns time series grouped by plan."""
        self._seed_time_series(test_db)

        with patch("apps.investor_portal.api.routes.analysis.get_connection") as mock_conn:
            mock_conn.return_value = test_db

            import asyncio
            from apps.investor_portal.api.routes.analysis import get_plan_performance

            mock_user = MagicMock()
            mock_user.investor_id = "20260101-01A"

            result = asyncio.run(get_plan_performance(user=mock_user, days=30))

            assert result.days == 30
            assert "plan_cash" in result.series
            assert "plan_etf" in result.series
            assert "plan_a" in result.series

            # Should have 10 data points per plan
            assert len(result.series["plan_cash"]) == 10
            assert len(result.series["plan_etf"]) == 10
            assert len(result.series["plan_a"]) == 10

    def test_plan_performance_empty(self, test_db):
        """Plan performance returns empty series when no data."""
        with patch("apps.investor_portal.api.routes.analysis.get_connection") as mock_conn:
            mock_conn.return_value = test_db

            import asyncio
            from apps.investor_portal.api.routes.analysis import get_plan_performance

            mock_user = MagicMock()
            mock_user.investor_id = "20260101-01A"

            result = asyncio.run(get_plan_performance(user=mock_user, days=90))
            assert result.series == {}


# ============================================================
# Sync Endpoint Integration with Plan Performance
# ============================================================

class TestSyncEndpointPlanPerformance:
    """Test that /admin/sync writes plan performance to database."""

    def test_sync_writes_plan_performance(self, test_db):
        """Sync endpoint upserts plan performance data."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import upsert_plan_performance

            rows = [
                {
                    "date": "2026-03-15",
                    "plan_id": "plan_cash",
                    "market_value": 5500.0,
                    "cost_basis": 5000.0,
                    "unrealized_pl": 500.0,
                    "allocation_pct": 55.0,
                    "position_count": 2,
                },
                {
                    "date": "2026-03-15",
                    "plan_id": "plan_a",
                    "market_value": 4500.0,
                    "cost_basis": 3000.0,
                    "unrealized_pl": 1500.0,
                    "allocation_pct": 45.0,
                    "position_count": 5,
                },
            ]
            count = upsert_plan_performance(rows)
            assert count == 2

            # Verify
            cursor = test_db.cursor()
            cursor.execute("""
                SELECT * FROM plan_daily_performance
                WHERE date = '2026-03-15'
                ORDER BY allocation_pct DESC
            """)
            records = cursor.fetchall()
            assert len(records) == 2
            assert records[0]["plan_id"] == "plan_cash"
            assert records[0]["market_value"] == 5500.0
            assert records[1]["plan_id"] == "plan_a"
            assert records[1]["market_value"] == 4500.0

    def test_sync_idempotent_plan_performance(self, test_db):
        """Re-syncing plan performance is idempotent."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import upsert_plan_performance

            rows = [
                {
                    "date": "2026-03-20",
                    "plan_id": "plan_etf",
                    "market_value": 3000.0,
                    "cost_basis": 2800.0,
                    "unrealized_pl": 200.0,
                    "allocation_pct": 30.0,
                    "position_count": 2,
                },
            ]
            upsert_plan_performance(rows)
            upsert_plan_performance(rows)  # Second time

            cursor = test_db.cursor()
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM plan_daily_performance
                WHERE date = '2026-03-20' AND plan_id = 'plan_etf'
            """)
            assert cursor.fetchone()["cnt"] == 1
