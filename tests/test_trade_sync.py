"""
Tests for trade sync functionality.

Validates source tagging, deduplication, trade insertion,
and multi-provider sync logic.
"""

import pytest
import sqlite3
from datetime import datetime, timedelta


class TestSourceTagging:
    """Test that trades are correctly tagged with their brokerage source."""

    def test_insert_tradier_trade(self, test_db):
        """Test inserting a trade with source='tradier'."""
        test_db.execute("""
            INSERT INTO trades (
                brokerage_transaction_id, source, date, trade_type,
                amount, symbol, quantity, price, category, subcategory
            ) VALUES ('TRD-001', 'tradier', '2026-01-15', 'buy',
                      -15000.0, 'AAPL', 100, 150.0, 'Trade', 'Stock Buy')
        """)
        test_db.commit()

        row = test_db.execute(
            "SELECT * FROM trades WHERE brokerage_transaction_id = 'TRD-001'"
        ).fetchone()

        assert row is not None
        assert row['source'] == 'tradier'
        assert row['symbol'] == 'AAPL'
        assert row['amount'] == -15000.0

    def test_insert_tastytrade_trade(self, test_db):
        """Test inserting a trade with source='tastytrade'."""
        test_db.execute("""
            INSERT INTO trades (
                brokerage_transaction_id, source, date, trade_type,
                amount, symbol, quantity, price, category, subcategory
            ) VALUES ('TT-001', 'tastytrade', '2026-01-15', 'sell_to_close',
                      2600.0, 'SPY 250321C500', 5, 5.20, 'Trade', 'Option Call')
        """)
        test_db.commit()

        row = test_db.execute(
            "SELECT * FROM trades WHERE brokerage_transaction_id = 'TT-001'"
        ).fetchone()

        assert row is not None
        assert row['source'] == 'tastytrade'
        assert row['trade_type'] == 'sell_to_close'

    def test_default_source_is_tradier(self, test_db):
        """Test that source defaults to 'tradier' when not specified."""
        test_db.execute("""
            INSERT INTO trades (date, trade_type, amount, symbol, category, subcategory)
            VALUES ('2026-01-15', 'buy', -5000, 'MSFT', 'Trade', 'Stock Buy')
        """)
        test_db.commit()

        row = test_db.execute(
            "SELECT source FROM trades WHERE symbol = 'MSFT'"
        ).fetchone()

        assert row['source'] == 'tradier'

    def test_query_trades_by_source(self, test_db):
        """Test querying trades filtered by brokerage source."""
        trades = [
            ('TRD-001', 'tradier', '2026-01-15', 'buy', -10000, 'AAPL'),
            ('TRD-002', 'tradier', '2026-01-16', 'sell', 12000, 'AAPL'),
            ('TT-001', 'tastytrade', '2026-01-15', 'buy_to_open', -1500, 'SPY'),
            ('TT-002', 'tastytrade', '2026-01-16', 'sell_to_close', 2000, 'SPY'),
            ('TT-003', 'tastytrade', '2026-01-17', 'buy', -8000, 'TSLA'),
        ]

        for brokerage_id, source, dt, ttype, amount, sym in trades:
            test_db.execute("""
                INSERT INTO trades (
                    brokerage_transaction_id, source, date, trade_type,
                    amount, symbol, category, subcategory
                ) VALUES (?, ?, ?, ?, ?, ?, 'Trade', 'Stock')
            """, (brokerage_id, source, dt, ttype, amount, sym))

        test_db.commit()

        tradier_count = test_db.execute(
            "SELECT COUNT(*) FROM trades WHERE source = 'tradier'"
        ).fetchone()[0]
        assert tradier_count == 2

        tt_count = test_db.execute(
            "SELECT COUNT(*) FROM trades WHERE source = 'tastytrade'"
        ).fetchone()[0]
        assert tt_count == 3


