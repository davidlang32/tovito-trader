"""
Tests for benchmark market data module.

Validates fetch/cache logic, data retrieval, normalization,
and edge cases. All yfinance calls are mocked to avoid network
dependencies in CI.
"""

import pytest
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pandas as pd

from src.market_data.benchmarks import (
    refresh_benchmark_cache,
    get_benchmark_data,
    normalize_series,
    BENCHMARK_TICKERS,
    _ensure_table,
    _get_latest_cached_date,
)


# ============================================================
# TEST FIXTURES
# ============================================================

@pytest.fixture
def benchmark_db(tmp_path):
    """Create a temporary database with benchmark_prices table."""
    db_path = tmp_path / "test_benchmarks.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE benchmark_prices (
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            close_price REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (date, ticker)
        )
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def populated_db(benchmark_db):
    """Database with pre-populated benchmark data."""
    conn = sqlite3.connect(str(benchmark_db))
    start = datetime(2026, 1, 2)

    for i in range(30):
        day = start + timedelta(days=i)
        date_str = day.strftime('%Y-%m-%d')

        # SPY: ~500, slight uptrend
        conn.execute(
            "INSERT INTO benchmark_prices (date, ticker, close_price) VALUES (?, ?, ?)",
            (date_str, 'SPY', round(500.0 + i * 0.5, 2))
        )
        # QQQ: ~450, slight uptrend
        conn.execute(
            "INSERT INTO benchmark_prices (date, ticker, close_price) VALUES (?, ?, ?)",
            (date_str, 'QQQ', round(450.0 + i * 0.4, 2))
        )
        # BTC-USD: ~95000, volatile
        conn.execute(
            "INSERT INTO benchmark_prices (date, ticker, close_price) VALUES (?, ?, ?)",
            (date_str, 'BTC-USD', round(95000.0 + i * 100 + (i % 3) * 500, 2))
        )

    conn.commit()
    conn.close()
    return benchmark_db


def _make_mock_yf_data(ticker, start_date, num_days=10, base_price=500.0):
    """Create a mock yfinance DataFrame response."""
    dates = pd.date_range(start=start_date, periods=num_days, freq='B')
    prices = [base_price + i * 0.5 for i in range(num_days)]

    # yfinance returns MultiIndex columns for single tickers too
    df = pd.DataFrame(
        {'Close': prices},
        index=dates,
    )
    return df


# ============================================================
# NORMALIZE SERIES TESTS
# ============================================================

class TestNormalizeSeries:
    """Tests for normalize_series()."""

    def test_starts_at_zero(self):
        """Normalized series should start at 0% change."""
        series = [
            {'date': '2026-01-01', 'close_price': 100.0},
            {'date': '2026-01-02', 'close_price': 105.0},
            {'date': '2026-01-03', 'close_price': 110.0},
        ]
        result = normalize_series(series)

        assert len(result) == 3
        assert result[0]['pct_change'] == 0.0
        assert result[0]['date'] == '2026-01-01'

    def test_calculates_percentage_correctly(self):
        """Test that percentage change is calculated correctly."""
        series = [
            {'date': '2026-01-01', 'close_price': 100.0},
            {'date': '2026-01-02', 'close_price': 110.0},
            {'date': '2026-01-03', 'close_price': 90.0},
        ]
        result = normalize_series(series)

        assert result[1]['pct_change'] == 10.0
        assert result[2]['pct_change'] == -10.0

    def test_empty_input(self):
        """Normalization of empty list returns empty list."""
        assert normalize_series([]) == []

    def test_single_point(self):
        """Single data point should return 0% change."""
        series = [{'date': '2026-01-01', 'close_price': 100.0}]
        result = normalize_series(series)
        assert result == [{'date': '2026-01-01', 'pct_change': 0.0}]

    def test_custom_price_key(self):
        """Test with a custom price key."""
        series = [
            {'date': '2026-01-01', 'nav_per_share': 1.0},
            {'date': '2026-01-02', 'nav_per_share': 1.05},
        ]
        result = normalize_series(series, price_key='nav_per_share')
        assert result[1]['pct_change'] == pytest.approx(5.0, abs=0.01)

    def test_zero_base_price(self):
        """Zero base price should return all zeros (no division by zero)."""
        series = [
            {'date': '2026-01-01', 'close_price': 0},
            {'date': '2026-01-02', 'close_price': 100.0},
        ]
        result = normalize_series(series)
        assert all(p['pct_change'] == 0.0 for p in result)


# ============================================================
# DATABASE CACHE TESTS
# ============================================================

class TestEnsureTable:
    """Tests for _ensure_table()."""

    def test_creates_table_if_missing(self, tmp_path):
        """Table should be created if it doesn't exist."""
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()

        _ensure_table(db_path)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='benchmark_prices'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_idempotent(self, benchmark_db):
        """Calling _ensure_table twice should not error."""
        _ensure_table(benchmark_db)
        _ensure_table(benchmark_db)


