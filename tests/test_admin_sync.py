"""
Tests for Admin Sync (Phase 1)
=================================

Tests admin API key authentication, sync endpoint,
and database upsert functions.
"""

import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


# The test_db fixture yields a Connection; we need the PATH for patching
TEST_DB_PATH = "data/test_tovito.db"


# ============================================================
# Admin Key Authentication Tests
# ============================================================

class TestVerifyAdminKey:
    """Test the verify_admin_key dependency."""

    def test_valid_key(self):
        """Valid admin key returns True."""
        from apps.investor_portal.api.dependencies import verify_admin_key
        import asyncio

        with patch("apps.investor_portal.api.dependencies.settings") as mock_settings:
            mock_settings.ADMIN_API_KEY = "test-secret-key-12345"
            result = asyncio.run(verify_admin_key("test-secret-key-12345"))
            assert result is True

    def test_invalid_key(self):
        """Wrong admin key raises 403."""
        from apps.investor_portal.api.dependencies import verify_admin_key
        from fastapi import HTTPException
        import asyncio

        with patch("apps.investor_portal.api.dependencies.settings") as mock_settings:
            mock_settings.ADMIN_API_KEY = "correct-key"
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(verify_admin_key("wrong-key"))
            assert exc_info.value.status_code == 403

    def test_empty_key_configured(self):
        """Empty admin key setting returns 503 (not configured)."""
        from apps.investor_portal.api.dependencies import verify_admin_key
        from fastapi import HTTPException
        import asyncio

        with patch("apps.investor_portal.api.dependencies.settings") as mock_settings:
            mock_settings.ADMIN_API_KEY = ""
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(verify_admin_key("any-key"))
            assert exc_info.value.status_code == 503

    def test_missing_header_raises_422(self):
        """Missing X-Admin-Key header would raise 422 (FastAPI validation).
        This test verifies our dependency has the correct signature."""
        from apps.investor_portal.api.dependencies import verify_admin_key
        import inspect

        sig = inspect.signature(verify_admin_key)
        params = list(sig.parameters.keys())
        assert "x_admin_key" in params


# ============================================================
# Database Upsert Functions Tests
# ============================================================

class TestUpsertDailyNav:
    """Test upsert_daily_nav function."""

    def test_insert_new_nav(self, test_db):
        """Insert a new daily NAV record."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import upsert_daily_nav

            row = {
                "date": "2026-03-01",
                "nav_per_share": 10.5000,
                "total_portfolio_value": 21000.00,
                "total_shares": 2000.0000,
                "daily_change_dollars": 50.00,
                "daily_change_percent": 0.24,
            }
            result = upsert_daily_nav(row)
            assert result is True

            # Verify in database using the test_db connection
            cursor = test_db.cursor()
            cursor.execute("SELECT * FROM daily_nav WHERE date = '2026-03-01'")
            record = cursor.fetchone()

            assert record is not None
            assert record["nav_per_share"] == 10.5000
            assert record["total_portfolio_value"] == 21000.00

    def test_upsert_existing_nav(self, test_db):
        """Upserting same date updates the record."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import upsert_daily_nav

            row = {
                "date": "2026-03-01",
                "nav_per_share": 10.5000,
                "total_portfolio_value": 21000.00,
                "total_shares": 2000.0000,
            }
            upsert_daily_nav(row)

            # Update with new values
            row["nav_per_share"] = 10.6000
            row["total_portfolio_value"] = 21200.00
            upsert_daily_nav(row)

            # Should have only 1 record with updated values
            cursor = test_db.cursor()
            cursor.execute("SELECT * FROM daily_nav WHERE date = '2026-03-01'")
            records = cursor.fetchall()

            assert len(records) == 1
            assert records[0]["nav_per_share"] == 10.6000


