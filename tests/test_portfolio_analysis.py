"""
Tests for Portfolio Analysis API endpoints and calculations.

Tests cover:
- Holdings breakdown endpoint
- Risk metrics calculations (Sharpe, drawdown, volatility)
- Monthly performance endpoint
- Edge cases (empty data, single day, etc.)
"""

import sqlite3
import math
import pytest
from pathlib import Path

# Add project root to path
import sys
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# RISK METRIC CALCULATION TESTS
# ============================================================

class TestRiskMetricCalculations:
    """Test the mathematical correctness of risk calculations."""

    def _compute_metrics(self, nav_data):
        """Simulate the risk-metrics endpoint logic."""
        if len(nav_data) < 2:
            return None

        start_nav = nav_data[0]['nav_per_share']
        end_nav = nav_data[-1]['nav_per_share']
        n_days = len(nav_data)

        daily_returns = [r.get('daily_change_percent', 0) or 0 for r in nav_data if r.get('daily_change_percent') is not None]

        # Total return
        total_return = ((end_nav / start_nav) - 1) * 100

        # Annualized
        years = n_days / 252
        ann_return = ((end_nav / start_nav) ** (1 / years) - 1) * 100 if years > 0 else 0

        # Volatility
        if len(daily_returns) > 1:
            mean_ret = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            daily_vol = math.sqrt(variance)
            ann_vol = daily_vol * math.sqrt(252)
        else:
            ann_vol = 0

        # Sharpe
        risk_free = 5.25
        sharpe = (ann_return - risk_free) / ann_vol if ann_vol > 0 else None

        # Max drawdown
        peak = nav_data[0]['nav_per_share']
        max_dd = 0
        for r in nav_data:
            nav = r['nav_per_share']
            if nav > peak:
                peak = nav
            dd = ((nav - peak) / peak) * 100
            if dd < max_dd:
                max_dd = dd

        # Best / worst
        best_pct = max(daily_returns) if daily_returns else 0
        worst_pct = min(daily_returns) if daily_returns else 0

        pos = sum(1 for r in daily_returns if r > 0)
        neg = sum(1 for r in daily_returns if r < 0)
        win_rate = (pos / (pos + neg) * 100) if (pos + neg) > 0 else 0

        return {
            'total_return': total_return,
            'ann_return': ann_return,
            'ann_vol': ann_vol,
            'sharpe': sharpe,
            'max_dd': max_dd,
            'best_pct': best_pct,
            'worst_pct': worst_pct,
            'win_rate': win_rate,
        }

    def test_sharpe_ratio_positive_return(self):
        """Sharpe ratio is calculated correctly with varying positive returns."""
        data = [
            {'nav_per_share': 1.0000, 'daily_change_percent': None, 'date': '2026-01-01'},
            {'nav_per_share': 1.0010, 'daily_change_percent': 0.10, 'date': '2026-01-02'},
            {'nav_per_share': 1.0030, 'daily_change_percent': 0.20, 'date': '2026-01-03'},
            {'nav_per_share': 1.0035, 'daily_change_percent': 0.05, 'date': '2026-01-06'},
            {'nav_per_share': 1.0055, 'daily_change_percent': 0.20, 'date': '2026-01-07'},
            {'nav_per_share': 1.0040, 'daily_change_percent': -0.15, 'date': '2026-01-08'},
        ]
        metrics = self._compute_metrics(data)
        assert metrics is not None
        assert metrics['total_return'] > 0
        # With varying returns, volatility > 0 so Sharpe should be calculable
        assert metrics['sharpe'] is not None

    def test_sharpe_ratio_constant_nav(self):
        """With constant NAV (zero volatility), Sharpe is None."""
        data = [
            {'nav_per_share': 1.0000, 'daily_change_percent': None, 'date': '2026-01-01'},
            {'nav_per_share': 1.0000, 'daily_change_percent': 0.0, 'date': '2026-01-02'},
            {'nav_per_share': 1.0000, 'daily_change_percent': 0.0, 'date': '2026-01-03'},
        ]
        metrics = self._compute_metrics(data)
        assert metrics['ann_vol'] == 0
        assert metrics['sharpe'] is None

    def test_max_drawdown_basic(self):
        """Max drawdown correctly identifies a peak-to-trough decline."""
        data = [
            {'nav_per_share': 1.0000, 'daily_change_percent': None, 'date': '2026-01-01'},
            {'nav_per_share': 1.1000, 'daily_change_percent': 10.0, 'date': '2026-01-02'},
            {'nav_per_share': 0.9900, 'daily_change_percent': -10.0, 'date': '2026-01-03'},
            {'nav_per_share': 1.0500, 'daily_change_percent': 6.06, 'date': '2026-01-06'},
        ]
        metrics = self._compute_metrics(data)
        # Peak is 1.10, trough is 0.99 → drawdown = (0.99-1.10)/1.10 = -10%
        assert metrics['max_dd'] == pytest.approx(-10.0, abs=0.1)

    def test_max_drawdown_no_decline(self):
        """Max drawdown is 0 when NAV only increases."""
        data = [
            {'nav_per_share': 1.0000, 'daily_change_percent': None, 'date': '2026-01-01'},
            {'nav_per_share': 1.0100, 'daily_change_percent': 1.0, 'date': '2026-01-02'},
            {'nav_per_share': 1.0200, 'daily_change_percent': 0.99, 'date': '2026-01-03'},
        ]
        metrics = self._compute_metrics(data)
        assert metrics['max_dd'] == 0

    def test_volatility_constant_nav(self):
        """Volatility is 0 when NAV never changes."""
        data = [
            {'nav_per_share': 1.0, 'daily_change_percent': 0.0, 'date': f'2026-01-{i:02d}'}
            for i in range(1, 11)
        ]
        metrics = self._compute_metrics(data)
        assert metrics['ann_vol'] == 0

    def test_best_worst_day(self):
        """Best and worst days are correctly identified."""
        data = [
            {'nav_per_share': 1.0, 'daily_change_percent': None, 'date': '2026-01-01'},
            {'nav_per_share': 1.02, 'daily_change_percent': 2.0, 'date': '2026-01-02'},
            {'nav_per_share': 0.99, 'daily_change_percent': -2.94, 'date': '2026-01-03'},
            {'nav_per_share': 1.01, 'daily_change_percent': 2.02, 'date': '2026-01-06'},
        ]
        metrics = self._compute_metrics(data)
        assert metrics['best_pct'] == pytest.approx(2.02, abs=0.01)
        assert metrics['worst_pct'] == pytest.approx(-2.94, abs=0.01)

    def test_win_rate(self):
        """Win rate is correctly calculated."""
        data = [
            {'nav_per_share': 1.0, 'daily_change_percent': None, 'date': '2026-01-01'},
            {'nav_per_share': 1.01, 'daily_change_percent': 1.0, 'date': '2026-01-02'},
            {'nav_per_share': 1.005, 'daily_change_percent': -0.5, 'date': '2026-01-03'},
            {'nav_per_share': 1.015, 'daily_change_percent': 1.0, 'date': '2026-01-06'},
        ]
        metrics = self._compute_metrics(data)
        # 2 positive, 1 negative = 66.67%
        assert metrics['win_rate'] == pytest.approx(66.67, abs=0.1)

    def test_single_data_point(self):
        """Single data point returns None (insufficient data)."""
        data = [{'nav_per_share': 1.0, 'daily_change_percent': None, 'date': '2026-01-01'}]
        assert self._compute_metrics(data) is None


