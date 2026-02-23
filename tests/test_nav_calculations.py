"""
Test NAV (Net Asset Value) calculations.

Tests the core mathematical calculations for:
- Basic NAV formula: Portfolio Value ÷ Total Shares
- Daily change calculations ($ and %)
- Edge cases (zero shares, negative values, etc.)
"""

import pytest
from tests.conftest import calculate_nav, assert_close


@pytest.mark.unit
@pytest.mark.calculations
@pytest.mark.critical
class TestBasicNAV:
    """Test basic NAV calculation formula."""
    
    def test_initial_nav_is_one_dollar(self):
        """On day 1, NAV should be $1.00 per share."""
        total_value = 38000
        total_shares = 38000
        nav = calculate_nav(total_value, total_shares)
        assert nav == 1.0
    
    def test_nav_after_gain(self):
        """After market gain, NAV increases proportionally."""
        total_value = 40000  # +$2000 gain
        total_shares = 38000
        expected_nav = 1.0526  # $1.0526 per share
        nav = calculate_nav(total_value, total_shares)
        assert_close(nav, expected_nav, 0.0001)
    
    def test_nav_after_loss(self):
        """After market loss, NAV decreases proportionally."""
        total_value = 36000  # -$2000 loss
        total_shares = 38000
        expected_nav = 0.9474  # $0.9474 per share
        nav = calculate_nav(total_value, total_shares)
        assert_close(nav, expected_nav, 0.0001)
    
    def test_nav_with_large_numbers(self):
        """NAV calculation works with large portfolio values."""
        total_value = 1000000
        total_shares = 800000
        expected_nav = 1.25
        nav = calculate_nav(total_value, total_shares)
        assert nav == expected_nav
    
    def test_nav_with_small_numbers(self):
        """NAV calculation works with small portfolio values."""
        total_value = 1000
        total_shares = 900
        expected_nav = 1.1111
        nav = calculate_nav(total_value, total_shares)
        assert_close(nav, expected_nav, 0.0001)


@pytest.mark.unit
@pytest.mark.calculations
class TestNAVEdgeCases:
    """Test NAV calculation edge cases."""
    
    def test_zero_shares_returns_one_dollar(self):
        """When no shares exist, NAV defaults to $1.00."""
        total_value = 0
        total_shares = 0
        nav = calculate_nav(total_value, total_shares)
        assert nav == 1.0
    
    def test_very_small_share_count(self):
        """NAV works with fractional shares."""
        total_value = 1000
        total_shares = 0.5
        expected_nav = 2000
        nav = calculate_nav(total_value, total_shares)
        assert nav == expected_nav
    
    def test_nav_precision(self):
        """NAV maintains 4 decimal place precision."""
        total_value = 10000
        total_shares = 9753
        nav = calculate_nav(total_value, total_shares)
        # Should round to 4 decimals: 10000/9753 = 1.0253
        assert len(str(nav).split('.')[-1]) <= 4
        assert nav == 1.0253


@pytest.mark.unit
@pytest.mark.calculations
@pytest.mark.critical
class TestDailyChanges:
    """Test daily change calculations."""
    
    def test_daily_change_dollars(self):
        """Calculate $ change from previous day."""
        previous_value = 38000
        current_value = 38500
        change = current_value - previous_value
        assert change == 500
    
    def test_daily_change_percent(self):
        """Calculate % change from previous day."""
        previous_value = 38000
        current_value = 38500
        change_dollars = current_value - previous_value
        change_percent = (change_dollars / previous_value) * 100
        assert_close(change_percent, 1.32, 0.01)
    
    def test_negative_daily_change(self):
        """Handle negative (loss) days correctly."""
        previous_value = 40000
        current_value = 39000
        change_dollars = current_value - previous_value
        change_percent = (change_dollars / previous_value) * 100
        assert change_dollars == -1000
        assert_close(change_percent, -2.5, 0.01)
    
    def test_zero_change(self):
        """Handle days with no change."""
        previous_value = 40000
        current_value = 40000
        change_dollars = current_value - previous_value
        change_percent = (change_dollars / previous_value) * 100
        assert change_dollars == 0
        assert change_percent == 0.0


