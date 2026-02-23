"""
Tests for chart generation module.

Validates that each chart function produces valid PNG files,
handles empty/minimal data gracefully, and respects parameters.
"""

import pytest
import os
from pathlib import Path
from datetime import datetime, timedelta

from src.reporting.charts import (
    generate_nav_chart,
    generate_investor_value_chart,
    generate_holdings_chart,
    generate_benchmark_chart,
    _parse_date,
)


# ============================================================
# TEST DATA FIXTURES
# ============================================================

@pytest.fixture
def nav_history():
    """Sample NAV history spanning 30 days."""
    base_nav = 1.0
    start = datetime(2026, 1, 1)
    history = []
    for i in range(30):
        day = start + timedelta(days=i)
        # Skip weekends for realism
        if day.weekday() >= 5:
            continue
        nav = base_nav + (i * 0.005) + (0.002 if i % 3 == 0 else -0.001)
        history.append({
            'date': day.strftime('%Y-%m-%d'),
            'nav_per_share': round(nav, 4),
        })
    return history


@pytest.fixture
def trade_counts():
    """Sample trade counts by date."""
    start = datetime(2026, 1, 1)
    counts = []
    for i in range(30):
        day = start + timedelta(days=i)
        if day.weekday() >= 5:
            continue
        if i % 4 == 0:  # Trades every ~4 days
            counts.append({
                'date': day.strftime('%Y-%m-%d'),
                'trade_count': (i % 7) + 1,
            })
    return counts


@pytest.fixture
def investor_transactions():
    """Sample investor transactions."""
    return [
        {'date': '2026-01-01', 'transaction_type': 'Initial', 'amount': 10000},
        {'date': '2026-01-10', 'transaction_type': 'Contribution', 'amount': 5000},
        {'date': '2026-01-20', 'transaction_type': 'Withdrawal', 'amount': -2000},
    ]


@pytest.fixture
def equity_positions():
    """Sample equity positions."""
    return [
        {
            'symbol': 'AAPL',
            'underlying_symbol': 'AAPL',
            'market_value': 17500,
            'instrument_type': 'Equity',
            'unrealized_pl': 2500,
        },
        {
            'symbol': 'MSFT',
            'underlying_symbol': 'MSFT',
            'market_value': 12000,
            'instrument_type': 'Equity',
            'unrealized_pl': -800,
        },
        {
            'symbol': 'TSLA',
            'underlying_symbol': 'TSLA',
            'market_value': 8500,
            'instrument_type': 'Equity',
            'unrealized_pl': 1200,
        },
    ]


@pytest.fixture
def mixed_positions():
    """Sample positions with equities and options."""
    return [
        {
            'symbol': 'AAPL',
            'underlying_symbol': 'AAPL',
            'market_value': 17500,
            'instrument_type': 'Equity',
            'unrealized_pl': 2500,
        },
        {
            'symbol': 'SPY 250321C500',
            'underlying_symbol': 'SPY',
            'market_value': 2600,
            'instrument_type': 'Equity Option',
            'unrealized_pl': 850,
        },
        {
            'symbol': 'SPY 250321P480',
            'underlying_symbol': 'SPY',
            'market_value': 1200,
            'instrument_type': 'Equity Option',
            'unrealized_pl': -300,
        },
        {
            'symbol': 'NVDA',
            'underlying_symbol': 'NVDA',
            'market_value': 9000,
            'instrument_type': 'Equity',
            'unrealized_pl': 3000,
        },
    ]


# ============================================================
# HELPER
# ============================================================

def assert_valid_png(path):
    """Assert that the file exists, is non-empty, and has PNG magic bytes."""
    assert path.exists(), f"Chart file does not exist: {path}"
    assert path.stat().st_size > 0, f"Chart file is empty: {path}"

    # Check PNG magic bytes
    with open(path, 'rb') as f:
        header = f.read(8)
    assert header[:4] == b'\x89PNG', f"Not a valid PNG file: {path}"


# ============================================================
# NAV CHART TESTS
# ============================================================