class TestUpsertHoldingsSnapshot:
    """Test upsert_holdings_snapshot function."""

    def test_insert_snapshot_with_positions(self, test_db):
        """Insert a holdings snapshot with multiple positions."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import upsert_holdings_snapshot

            header = {
                "date": "2026-03-01",
                "source": "tastytrade",
                "snapshot_time": "2026-03-01T16:05:00",
                "total_positions": 2,
            }
            positions = [
                {
                    "symbol": "SGOV",
                    "quantity": 100.0,
                    "instrument_type": "Equity",
                    "market_value": 10050.00,
                    "cost_basis": 10000.00,
                    "unrealized_pl": 50.00,
                },
                {
                    "symbol": "SPY 500C 2026-04-17",
                    "underlying_symbol": "SPY",
                    "quantity": 5.0,
                    "instrument_type": "Option",
                    "market_value": 5000.00,
                    "cost_basis": 4500.00,
                    "unrealized_pl": 500.00,
                    "option_type": "call",
                    "strike": 500.0,
                    "expiration_date": "2026-04-17",
                    "multiplier": 100,
                },
            ]
            snapshot_id = upsert_holdings_snapshot(header, positions)
            assert snapshot_id > 0

            # Verify positions
            cursor = test_db.cursor()
            cursor.execute(
                "SELECT * FROM position_snapshots WHERE snapshot_id = ?",
                (snapshot_id,)
            )
            records = cursor.fetchall()

            assert len(records) == 2
            symbols = {r["symbol"] for r in records}
            assert "SGOV" in symbols
            assert "SPY 500C 2026-04-17" in symbols

    def test_upsert_snapshot_replaces_positions(self, test_db):
        """Re-inserting same date/source replaces positions."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import upsert_holdings_snapshot

            header = {"date": "2026-03-01", "source": "tastytrade"}
            positions_v1 = [
                {"symbol": "SGOV", "quantity": 100.0},
                {"symbol": "SPY", "quantity": 50.0},
            ]
            snapshot_id = upsert_holdings_snapshot(header, positions_v1)

            # Re-insert with different positions
            positions_v2 = [
                {"symbol": "QQQ", "quantity": 30.0},
            ]
            snapshot_id_2 = upsert_holdings_snapshot(header, positions_v2)

            # Same snapshot_id should be reused
            assert snapshot_id == snapshot_id_2

            # Only the new positions should exist
            cursor = test_db.cursor()
            cursor.execute(
                "SELECT * FROM position_snapshots WHERE snapshot_id = ?",
                (snapshot_id,)
            )
            records = cursor.fetchall()

            assert len(records) == 1
            assert records[0]["symbol"] == "QQQ"