class TestDeduplication:
    """Test trade deduplication via (source, brokerage_transaction_id)."""

    def test_same_id_different_sources_allowed(self, test_db):
        """Test that same brokerage_transaction_id is OK across different sources."""
        test_db.execute("""
            INSERT INTO trades (
                brokerage_transaction_id, source, date, trade_type,
                amount, symbol, category, subcategory
            ) VALUES ('TX-001', 'tradier', '2026-01-15', 'buy',
                      -10000, 'AAPL', 'Trade', 'Stock Buy')
        """)
        test_db.execute("""
            INSERT INTO trades (
                brokerage_transaction_id, source, date, trade_type,
                amount, symbol, category, subcategory
            ) VALUES ('TX-001', 'tastytrade', '2026-01-15', 'buy',
                      -10000, 'AAPL', 'Trade', 'Stock Buy')
        """)
        test_db.commit()

        rows = test_db.execute(
            "SELECT * FROM trades WHERE brokerage_transaction_id = 'TX-001'"
        ).fetchall()
        assert len(rows) == 2

    def test_dedup_check_by_source_and_id(self, test_db):
        """Test deduplication logic: check existing IDs before inserting."""
        # Insert initial trade
        test_db.execute("""
            INSERT INTO trades (
                brokerage_transaction_id, source, date, trade_type,
                amount, symbol, category, subcategory
            ) VALUES ('TRD-001', 'tradier', '2026-01-15', 'buy',
                      -10000, 'AAPL', 'Trade', 'Stock Buy')
        """)
        test_db.commit()

        # Simulate dedup check (as sync_all_trades.py does)
        existing_ids = set()
        rows = test_db.execute(
            "SELECT brokerage_transaction_id FROM trades "
            "WHERE source = ? AND brokerage_transaction_id IS NOT NULL",
            ('tradier',)
        ).fetchall()
        existing_ids = {row[0] for row in rows}

        assert 'TRD-001' in existing_ids

        # New transaction should pass dedup
        assert 'TRD-002' not in existing_ids

    def test_null_brokerage_id_not_deduped(self, test_db):
        """Test that trades with NULL brokerage_transaction_id are not deduped."""
        test_db.execute("""
            INSERT INTO trades (
                source, date, trade_type, amount, symbol, category, subcategory
            ) VALUES ('tradier', '2026-01-15', 'dividend', 50.0, 'AAPL', 'Income', 'Dividend')
        """)
        test_db.execute("""
            INSERT INTO trades (
                source, date, trade_type, amount, symbol, category, subcategory
            ) VALUES ('tradier', '2026-01-15', 'dividend', 50.0, 'AAPL', 'Income', 'Dividend')
        """)
        test_db.commit()

        count = test_db.execute(
            "SELECT COUNT(*) FROM trades WHERE symbol = 'AAPL' AND trade_type = 'dividend'"
        ).fetchone()[0]

        # Both should be inserted since brokerage_transaction_id is NULL
        assert count == 2


class TestTradeInsertion:
    """Test the trade insertion pattern used by sync scripts."""

    def test_insert_full_trade_record(self, test_db):
        """Test inserting a trade with all fields populated."""
        test_db.execute("""
            INSERT INTO trades (
                brokerage_transaction_id, source, date, type, trade_type,
                amount, commission, symbol, quantity, price,
                option_type, strike, expiration_date,
                description, notes, category, subcategory
            ) VALUES (
                'TT-100', 'tastytrade', '2026-01-20', 'sell_to_close', 'sell_to_close',
                2600.0, 0.63, 'SPY 250321C500', 5, 5.20,
                'call', 500.0, '2025-03-21',
                'Sold 5 SPY call options', '', 'Trade', 'Option Call'
            )
        """)
        test_db.commit()

        row = test_db.execute(
            "SELECT * FROM trades WHERE brokerage_transaction_id = 'TT-100'"
        ).fetchone()

        assert row['source'] == 'tastytrade'
        assert row['option_type'] == 'call'
        assert row['strike'] == 500.0
        assert row['commission'] == 0.63
        assert row['category'] == 'Trade'
        assert row['subcategory'] == 'Option Call'

    def test_insert_ach_transfer(self, test_db):
        """Test inserting an ACH transfer trade."""
        test_db.execute("""
            INSERT INTO trades (
                brokerage_transaction_id, source, date, type, trade_type,
                amount, commission, symbol, category, subcategory
            ) VALUES (
                'ACH-001', 'tradier', '2026-01-10', 'ach', 'ach',
                5000.0, 0.0, '', 'Transfer', 'Deposit'
            )
        """)
        test_db.commit()

        row = test_db.execute(
            "SELECT * FROM trades WHERE brokerage_transaction_id = 'ACH-001'"
        ).fetchone()

        assert row['trade_type'] == 'ach'
        assert row['amount'] == 5000.0
        assert row['category'] == 'Transfer'
        assert row['subcategory'] == 'Deposit'

    def test_insert_dividend(self, test_db):
        """Test inserting a dividend transaction."""
        test_db.execute("""
            INSERT INTO trades (
                brokerage_transaction_id, source, date, type, trade_type,
                amount, commission, symbol, description, category, subcategory
            ) VALUES (
                'DIV-001', 'tradier', '2026-01-25', 'dividend', 'dividend',
                125.50, 0.0, 'AAPL', 'Dividend payment', 'Income', 'Dividend'
            )
        """)
        test_db.commit()

        row = test_db.execute(
            "SELECT * FROM trades WHERE brokerage_transaction_id = 'DIV-001'"
        ).fetchone()

        assert row['trade_type'] == 'dividend'
        assert row['amount'] == 125.50
        assert row['category'] == 'Income'


