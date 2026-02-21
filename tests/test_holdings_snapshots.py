"""
Tests for holdings snapshot functionality.

Validates that daily position snapshots are correctly stored
and retrieved, with proper deduplication on (date, source).
"""

import pytest
import sqlite3
from datetime import datetime


class TestSnapshotCreation:
    """Test creating holdings snapshots."""

    def test_insert_snapshot_header(self, test_db):
        """Test inserting a holdings snapshot header record."""
        test_db.execute("""
            INSERT INTO holdings_snapshots (date, source, snapshot_time, total_positions)
            VALUES ('2026-01-15', 'tradier', '2026-01-15T16:05:00', 3)
        """)
        test_db.commit()

        row = test_db.execute(
            "SELECT * FROM holdings_snapshots WHERE date = '2026-01-15'"
        ).fetchone()

        assert row is not None
        assert row['source'] == 'tradier'
        assert row['total_positions'] == 3

    def test_insert_position_snapshots(self, test_db):
        """Test inserting position records linked to a snapshot."""
        test_db.execute("""
            INSERT INTO holdings_snapshots (date, source, snapshot_time, total_positions)
            VALUES ('2026-01-15', 'tradier', '2026-01-15T16:05:00', 2)
        """)
        snapshot_id = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]

        positions = [
            (snapshot_id, 'AAPL', 'AAPL', 100, 'Equity', 150.0, 175.0, 17500.0, 15000.0, 2500.0),
            (snapshot_id, 'SPY 250321C500', 'SPY', 5, 'Equity Option', 3.50, 5.20, 2600.0, 1750.0, 850.0),
        ]

        for pos in positions:
            test_db.execute("""
                INSERT INTO position_snapshots (
                    snapshot_id, symbol, underlying_symbol, quantity,
                    instrument_type, average_open_price, close_price,
                    market_value, cost_basis, unrealized_pl
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, pos)

        test_db.commit()

        rows = test_db.execute(
            "SELECT * FROM position_snapshots WHERE snapshot_id = ?",
            (snapshot_id,)
        ).fetchall()

        assert len(rows) == 2
        assert rows[0]['symbol'] == 'AAPL'
        assert rows[0]['market_value'] == 17500.0
        assert rows[1]['instrument_type'] == 'Equity Option'

    def test_multiple_brokerages_same_day(self, test_db):
        """Test snapshots from different brokerages on the same day."""
        test_db.execute("""
            INSERT INTO holdings_snapshots (date, source, snapshot_time, total_positions)
            VALUES ('2026-01-15', 'tradier', '2026-01-15T16:05:00', 3)
        """)
        test_db.execute("""
            INSERT INTO holdings_snapshots (date, source, snapshot_time, total_positions)
            VALUES ('2026-01-15', 'tastytrade', '2026-01-15T16:05:00', 5)
        """)
        test_db.commit()

        rows = test_db.execute(
            "SELECT * FROM holdings_snapshots WHERE date = '2026-01-15'"
        ).fetchall()

        assert len(rows) == 2
        sources = {row['source'] for row in rows}
        assert sources == {'tradier', 'tastytrade'}


class TestSnapshotDeduplication:
    """Test that (date, source) uniqueness is enforced."""

    def test_unique_constraint_prevents_duplicate(self, test_db):
        """Test that duplicate (date, source) raises IntegrityError."""
        test_db.execute("""
            INSERT INTO holdings_snapshots (date, source, snapshot_time, total_positions)
            VALUES ('2026-01-15', 'tradier', '2026-01-15T16:05:00', 3)
        """)
        test_db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            test_db.execute("""
                INSERT INTO holdings_snapshots (date, source, snapshot_time, total_positions)
                VALUES ('2026-01-15', 'tradier', '2026-01-15T16:10:00', 4)
            """)

    def test_replace_updates_existing_snapshot(self, test_db):
        """Test INSERT OR REPLACE updates a snapshot for same (date, source)."""
        test_db.execute("""
            INSERT INTO holdings_snapshots (date, source, snapshot_time, total_positions)
            VALUES ('2026-01-15', 'tradier', '2026-01-15T16:05:00', 3)
        """)
        test_db.commit()

        test_db.execute("""
            INSERT OR REPLACE INTO holdings_snapshots (date, source, snapshot_time, total_positions)
            VALUES ('2026-01-15', 'tradier', '2026-01-15T16:10:00', 5)
        """)
        test_db.commit()

        rows = test_db.execute(
            "SELECT * FROM holdings_snapshots WHERE date = '2026-01-15' AND source = 'tradier'"
        ).fetchall()

        assert len(rows) == 1
        assert rows[0]['total_positions'] == 5


class TestPositionCounting:
    """Test position counting and aggregation."""

    def test_count_positions_by_source(self, test_db):
        """Test counting positions grouped by brokerage source."""
        # Tradier snapshot with 2 positions
        test_db.execute("""
            INSERT INTO holdings_snapshots (date, source, snapshot_time, total_positions)
            VALUES ('2026-01-15', 'tradier', '2026-01-15T16:05:00', 2)
        """)
        tradier_id = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]

        for sym in ['AAPL', 'MSFT']:
            test_db.execute("""
                INSERT INTO position_snapshots (snapshot_id, symbol, quantity, market_value)
                VALUES (?, ?, 100, 10000)
            """, (tradier_id, sym))

        # TastyTrade snapshot with 3 positions
        test_db.execute("""
            INSERT INTO holdings_snapshots (date, source, snapshot_time, total_positions)
            VALUES ('2026-01-15', 'tastytrade', '2026-01-15T16:05:00', 3)
        """)
        tt_id = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]

        for sym in ['TSLA', 'NVDA', 'AMD']:
            test_db.execute("""
                INSERT INTO position_snapshots (snapshot_id, symbol, quantity, market_value)
                VALUES (?, ?, 50, 5000)
            """, (tt_id, sym))

        test_db.commit()

        # Count total positions across all sources
        total = test_db.execute(
            "SELECT COUNT(*) FROM position_snapshots"
        ).fetchone()[0]
        assert total == 5

        # Count per source via join
        per_source = test_db.execute("""
            SELECT h.source, COUNT(p.position_id) as pos_count
            FROM holdings_snapshots h
            JOIN position_snapshots p ON h.snapshot_id = p.snapshot_id
            WHERE h.date = '2026-01-15'
            GROUP BY h.source
        """).fetchall()

        source_counts = {row['source']: row['pos_count'] for row in per_source}
        assert source_counts['tradier'] == 2
        assert source_counts['tastytrade'] == 3

    def test_multi_day_snapshot_history(self, test_db):
        """Test snapshot data across multiple days."""
        for day in range(15, 18):
            date_str = f'2026-01-{day}'
            test_db.execute("""
                INSERT INTO holdings_snapshots (date, source, snapshot_time, total_positions)
                VALUES (?, 'tradier', ?, ?)
            """, (date_str, f'{date_str}T16:05:00', day - 14))

            snap_id = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]
            for i in range(day - 14):
                test_db.execute("""
                    INSERT INTO position_snapshots (snapshot_id, symbol, quantity, market_value)
                    VALUES (?, ?, 100, 10000)
                """, (snap_id, f'SYM{i}'))

        test_db.commit()

        # Query history
        rows = test_db.execute("""
            SELECT date, total_positions FROM holdings_snapshots
            ORDER BY date
        """).fetchall()

        assert len(rows) == 3
        assert rows[0]['total_positions'] == 1
        assert rows[1]['total_positions'] == 2
        assert rows[2]['total_positions'] == 3


class TestPositionDataIntegrity:
    """Test that position snapshot data is stored accurately."""

    def test_option_position_fields(self, test_db):
        """Test that option-specific fields are stored correctly."""
        test_db.execute("""
            INSERT INTO holdings_snapshots (date, source, snapshot_time, total_positions)
            VALUES ('2026-01-15', 'tastytrade', '2026-01-15T16:05:00', 1)
        """)
        snap_id = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]

        test_db.execute("""
            INSERT INTO position_snapshots (
                snapshot_id, symbol, underlying_symbol, quantity,
                instrument_type, average_open_price, close_price,
                market_value, cost_basis, unrealized_pl,
                option_type, strike, expiration_date, multiplier
            ) VALUES (?, 'SPY 250321C500', 'SPY', 10, 'Equity Option',
                      3.50, 5.20, 5200.0, 3500.0, 1700.0,
                      'call', 500.0, '2025-03-21', 100)
        """, (snap_id,))
        test_db.commit()

        row = test_db.execute(
            "SELECT * FROM position_snapshots WHERE symbol = 'SPY 250321C500'"
        ).fetchone()

        assert row['underlying_symbol'] == 'SPY'
        assert row['instrument_type'] == 'Equity Option'
        assert row['option_type'] == 'call'
        assert row['strike'] == 500.0
        assert row['expiration_date'] == '2025-03-21'
        assert row['multiplier'] == 100
        assert row['unrealized_pl'] == 1700.0

    def test_unrealized_pl_calculation(self, test_db):
        """Test that unrealized P&L values are stored correctly."""
        test_db.execute("""
            INSERT INTO holdings_snapshots (date, source, snapshot_time, total_positions)
            VALUES ('2026-01-15', 'tradier', '2026-01-15T16:05:00', 2)
        """)
        snap_id = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Profitable position
        test_db.execute("""
            INSERT INTO position_snapshots (
                snapshot_id, symbol, quantity, average_open_price, close_price,
                market_value, cost_basis, unrealized_pl
            ) VALUES (?, 'AAPL', 100, 150.0, 175.0, 17500.0, 15000.0, 2500.0)
        """, (snap_id,))

        # Losing position
        test_db.execute("""
            INSERT INTO position_snapshots (
                snapshot_id, symbol, quantity, average_open_price, close_price,
                market_value, cost_basis, unrealized_pl
            ) VALUES (?, 'MSFT', 50, 400.0, 380.0, 19000.0, 20000.0, -1000.0)
        """, (snap_id,))

        test_db.commit()

        rows = test_db.execute("""
            SELECT symbol, unrealized_pl FROM position_snapshots
            WHERE snapshot_id = ?
            ORDER BY symbol
        """, (snap_id,)).fetchall()

        assert rows[0]['symbol'] == 'AAPL'
        assert rows[0]['unrealized_pl'] == 2500.0
        assert rows[1]['symbol'] == 'MSFT'
        assert rows[1]['unrealized_pl'] == -1000.0

    def test_foreign_key_constraint(self, test_db):
        """Test that position_snapshots requires a valid snapshot_id."""
        # Enable foreign keys (SQLite has them off by default)
        test_db.execute("PRAGMA foreign_keys = ON")

        with pytest.raises(sqlite3.IntegrityError):
            test_db.execute("""
                INSERT INTO position_snapshots (
                    snapshot_id, symbol, quantity, market_value
                ) VALUES (999, 'AAPL', 100, 10000)
            """)