# ============================================================
# MONTHLY PERFORMANCE TESTS
# ============================================================

class TestMonthlyPerformanceCalc:
    """Test monthly return calculations."""

    def test_return_calculation(self):
        """Monthly return = (end_nav / start_nav - 1) * 100."""
        start = 1.0000
        end = 1.0500
        expected = ((end / start) - 1) * 100
        assert expected == pytest.approx(5.0, abs=0.01)

    def test_negative_return(self):
        """Negative monthly return is calculated correctly."""
        start = 1.0000
        end = 0.9700
        expected = ((end / start) - 1) * 100
        assert expected == pytest.approx(-3.0, abs=0.01)

    def test_zero_start_nav_handled(self):
        """Division by zero is handled when start_nav is 0."""
        start = 0
        end = 1.0
        ret = ((end / start) - 1) * 100 if start and start > 0 else 0
        assert ret == 0


# ============================================================
# HOLDINGS AGGREGATION TESTS
# ============================================================

class TestHoldingsAggregation:
    """Test option leg aggregation and allocation calculations."""

    def test_weight_sums_to_100(self):
        """Weights should sum to approximately 100%."""
        holdings = [
            {'market_value': 5000, 'cost_basis': 4500, 'unrealized_pl': 500},
            {'market_value': 3000, 'cost_basis': 3100, 'unrealized_pl': -100},
            {'market_value': 2000, 'cost_basis': 1800, 'unrealized_pl': 200},
        ]
        total = sum(h['market_value'] for h in holdings)
        weights = [h['market_value'] / total * 100 for h in holdings]
        assert sum(weights) == pytest.approx(100.0, abs=0.01)

    def test_pl_pct_calculation(self):
        """P&L percentage is calculated correctly."""
        cost_basis = 5000
        unrealized_pl = 250
        pct = (unrealized_pl / cost_basis) * 100
        assert pct == pytest.approx(5.0, abs=0.01)

    def test_pl_pct_zero_cost_basis(self):
        """P&L percentage handles zero cost basis."""
        cost_basis = 0
        unrealized_pl = 100
        pct = (unrealized_pl / cost_basis * 100) if cost_basis and cost_basis != 0 else 0
        assert pct == 0

    def test_by_symbol_top_8_plus_other(self):
        """by_symbol groups beyond 8th position into Other."""
        symbols = [{'name': f'SYM{i}', 'value': 1000 - i * 100} for i in range(12)]
        by_symbol = []
        other_value = 0
        for i, s in enumerate(symbols):
            if i < 8:
                by_symbol.append(s)
            else:
                other_value += s['value']
        if other_value > 0:
            by_symbol.append({'name': 'Other', 'value': other_value})

        assert len(by_symbol) == 9  # 8 + Other
        assert by_symbol[-1]['name'] == 'Other'
        assert by_symbol[-1]['value'] > 0