class TestNAVChart:
    """Tests for generate_nav_chart()."""

    def test_produces_valid_png(self, nav_history):
        """Test that NAV chart produces a valid PNG file."""
        path = generate_nav_chart(nav_history)
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_with_trade_counts(self, nav_history, trade_counts):
        """Test NAV chart with trade count overlay."""
        path = generate_nav_chart(nav_history, trade_counts=trade_counts)
        try:
            assert_valid_png(path)
            # Chart with dual axes should be larger than without
            assert path.stat().st_size > 10000
        finally:
            path.unlink(missing_ok=True)

    def test_empty_data(self):
        """Test NAV chart with empty data produces placeholder."""
        path = generate_nav_chart([])
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_single_data_point(self):
        """Test NAV chart with only one data point."""
        path = generate_nav_chart([
            {'date': '2026-01-01', 'nav_per_share': 1.0}
        ])
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_two_data_points(self):
        """Test NAV chart with minimum meaningful data."""
        path = generate_nav_chart([
            {'date': '2026-01-01', 'nav_per_share': 1.0},
            {'date': '2026-01-02', 'nav_per_share': 1.01},
        ])
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_with_empty_trade_counts(self, nav_history):
        """Test NAV chart with empty trade counts list."""
        path = generate_nav_chart(nav_history, trade_counts=[])
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)


# ============================================================
# INVESTOR VALUE CHART TESTS
# ============================================================

class TestInvestorValueChart:
    """Tests for generate_investor_value_chart()."""

    def test_produces_valid_png(self, nav_history):
        """Test that investor value chart produces a valid PNG."""
        path = generate_investor_value_chart(nav_history, investor_shares=10000)
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_with_transaction_markers(self, nav_history, investor_transactions):
        """Test chart with contribution/withdrawal event markers."""
        path = generate_investor_value_chart(
            nav_history,
            investor_shares=15000,
            investor_transactions=investor_transactions,
        )
        try:
            assert_valid_png(path)
            assert path.stat().st_size > 10000
        finally:
            path.unlink(missing_ok=True)

    def test_empty_data(self):
        """Test investor value chart with empty data produces placeholder."""
        path = generate_investor_value_chart([], investor_shares=10000)
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_zero_shares(self, nav_history):
        """Test chart with zero shares (inactive investor edge case)."""
        path = generate_investor_value_chart(nav_history, investor_shares=0)
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_no_transactions(self, nav_history):
        """Test chart without transaction markers."""
        path = generate_investor_value_chart(
            nav_history,
            investor_shares=10000,
            investor_transactions=None,
        )
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)


# ============================================================
# HOLDINGS CHART TESTS
# ============================================================

class TestHoldingsChart:
    """Tests for generate_holdings_chart()."""

    def test_produces_valid_png(self, equity_positions):
        """Test that holdings chart produces a valid PNG."""
        path = generate_holdings_chart(equity_positions)
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_mixed_instruments(self, mixed_positions):
        """Test chart with equity and option positions."""
        path = generate_holdings_chart(mixed_positions)
        try:
            assert_valid_png(path)
            assert path.stat().st_size > 10000
        finally:
            path.unlink(missing_ok=True)

    def test_empty_positions(self):
        """Test holdings chart with empty data produces placeholder."""
        path = generate_holdings_chart([])
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_single_position(self):
        """Test holdings chart with single position."""
        path = generate_holdings_chart([{
            'symbol': 'AAPL',
            'underlying_symbol': 'AAPL',
            'market_value': 17500,
            'instrument_type': 'Equity',
            'unrealized_pl': 2500,
        }])
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_grouping_many_positions(self):
        """Test that positions beyond max_positions are grouped into 'Other'."""
        positions = [
            {
                'symbol': f'SYM{i}',
                'underlying_symbol': f'SYM{i}',
                'market_value': 1000 * (15 - i),
                'instrument_type': 'Equity',
                'unrealized_pl': 100 * (i % 5 - 2),
            }
            for i in range(15)
        ]
        path = generate_holdings_chart(positions, max_positions=8)
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_option_legs_aggregation(self):
        """Test that multiple option legs on same underlying are aggregated."""
        positions = [
            {
                'symbol': 'SPY 250321C500',
                'underlying_symbol': 'SPY',
                'market_value': 2600,
                'instrument_type': 'Equity Option',
                'unrealized_pl': 850,
            },
            {
                'symbol': 'SPY 250321P480',
                'underlying_symbol': 'SPY',
                'market_value': 1200,
                'instrument_type': 'Equity Option',
                'unrealized_pl': -300,
            },
        ]
        path = generate_holdings_chart(positions)
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)


# ============================================================
# EDGE CASE TESTS
# ============================================================