class TestUpsertTrades:
    """Test upsert_trades function."""

    def test_insert_new_trades(self, test_db):
        """Insert new trades."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import upsert_trades

            trades = [
                {
                    "date": "2026-03-01",
                    "trade_type": "buy",
                    "symbol": "SPY",
                    "quantity": 10.0,
                    "price": 500.0,
                    "amount": -5000.0,
                    "category": "Trade",
                    "subcategory": "Stock Buy",
                    "source": "tastytrade",
                    "brokerage_transaction_id": "TT-12345",
                },
            ]
            result = upsert_trades(trades)
            assert result["inserted"] == 1
            assert result["skipped"] == 0

    def test_skip_duplicate_trades(self, test_db):
        """Trades with same source+brokerage_txn_id are skipped."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import upsert_trades

            trades = [
                {
                    "date": "2026-03-01",
                    "trade_type": "buy",
                    "symbol": "SPY",
                    "quantity": 10.0,
                    "price": 500.0,
                    "amount": -5000.0,
                    "source": "tastytrade",
                    "brokerage_transaction_id": "TT-99999",
                },
            ]
            # First insert
            result1 = upsert_trades(trades)
            assert result1["inserted"] == 1

            # Second insert — same brokerage_transaction_id
            result2 = upsert_trades(trades)
            assert result2["inserted"] == 0
            assert result2["skipped"] == 1

    def test_insert_trade_without_brokerage_id(self, test_db):
        """Trades without brokerage_transaction_id always insert."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import upsert_trades

            trades = [
                {
                    "date": "2026-03-01",
                    "trade_type": "interest",
                    "amount": 1.50,
                    "source": "tastytrade",
                },
            ]
            result1 = upsert_trades(trades)
            assert result1["inserted"] == 1

            result2 = upsert_trades(trades)
            assert result2["inserted"] == 1  # No dedup without brokerage_id


class TestUpsertBenchmarkPrices:
    """Test upsert_benchmark_prices function."""

    def test_insert_benchmark_prices(self, test_db):
        """Insert benchmark prices."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import upsert_benchmark_prices

            prices = [
                {"date": "2026-03-01", "ticker": "SPY", "close_price": 500.25},
                {"date": "2026-03-01", "ticker": "QQQ", "close_price": 450.50},
                {"date": "2026-03-01", "ticker": "BTC-USD", "close_price": 85000.00},
            ]
            inserted = upsert_benchmark_prices(prices)
            assert inserted == 3

    def test_ignore_duplicate_prices(self, test_db):
        """Duplicate date+ticker combos are ignored."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import upsert_benchmark_prices

            prices = [
                {"date": "2026-03-01", "ticker": "SPY", "close_price": 500.25},
            ]
            inserted1 = upsert_benchmark_prices(prices)
            assert inserted1 == 1

            inserted2 = upsert_benchmark_prices(prices)
            assert inserted2 == 0  # Already exists


class TestUpsertReconciliation:
    """Test upsert_reconciliation function."""

    def test_insert_reconciliation(self, test_db):
        """Insert a reconciliation record."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import upsert_reconciliation

            row = {
                "date": "2026-03-01",
                "tradier_balance": 21000.00,
                "calculated_portfolio_value": 21000.00,
                "difference": 0.00,
                "total_shares": 2000.0,
                "nav_per_share": 10.5,
                "status": "matched",
                "notes": None,
            }
            result = upsert_reconciliation(row)
            assert result is True

    def test_upsert_reconciliation_replaces(self, test_db):
        """Re-inserting same date replaces the record."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import upsert_reconciliation

            row = {
                "date": "2026-03-01",
                "tradier_balance": 21000.00,
                "status": "matched",
            }
            upsert_reconciliation(row)

            row["status"] = "mismatch"
            row["notes"] = "Balance discrepancy"
            upsert_reconciliation(row)

            cursor = test_db.cursor()
            cursor.execute(
                "SELECT * FROM daily_reconciliation WHERE date = '2026-03-01'"
            )
            records = cursor.fetchall()

            assert len(records) == 1
            assert records[0]["status"] == "mismatch"


# ============================================================
# Sync Payload Assembly Tests
# ============================================================

class TestSyncPayloadAssembly:
    """Test sync_to_production.py payload collection functions."""

    def _seed_test_data(self, conn):
        """Seed the test database with sample pipeline data."""
        cursor = conn.cursor()

        # NAV
        cursor.execute("""
            INSERT INTO daily_nav (date, nav_per_share, total_portfolio_value,
                                   total_shares, daily_change_dollars, daily_change_percent,
                                   created_at)
            VALUES ('2026-03-01', 10.5, 21000.0, 2000.0, 50.0, 0.24, datetime('now'))
        """)

        # Holdings snapshot
        cursor.execute("""
            INSERT INTO holdings_snapshots (date, source, snapshot_time, total_positions)
            VALUES ('2026-03-01', 'tastytrade', '2026-03-01T16:05:00', 1)
        """)
        snapshot_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO position_snapshots (snapshot_id, symbol, quantity, instrument_type,
                                            market_value, cost_basis, unrealized_pl)
            VALUES (?, 'SGOV', 100.0, 'Equity', 10050.0, 10000.0, 50.0)
        """, (snapshot_id,))

        # Trade
        cursor.execute("""
            INSERT INTO trades (date, trade_type, symbol, quantity, price, amount,
                                category, subcategory, source, brokerage_transaction_id)
            VALUES ('2026-03-01', 'buy', 'SGOV', 100, 100.5, -10050.0,
                    'Trade', 'Stock Buy', 'tastytrade', 'TT-SEED-001')
        """)

        # Benchmark
        cursor.execute("""
            INSERT INTO benchmark_prices (date, ticker, close_price)
            VALUES ('2026-03-01', 'SPY', 500.25)
        """)

        # Reconciliation
        cursor.execute("""
            INSERT INTO daily_reconciliation (date, tradier_balance,
                    calculated_portfolio_value, difference, status)
            VALUES ('2026-03-01', 21000.0, 21000.0, 0.0, 'matched')
        """)

        conn.commit()

    def test_collect_daily_nav(self, test_db):
        """Collect daily NAV from local database."""
        self._seed_test_data(test_db)

        with patch("scripts.sync_to_production.DB_PATH", Path(TEST_DB_PATH)):
            from scripts.sync_to_production import collect_daily_nav

            nav = collect_daily_nav("2026-03-01")
            assert nav is not None
            assert nav["nav_per_share"] == 10.5
            assert nav["total_portfolio_value"] == 21000.0

    def test_collect_daily_nav_missing_date(self, test_db):
        """Missing date returns None."""
        with patch("scripts.sync_to_production.DB_PATH", Path(TEST_DB_PATH)):
            from scripts.sync_to_production import collect_daily_nav

            nav = collect_daily_nav("2099-01-01")
            assert nav is None

    def test_collect_holdings_snapshot(self, test_db):
        """Collect holdings snapshot with positions."""
        self._seed_test_data(test_db)

        with patch("scripts.sync_to_production.DB_PATH", Path(TEST_DB_PATH)):
            from scripts.sync_to_production import collect_holdings_snapshot

            snapshot = collect_holdings_snapshot("2026-03-01")
            assert snapshot is not None
            assert snapshot["source"] == "tastytrade"
            assert len(snapshot["positions"]) == 1
            assert snapshot["positions"][0]["symbol"] == "SGOV"

    def test_collect_trades(self, test_db):
        """Collect trades since a given date."""
        self._seed_test_data(test_db)

        with patch("scripts.sync_to_production.DB_PATH", Path(TEST_DB_PATH)):
            from scripts.sync_to_production import collect_trades

            trades = collect_trades("2026-02-28")
            assert len(trades) >= 1
            assert trades[0]["symbol"] == "SGOV"

    def test_collect_benchmark_prices(self, test_db):
        """Collect benchmark prices since a given date."""
        self._seed_test_data(test_db)

        with patch("scripts.sync_to_production.DB_PATH", Path(TEST_DB_PATH)):
            from scripts.sync_to_production import collect_benchmark_prices

            prices = collect_benchmark_prices("2026-02-28")
            assert len(prices) >= 1
            assert prices[0]["ticker"] == "SPY"

    def test_build_sync_payload(self, test_db):
        """Build full sync payload for a date."""
        self._seed_test_data(test_db)

        with patch("scripts.sync_to_production.DB_PATH", Path(TEST_DB_PATH)):
            from scripts.sync_to_production import build_sync_payload

            payload = build_sync_payload("2026-03-01", lookback_days=3)
            assert "daily_nav" in payload
            assert "holdings_snapshot" in payload
            assert "trades" in payload
            assert "benchmark_prices" in payload
            assert "reconciliation" in payload

    def test_build_payload_empty_date(self, test_db):
        """Payload for a date with no data returns empty dict."""
        with patch("scripts.sync_to_production.DB_PATH", Path(TEST_DB_PATH)):
            from scripts.sync_to_production import build_sync_payload

            payload = build_sync_payload("2099-01-01", lookback_days=0)
            assert payload == {}