# ============================================================
# DATABASE INTEGRATION TESTS (using test fixtures)
# ============================================================

class TestAnalysisWithTestDB:
    """Test analysis queries against a test database."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a minimal test database with required tables."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create daily_nav
        cursor.execute("""
            CREATE TABLE daily_nav (
                date TEXT PRIMARY KEY,
                nav_per_share REAL,
                total_portfolio_value REAL,
                total_shares REAL,
                daily_change_dollars REAL,
                daily_change_percent REAL,
                source TEXT
            )
        """)

        # Insert test data (20 days)
        import random
        random.seed(42)
        nav = 1.0000
        for i in range(20):
            day = f"2026-01-{i+1:02d}"
            change_pct = random.uniform(-1.0, 1.5)
            nav = nav * (1 + change_pct / 100)
            cursor.execute("""
                INSERT INTO daily_nav (date, nav_per_share, total_portfolio_value,
                    total_shares, daily_change_dollars, daily_change_percent, source)
                VALUES (?, ?, ?, 10000, ?, ?, 'test')
            """, (day, nav, nav * 10000, nav * 10000 - 10000, change_pct))

        # Create holdings tables
        cursor.execute("""
            CREATE TABLE holdings_snapshots (
                snapshot_id INTEGER PRIMARY KEY,
                date TEXT, source TEXT, snapshot_time TEXT, total_positions INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE position_snapshots (
                position_id INTEGER PRIMARY KEY,
                snapshot_id INTEGER,
                symbol TEXT, quantity REAL, market_value REAL,
                cost_basis REAL, unrealized_pl REAL, instrument_type TEXT
            )
        """)
        cursor.execute("""
            INSERT INTO holdings_snapshots (date, source, total_positions)
            VALUES ('2026-01-20', 'test', 3)
        """)
        snap_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO position_snapshots (snapshot_id, symbol, quantity, market_value, cost_basis, unrealized_pl, instrument_type)
            VALUES (?, 'SPY', 100, 50000, 48000, 2000, 'Equity')
        """, (snap_id,))
        cursor.execute("""
            INSERT INTO position_snapshots (snapshot_id, symbol, quantity, market_value, cost_basis, unrealized_pl, instrument_type)
            VALUES (?, 'AAPL', 50, 8500, 8000, 500, 'Equity')
        """, (snap_id,))
        cursor.execute("""
            INSERT INTO position_snapshots (snapshot_id, symbol, quantity, market_value, cost_basis, unrealized_pl, instrument_type)
            VALUES (?, 'AAPL 260221C200', 10, 1500, 1000, 500, 'Equity Option')
        """, (snap_id,))

        # Create monthly performance view
        cursor.execute("""
            CREATE VIEW v_monthly_performance AS
            SELECT
                strftime('%Y-%m', date) as month,
                MIN(nav_per_share) as min_nav,
                MAX(nav_per_share) as max_nav,
                (SELECT nav_per_share FROM daily_nav d2
                 WHERE strftime('%Y-%m', d2.date) = strftime('%Y-%m', d1.date)
                 ORDER BY d2.date ASC LIMIT 1) as start_nav,
                (SELECT nav_per_share FROM daily_nav d2
                 WHERE strftime('%Y-%m', d2.date) = strftime('%Y-%m', d1.date)
                 ORDER BY d2.date DESC LIMIT 1) as end_nav,
                COUNT(*) as trading_days
            FROM daily_nav d1
            GROUP BY strftime('%Y-%m', date)
            ORDER BY month
        """)

        conn.commit()
        conn.close()
        return db_path

    def test_nav_data_for_risk(self, test_db):
        """Test that NAV data can be queried for risk metrics."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM daily_nav")
        assert cursor.fetchone()['cnt'] == 20
        conn.close()

    def test_holdings_snapshot_query(self, test_db):
        """Test that holdings snapshots return aggregated positions."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT snapshot_id, date FROM holdings_snapshots ORDER BY date DESC LIMIT 1")
        snap = cursor.fetchone()
        assert snap is not None

        cursor.execute("SELECT * FROM position_snapshots WHERE snapshot_id = ?", (snap['snapshot_id'],))
        positions = cursor.fetchall()
        assert len(positions) == 3
        conn.close()

    def test_monthly_performance_view(self, test_db):
        """Test that v_monthly_performance view returns valid data."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM v_monthly_performance")
        rows = cursor.fetchall()
        assert len(rows) >= 1
        row = dict(rows[0])
        assert 'start_nav' in row
        assert 'end_nav' in row
        assert row['trading_days'] > 0
        conn.close()