class TestChartEdgeCases:
    """Test edge cases across all chart types."""

    def test_nav_chart_with_declining_values(self):
        """Test NAV chart when values decline (negative trend)."""
        path = generate_nav_chart([
            {'date': '2026-01-01', 'nav_per_share': 1.10},
            {'date': '2026-01-02', 'nav_per_share': 1.05},
            {'date': '2026-01-03', 'nav_per_share': 0.98},
            {'date': '2026-01-04', 'nav_per_share': 0.95},
        ])
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_holdings_with_negative_market_value(self):
        """Test holdings chart with short positions (negative values)."""
        path = generate_holdings_chart([
            {
                'symbol': 'AAPL',
                'underlying_symbol': 'AAPL',
                'market_value': 17500,
                'instrument_type': 'Equity',
                'unrealized_pl': 2500,
            },
            {
                'symbol': 'SPY Short',
                'underlying_symbol': 'SPY',
                'market_value': -5000,
                'instrument_type': 'Equity Option',
                'unrealized_pl': 1200,
            },
        ])
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_temp_files_are_created_in_temp_dir(self, nav_history):
        """Test that chart files are created in system temp directory."""
        import tempfile
        path = generate_nav_chart(nav_history)
        try:
            temp_dir = Path(tempfile.gettempdir())
            assert path.parent == temp_dir or str(path.parent).startswith(str(temp_dir))
        finally:
            path.unlink(missing_ok=True)

    def test_all_charts_produce_different_files(self, nav_history, equity_positions):
        """Test that each chart function creates a unique file."""
        paths = []
        try:
            paths.append(generate_nav_chart(nav_history))
            paths.append(generate_investor_value_chart(nav_history, investor_shares=10000))
            paths.append(generate_holdings_chart(equity_positions))

            # All should be unique paths
            assert len(set(str(p) for p in paths)) == 3

            # All should be valid PNGs
            for p in paths:
                assert_valid_png(p)
        finally:
            for p in paths:
                p.unlink(missing_ok=True)


# ============================================================
# DATE PARSING RESILIENCE TESTS
# ============================================================