class TestMultiProviderSync:
    """Test syncing from multiple brokerages."""

    def test_combined_trade_count(self, test_db):
        """Test total trade count across multiple providers."""
        # Insert trades from both providers
        tradier_trades = [
            ('T-001', 'tradier', '2026-01-15', 'buy', -10000, 'AAPL'),
            ('T-002', 'tradier', '2026-01-16', 'sell', 12000, 'AAPL'),
        ]
        tt_trades = [
            ('TT-001', 'tastytrade', '2026-01-15', 'buy_to_open', -1500, 'SPY'),
            ('TT-002', 'tastytrade', '2026-01-16', 'sell_to_close', 2000, 'SPY'),
            ('TT-003', 'tastytrade', '2026-01-17', 'buy', -8000, 'TSLA'),
        ]

        for brokerage_id, source, dt, ttype, amount, sym in tradier_trades + tt_trades:
            test_db.execute("""
                INSERT INTO trades (
                    brokerage_transaction_id, source, date, trade_type,
                    amount, symbol, category, subcategory
                ) VALUES (?, ?, ?, ?, ?, ?, 'Trade', 'Stock')
            """, (brokerage_id, source, dt, ttype, amount, sym))

        test_db.commit()

        total = test_db.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        assert total == 5

    def test_trade_count_by_date_aggregation(self, test_db):
        """Test aggregating trade counts by date (used for chart secondary Y-axis)."""
        trades = [
            ('T1', 'tradier', '2026-01-15', 'buy', -5000, 'AAPL'),
            ('T2', 'tradier', '2026-01-15', 'sell', 6000, 'MSFT'),
            ('TT1', 'tastytrade', '2026-01-15', 'buy', -3000, 'TSLA'),
            ('T3', 'tradier', '2026-01-16', 'buy', -7000, 'NVDA'),
            ('TT2', 'tastytrade', '2026-01-17', 'sell', 4000, 'AMD'),
        ]

        for brokerage_id, source, dt, ttype, amount, sym in trades:
            test_db.execute("""
                INSERT INTO trades (
                    brokerage_transaction_id, source, date, trade_type,
                    amount, symbol, category, subcategory
                ) VALUES (?, ?, ?, ?, ?, ?, 'Trade', 'Stock')
            """, (brokerage_id, source, dt, ttype, amount, sym))

        test_db.commit()

        # Aggregate trade counts by date — the query charts will use
        rows = test_db.execute("""
            SELECT date, COUNT(*) as trade_count
            FROM trades
            WHERE category = 'Trade'
            GROUP BY date
            ORDER BY date
        """).fetchall()

        assert len(rows) == 3
        assert rows[0]['date'] == '2026-01-15'
        assert rows[0]['trade_count'] == 3
        assert rows[1]['trade_count'] == 1
        assert rows[2]['trade_count'] == 1


class TestMockBrokerageTransactions:
    """Test that the mock_brokerage_api fixture returns proper transactions."""

    def test_mock_get_transactions_returns_list(self, mock_brokerage_api):
        """Test that get_transactions() returns a list."""
        txns = mock_brokerage_api.get_transactions()
        assert isinstance(txns, list)
        assert len(txns) == 2

    def test_mock_transactions_have_required_fields(self, mock_brokerage_api):
        """Test that mock transactions have all required fields."""
        required_fields = [
            'date', 'transaction_type', 'symbol', 'quantity', 'price',
            'amount', 'commission', 'fees', 'description',
            'brokerage_transaction_id', 'category', 'subcategory',
        ]

        txns = mock_brokerage_api.get_transactions()
        for txn in txns:
            for field in required_fields:
                assert field in txn, f"Missing field: {field}"

    def test_mock_transactions_have_valid_types(self, mock_brokerage_api):
        """Test that mock transaction types are valid."""
        valid_types = {
            'buy', 'sell', 'buy_to_open', 'sell_to_close',
            'buy_to_close', 'sell_to_open', 'dividend', 'interest',
            'ach', 'fee', 'other',
        }

        txns = mock_brokerage_api.get_transactions()
        for txn in txns:
            assert txn['transaction_type'] in valid_types, (
                f"Invalid type: {txn['transaction_type']}"
            )

    def test_mock_positions_have_required_fields(self, mock_brokerage_api):
        """Test that mock positions have all required fields."""
        required_fields = [
            'symbol', 'quantity', 'instrument_type',
            'underlying_symbol', 'average_open_price', 'close_price',
        ]

        positions = mock_brokerage_api.get_positions()
        assert len(positions) == 2

        for pos in positions:
            for field in required_fields:
                assert field in pos, f"Missing field: {field}"