@pytest.mark.integration
@pytest.mark.database
class TestNAVDatabaseOperations:
    """Test NAV operations with database."""
    
    def test_insert_daily_nav(self, test_db):
        """Can insert NAV record into database."""
        from datetime import datetime
        
        test_db.execute("""
            INSERT INTO daily_nav
            (date, nav_per_share, total_portfolio_value, total_shares, 
             daily_change_dollars, daily_change_percent, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("2026-01-15", 1.0526, 40000, 38000, 500, 1.32, datetime.now().isoformat()))
        test_db.commit()
        
        cursor = test_db.execute("SELECT * FROM daily_nav WHERE date = ?", ("2026-01-15",))
        row = cursor.fetchone()
        
        assert row is not None
        assert row['nav_per_share'] == 1.0526
        assert row['total_portfolio_value'] == 40000
    
    def test_retrieve_latest_nav(self, populated_db):
        """Can retrieve most recent NAV record."""
        cursor = populated_db.execute("""
            SELECT nav_per_share, total_portfolio_value, total_shares
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        
        assert row is not None
        assert row['nav_per_share'] > 0
        assert row['total_shares'] > 0
    
    def test_nav_history_ordering(self, populated_db):
        """NAV records are properly ordered by date."""
        cursor = populated_db.execute("""
            SELECT date, nav_per_share
            FROM daily_nav
            ORDER BY date ASC
        """)
        dates = [row['date'] for row in cursor.fetchall()]
        
        # Verify dates are in ascending order
        assert dates == sorted(dates)
        
        # Verify NAV generally increases (in our test data)
        cursor = populated_db.execute("""
            SELECT nav_per_share
            FROM daily_nav
            ORDER BY date ASC
        """)
        navs = [row['nav_per_share'] for row in cursor.fetchall()]
        
        # First NAV should be 1.0
        assert navs[0] == 1.0
        
        # Last NAV should be higher (portfolio grew)
        assert navs[-1] > navs[0]


@pytest.mark.integration
class TestNAVWithContributions:
    """Test NAV behavior when processing contributions."""
    
    def test_nav_stays_same_after_contribution(self, populated_db):
        """NAV per share doesn't change when contribution processed."""
        # Get current NAV
        cursor = populated_db.execute("""
            SELECT nav_per_share, total_portfolio_value, total_shares
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        before = cursor.fetchone()
        nav_before = before['nav_per_share']
        
        # Simulate contribution: add $5000 at current NAV
        contribution = 5000
        shares_purchased = contribution / nav_before
        new_value = before['total_portfolio_value'] + contribution
        new_shares = before['total_shares'] + shares_purchased
        
        # Calculate new NAV
        nav_after = calculate_nav(new_value, new_shares)
        
        # NAV should stay the same (within rounding)
        assert_close(nav_after, nav_before, 0.0001)


@pytest.mark.calculations
@pytest.mark.critical
class TestNAVAccuracy:
    """Test NAV calculation accuracy with real-world scenarios."""
    
    def test_scenario_from_test_guide(self):
        """Verify NAV calculation from Test Scenarios Guide."""
        # Scenario 1: Simple Daily Update
        portfolio_value = 38500
        total_shares = 38000
        expected_nav = 1.0132
        
        nav = calculate_nav(portfolio_value, total_shares)
        assert_close(nav, expected_nav, 0.0001)
    
    def test_scenario_after_contribution(self):
        """Verify NAV calculation after contribution."""
        # From Scenario 2: After $5000 contribution
        portfolio_value = 45000
        total_shares = 42750
        expected_nav = 1.0526
        
        nav = calculate_nav(portfolio_value, total_shares)
        assert_close(nav, expected_nav, 0.0001)
    
    def test_scenario_multiple_contributions(self):
        """Verify NAV after multiple contributions same day."""
        # From Scenario 3
        portfolio_value = 56500
        total_shares = 51391.82
        expected_nav = 1.0994
        
        nav = calculate_nav(portfolio_value, total_shares)
        assert_close(nav, expected_nav, 0.0001)