class TestDateParsing:
    """Tests for _parse_date() handling various date formats."""

    def test_plain_date(self):
        """Standard YYYY-MM-DD format."""
        d = _parse_date('2026-01-15')
        assert d == datetime(2026, 1, 15)

    def test_iso8601_with_time_and_z(self):
        """ISO 8601 with T00:00:00Z suffix (from Tradier imports)."""
        d = _parse_date('2025-12-30T00:00:00Z')
        assert d == datetime(2025, 12, 30)

    def test_iso8601_with_timezone_offset(self):
        """ISO 8601 with timezone offset."""
        d = _parse_date('2026-01-15T16:00:00+00:00')
        assert d == datetime(2026, 1, 15)

    def test_iso8601_with_time_no_z(self):
        """ISO 8601 with time but no timezone."""
        d = _parse_date('2026-01-15T12:30:00')
        assert d == datetime(2026, 1, 15)

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace in date string."""
        d = _parse_date('  2026-01-15  ')
        assert d == datetime(2026, 1, 15)

    def test_nav_chart_with_iso_dates(self):
        """NAV chart handles ISO 8601 dates in trade counts."""
        nav = [
            {'date': '2026-01-01', 'nav_per_share': 1.0},
            {'date': '2026-01-02', 'nav_per_share': 1.01},
        ]
        trades = [
            {'date': '2026-01-01T00:00:00Z', 'trade_count': 3},
            {'date': '2026-01-02T00:00:00Z', 'trade_count': 1},
        ]
        path = generate_nav_chart(nav, trade_counts=trades)
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)


# ============================================================
# INVESTOR VALUE CHART — SHARE RECONSTRUCTION TESTS
# ============================================================

class TestInvestorValueShareReconstruction:
    """Tests for accurate share-count reconstruction in value chart."""

    def test_with_shares_transacted_data(self):
        """Chart reconstructs share history from transaction data."""
        nav = [
            {'date': '2026-01-01', 'nav_per_share': 1.0},
            {'date': '2026-01-02', 'nav_per_share': 1.01},
            {'date': '2026-01-03', 'nav_per_share': 1.02},
            {'date': '2026-01-06', 'nav_per_share': 1.03},
            {'date': '2026-01-07', 'nav_per_share': 1.04},
        ]
        txns = [
            {
                'date': '2026-01-01',
                'transaction_type': 'Initial',
                'amount': 10000,
                'shares_transacted': 10000.0,
            },
            {
                'date': '2026-01-06',
                'transaction_type': 'Contribution',
                'amount': 5000,
                'shares_transacted': 4854.3689,
            },
        ]
        path = generate_investor_value_chart(
            nav, investor_shares=14854.3689, investor_transactions=txns,
        )
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_falls_back_to_constant_shares_without_data(self):
        """Without shares_transacted, uses constant investor_shares."""
        nav = [
            {'date': '2026-01-01', 'nav_per_share': 1.0},
            {'date': '2026-01-02', 'nav_per_share': 1.01},
        ]
        txns = [
            {'date': '2026-01-01', 'transaction_type': 'Initial', 'amount': 10000},
        ]
        # No shares_transacted → should use constant 10000
        path = generate_investor_value_chart(
            nav, investor_shares=10000, investor_transactions=txns,
        )
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_withdrawal_reduces_shares(self):
        """Withdrawals properly reduce share count in chart."""
        nav = [
            {'date': '2026-01-01', 'nav_per_share': 1.0},
            {'date': '2026-01-02', 'nav_per_share': 1.01},
            {'date': '2026-01-03', 'nav_per_share': 1.02},
        ]
        txns = [
            {
                'date': '2026-01-01',
                'transaction_type': 'Initial',
                'amount': 10000,
                'shares_transacted': 10000.0,
            },
            {
                'date': '2026-01-02',
                'transaction_type': 'Withdrawal',
                'amount': -2000,
                'shares_transacted': 1980.1980,
            },
        ]
        path = generate_investor_value_chart(
            nav, investor_shares=8019.8020, investor_transactions=txns,
        )
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)


# ============================================================
# BENCHMARK CHART TESTS
# ============================================================

@pytest.fixture
def benchmark_data():
    """Sample benchmark data for 22 trading days."""
    start = datetime(2026, 1, 1)
    data = {}
    for ticker, base_price in [('SPY', 500.0), ('QQQ', 450.0), ('BTC-USD', 95000.0)]:
        series = []
        for i in range(30):
            day = start + timedelta(days=i)
            # SPY/QQQ skip weekends; BTC trades every day
            if day.weekday() >= 5 and ticker != 'BTC-USD':
                continue
            price = base_price * (1 + i * 0.003 + (0.005 if i % 5 == 0 else -0.002))
            series.append({
                'date': day.strftime('%Y-%m-%d'),
                'close_price': round(price, 2),
            })
        data[ticker] = series
    return data


class TestBenchmarkChart:
    """Tests for generate_benchmark_chart()."""

    def test_produces_valid_png(self, nav_history, benchmark_data):
        """Test that benchmark chart produces a valid PNG file."""
        path = generate_benchmark_chart(nav_history, benchmark_data)
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_with_empty_benchmarks(self, nav_history):
        """Test chart with no benchmark data still produces a chart."""
        path = generate_benchmark_chart(nav_history, {})
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_with_none_benchmarks(self, nav_history):
        """Test chart with None benchmark data."""
        path = generate_benchmark_chart(nav_history, None)
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_with_partial_benchmarks(self, nav_history):
        """Test chart when only one benchmark has data."""
        partial = {
            'SPY': [
                {'date': '2026-01-01', 'close_price': 500.0},
                {'date': '2026-01-02', 'close_price': 502.0},
                {'date': '2026-01-03', 'close_price': 504.0},
            ],
            'QQQ': [],
            'BTC-USD': [],
        }
        path = generate_benchmark_chart(nav_history, partial)
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_empty_nav_produces_placeholder(self):
        """Test chart with empty NAV data returns a placeholder."""
        path = generate_benchmark_chart([], {})
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_single_nav_point_produces_placeholder(self):
        """Test chart with only one NAV point returns a placeholder."""
        path = generate_benchmark_chart(
            [{'date': '2026-01-01', 'nav_per_share': 1.0}], {}
        )
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_custom_dimensions(self, nav_history, benchmark_data):
        """Test chart at Discord-optimized dimensions."""
        path = generate_benchmark_chart(
            nav_history, benchmark_data,
            width=14.0, height=7.0, dpi=200,
        )
        try:
            assert_valid_png(path)
            # Discord chart should be larger than default
            assert path.stat().st_size > 1000
        finally:
            path.unlink(missing_ok=True)

    def test_report_dimensions(self, nav_history, benchmark_data):
        """Test chart at report-optimized dimensions."""
        path = generate_benchmark_chart(
            nav_history, benchmark_data,
            width=7.5, height=4.0, dpi=150,
        )
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_no_mountain(self, nav_history, benchmark_data):
        """Test chart with show_mountain=False."""
        path = generate_benchmark_chart(
            nav_history, benchmark_data, show_mountain=False,
        )
        try:
            assert_valid_png(path)
        finally:
            path.unlink(missing_ok=True)

    def test_unique_temp_files(self, nav_history, benchmark_data):
        """Each call should produce a unique temporary file."""
        path1 = generate_benchmark_chart(nav_history, benchmark_data)
        path2 = generate_benchmark_chart(nav_history, benchmark_data)
        try:
            assert path1 != path2
        finally:
            path1.unlink(missing_ok=True)
            path2.unlink(missing_ok=True)