# ============================================================
# Admin Sync Endpoint Tests (via Pydantic model validation)
# ============================================================

class TestSyncPayloadValidation:
    """Test Pydantic model validation for sync payloads."""

    def test_full_payload(self):
        """Full payload validates successfully."""
        from apps.investor_portal.api.routes.admin import SyncPayload

        payload = SyncPayload(
            daily_nav={
                "date": "2026-03-01",
                "nav_per_share": 10.5,
                "total_portfolio_value": 21000.0,
                "total_shares": 2000.0,
            },
            holdings_snapshot={
                "date": "2026-03-01",
                "source": "tastytrade",
                "positions": [
                    {"symbol": "SGOV", "quantity": 100.0},
                ],
            },
            trades=[
                {"date": "2026-03-01", "trade_type": "buy", "amount": -5000.0},
            ],
            benchmark_prices=[
                {"date": "2026-03-01", "ticker": "SPY", "close_price": 500.0},
            ],
            reconciliation={
                "date": "2026-03-01",
                "status": "matched",
            },
        )
        assert payload.daily_nav.nav_per_share == 10.5
        assert len(payload.holdings_snapshot.positions) == 1
        assert len(payload.trades) == 1
        assert len(payload.benchmark_prices) == 1

    def test_partial_payload(self):
        """Partial payload (just NAV) is valid."""
        from apps.investor_portal.api.routes.admin import SyncPayload

        payload = SyncPayload(
            daily_nav={
                "date": "2026-03-01",
                "nav_per_share": 10.5,
                "total_portfolio_value": 21000.0,
                "total_shares": 2000.0,
            }
        )
        assert payload.daily_nav is not None
        assert payload.holdings_snapshot is None
        assert payload.trades == []
        assert payload.benchmark_prices == []
        assert payload.reconciliation is None

    def test_empty_payload(self):
        """Empty payload is valid (nothing to sync)."""
        from apps.investor_portal.api.routes.admin import SyncPayload

        payload = SyncPayload()
        assert payload.daily_nav is None
        assert payload.trades == []