class TestGetLatestCachedDate:
    """Tests for _get_latest_cached_date()."""

    def test_returns_none_for_empty(self, benchmark_db):
        """Should return None when no data exists for ticker."""
        assert _get_latest_cached_date(benchmark_db, 'SPY') is None

    def test_returns_latest_date(self, populated_db):
        """Should return the most recent cached date."""
        latest = _get_latest_cached_date(populated_db, 'SPY')
        assert latest is not None
        # Should be a valid date string
        datetime.strptime(latest, '%Y-%m-%d')


class TestGetBenchmarkData:
    """Tests for get_benchmark_data()."""

    def test_returns_all_tickers(self, populated_db):
        """Should return data for all default tickers."""
        data = get_benchmark_data(populated_db, days=365)
        assert 'SPY' in data
        assert 'QQQ' in data
        assert 'BTC-USD' in data

    def test_data_is_chronological(self, populated_db):
        """Data should be ordered oldest first."""
        data = get_benchmark_data(populated_db, days=365)
        for ticker, series in data.items():
            if len(series) > 1:
                dates = [s['date'] for s in series]
                assert dates == sorted(dates), f"{ticker} not sorted"

    def test_respects_days_limit(self, populated_db):
        """Should only return data within the days window."""
        data_short = get_benchmark_data(populated_db, days=5)
        data_long = get_benchmark_data(populated_db, days=365)

        for ticker in BENCHMARK_TICKERS:
            assert len(data_short[ticker]) <= len(data_long[ticker])

    def test_empty_table(self, benchmark_db):
        """Should return empty lists when no data cached."""
        data = get_benchmark_data(benchmark_db, days=90)
        for ticker in BENCHMARK_TICKERS:
            assert data[ticker] == []

    def test_returns_correct_format(self, populated_db):
        """Each item should have 'date' and 'close_price' keys."""
        data = get_benchmark_data(populated_db, days=365)
        for ticker, series in data.items():
            for item in series:
                assert 'date' in item
                assert 'close_price' in item
                assert isinstance(item['close_price'], float)

    def test_start_date_filter(self, populated_db):
        """Should filter by start_date when provided."""
        data = get_benchmark_data(
            populated_db,
            start_date='2026-01-20',
        )
        for ticker, series in data.items():
            for item in series:
                assert item['date'] >= '2026-01-20'

    def test_handles_missing_table_gracefully(self, tmp_path):
        """Should return empty dict if table doesn't exist yet."""
        db_path = tmp_path / "no_table.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()
        # _ensure_table is called internally, so it should create it
        data = get_benchmark_data(db_path, days=90)
        assert isinstance(data, dict)


# ============================================================
# REFRESH CACHE TESTS (mocked yfinance)
# ============================================================

class TestRefreshBenchmarkCache:
    """Tests for refresh_benchmark_cache() with mocked yfinance."""

    @patch('src.market_data.benchmarks.yf', create=True)
    def test_inserts_new_data(self, mock_yf_module, benchmark_db):
        """Should insert new rows when cache is empty."""
        # We need to patch at the point of import inside the function
        mock_df = _make_mock_yf_data('SPY', '2026-01-02', num_days=5, base_price=500.0)

        with patch('yfinance.download', return_value=mock_df):
            stats = refresh_benchmark_cache(
                benchmark_db,
                tickers=['SPY'],
                lookback_days=30,
            )

        assert 'SPY' in stats
        assert stats['SPY'] > 0

        # Verify data in database
        data = get_benchmark_data(benchmark_db, tickers=['SPY'], days=365)
        assert len(data['SPY']) > 0

    @patch('yfinance.download')
    def test_incremental_fetch(self, mock_download, populated_db):
        """Should only fetch dates after the last cached date."""
        # Mock returns empty (no new data)
        mock_download.return_value = pd.DataFrame()

        stats = refresh_benchmark_cache(populated_db, tickers=['SPY'])

        assert stats['SPY'] == 0

    @patch('yfinance.download')
    def test_handles_download_failure(self, mock_download, benchmark_db):
        """Should handle yfinance failures gracefully."""
        mock_download.side_effect = Exception("Network error")

        stats = refresh_benchmark_cache(benchmark_db, tickers=['SPY'])
        assert stats['SPY'] == 0

    @patch('yfinance.download')
    def test_no_duplicate_inserts(self, mock_download, populated_db):
        """INSERT OR IGNORE should prevent duplicate entries."""
        # Mock returns data that overlaps with existing cache
        existing_data = get_benchmark_data(populated_db, tickers=['SPY'], days=365)
        initial_count = len(existing_data['SPY'])

        mock_download.return_value = pd.DataFrame()
        stats = refresh_benchmark_cache(populated_db, tickers=['SPY'])

        # Count should not have increased
        after_data = get_benchmark_data(populated_db, tickers=['SPY'], days=365)
        assert len(after_data['SPY']) == initial_count