class TestSyncEndpointIntegration:
    """Integration tests for the /admin/sync endpoint."""

    def test_sync_writes_to_database(self, test_db):
        """Sync endpoint writes data to database via upsert functions."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import (
                upsert_daily_nav,
                upsert_holdings_snapshot,
                upsert_trades,
                upsert_benchmark_prices,
                upsert_reconciliation,
            )

            # Simulate what the endpoint does
            upsert_daily_nav({
                "date": "2026-03-15",
                "nav_per_share": 11.0,
                "total_portfolio_value": 22000.0,
                "total_shares": 2000.0,
                "daily_change_dollars": 100.0,
                "daily_change_percent": 0.46,
            })
            upsert_holdings_snapshot(
                {"date": "2026-03-15", "source": "tastytrade"},
                [{"symbol": "SGOV", "quantity": 100.0, "market_value": 10000.0}],
            )
            trade_result = upsert_trades([{
                "date": "2026-03-15",
                "trade_type": "interest",
                "amount": 1.50,
                "source": "tastytrade",
                "brokerage_transaction_id": "TT-INT-001",
            }])
            bench_count = upsert_benchmark_prices([
                {"date": "2026-03-15", "ticker": "SPY", "close_price": 505.0},
            ])
            upsert_reconciliation({
                "date": "2026-03-15",
                "tradier_balance": 22000.0,
                "status": "matched",
            })

            # Verify all data written
            cursor = test_db.cursor()

            cursor.execute("SELECT * FROM daily_nav WHERE date = '2026-03-15'")
            assert cursor.fetchone() is not None

            cursor.execute("""
                SELECT COUNT(*) as cnt FROM position_snapshots ps
                JOIN holdings_snapshots hs ON ps.snapshot_id = hs.snapshot_id
                WHERE hs.date = '2026-03-15'
            """)
            assert cursor.fetchone()["cnt"] == 1

            assert trade_result["inserted"] == 1
            assert bench_count == 1

            cursor.execute(
                "SELECT * FROM daily_reconciliation WHERE date = '2026-03-15'"
            )
            assert cursor.fetchone() is not None

    def test_idempotent_sync(self, test_db):
        """Running sync twice for the same date is safe."""
        with patch("apps.investor_portal.api.models.database.get_database_path",
                    return_value=Path(TEST_DB_PATH)):
            from apps.investor_portal.api.models.database import (
                upsert_daily_nav,
                upsert_benchmark_prices,
            )

            nav_row = {
                "date": "2026-03-20",
                "nav_per_share": 10.5,
                "total_portfolio_value": 21000.0,
                "total_shares": 2000.0,
            }
            upsert_daily_nav(nav_row)
            upsert_daily_nav(nav_row)  # Second time

            cursor = test_db.cursor()
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM daily_nav WHERE date = '2026-03-20'"
            )
            assert cursor.fetchone()["cnt"] == 1

            # Benchmarks
            prices = [{"date": "2026-03-20", "ticker": "SPY", "close_price": 500.0}]
            upsert_benchmark_prices(prices)
            upsert_benchmark_prices(prices)

            cursor.execute("""
                SELECT COUNT(*) as cnt FROM benchmark_prices
                WHERE date = '2026-03-20' AND ticker = 'SPY'
            """)
            assert cursor.fetchone()["cnt"] == 1
