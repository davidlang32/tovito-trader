"""
Test contribution processing workflow.

Tests:
- Share calculation when investor adds money
- Database updates (investor shares, NAV, transactions)
- Multiple contributions on same day
- Edge cases
"""

import pytest
from datetime import datetime
from tests.conftest import calculate_shares, calculate_nav, assert_close, assert_database_consistency


@pytest.mark.unit
@pytest.mark.calculations
@pytest.mark.critical
class TestShareCalculations:
    """Test share purchase calculations for contributions."""
    
    def test_basic_share_calculation(self):
        """Calculate shares purchased with contribution."""
        amount = 5000
        nav = 1.0526
        expected_shares = 4750.0
        
        shares = calculate_shares(amount, nav)
        assert_close(shares, expected_shares, 0.01)
    
    def test_share_calculation_at_one_dollar(self):
        """At $1.00 NAV, $1 = 1 share."""
        amount = 10000
        nav = 1.0
        
        shares = calculate_shares(amount, nav)
        assert shares == 10000
    
    def test_share_calculation_high_nav(self):
        """Calculate shares when NAV is high."""
        amount = 10000
        nav = 2.50
        expected_shares = 4000
        
        shares = calculate_shares(amount, nav)
        assert shares == expected_shares
    
    def test_share_calculation_precision(self):
        """Share calculations maintain precision."""
        amount = 3000
        nav = 1.0994
        expected_shares = 2729.0
        
        shares = calculate_shares(amount, nav)
        assert_close(shares, expected_shares, 1.0)  # Within 1 share
    
    def test_fractional_shares(self):
        """System handles fractional shares correctly."""
        amount = 5555.55
        nav = 1.23
        
        shares = calculate_shares(amount, nav)
        # Should be fractional
        assert shares > 4000
        assert shares < 5000


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.critical
class TestContributionWorkflow:
    """Test complete contribution processing workflow."""
    
    def test_single_contribution(self, populated_db):
        """Process single contribution successfully."""
        # Get investor before contribution
        cursor = populated_db.execute("""
            SELECT current_shares, net_investment
            FROM investors
            WHERE id = ?
        """, ("20260101-01A",))
        before = cursor.fetchone()
        
        # Get current NAV
        cursor = populated_db.execute("""
            SELECT nav_per_share, total_portfolio_value, total_shares
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        nav_data = cursor.fetchone()
        current_nav = nav_data['nav_per_share']
        
        # Process contribution
        contribution_amount = 5000
        shares_to_add = calculate_shares(contribution_amount, current_nav)
        
        # Update investor
        new_shares = before['current_shares'] + shares_to_add
        new_investment = before['net_investment'] + contribution_amount
        
        populated_db.execute("""
            UPDATE investors
            SET current_shares = ?,
                net_investment = ?,
                updated_at = ?
            WHERE id = ?
        """, (new_shares, new_investment, datetime.now().isoformat(), "20260101-01A"))
        
        # Record transaction
        populated_db.execute("""
            INSERT INTO transactions
            (date, investor_id, investor_name, transaction_type, amount, 
             share_price, shares_transacted, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("2026-01-15", "20260101-01A", "Test Investor 1", "Contribution",
              contribution_amount, current_nav, shares_to_add, datetime.now().isoformat()))
        
        # Update daily NAV
        new_total_value = nav_data['total_portfolio_value'] + contribution_amount
        new_total_shares = nav_data['total_shares'] + shares_to_add
        new_nav = calculate_nav(new_total_value, new_total_shares)
        
        populated_db.execute("""
            INSERT INTO daily_nav
            (date, nav_per_share, total_portfolio_value, total_shares,
             daily_change_dollars, daily_change_percent, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("2026-01-15", new_nav, new_total_value, new_total_shares,
              contribution_amount, 0, datetime.now().isoformat()))
        
        populated_db.commit()
        
        # Verify investor updated
        cursor = populated_db.execute("""
            SELECT current_shares, net_investment
            FROM investors
            WHERE id = ?
        """, ("20260101-01A",))
        after = cursor.fetchone()
        
        assert_close(after['current_shares'], new_shares, 0.01)
        assert_close(after['net_investment'], new_investment, 0.01)
        
        # Verify transaction recorded
        cursor = populated_db.execute("""
            SELECT COUNT(*) as count
            FROM transactions
            WHERE investor_id = ? AND transaction_type = 'Contribution'
        """, ("20260101-01A",))
        assert cursor.fetchone()['count'] >= 1
        
        # Verify NAV stayed same (within rounding)
        assert_close(new_nav, current_nav, 0.0001)
        
        # Verify database consistency
        assert_database_consistency(populated_db)
    
    def test_multiple_contributions_same_day(self, populated_db):
        """Process multiple contributions on same day."""
        # Get current NAV
        cursor = populated_db.execute("""
            SELECT nav_per_share, total_portfolio_value, total_shares
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        nav_data = cursor.fetchone()
        current_nav = nav_data['nav_per_share']
        
        # Three contributions
        contributions = [
            ("20260101-01A", "Test Investor 1", 3000),
            ("20260101-02A", "Test Investor 2", 4500),
            ("20260101-04A", "Test Investor 4", 2000),
        ]
        
        total_contributed = sum(c[2] for c in contributions)
        total_shares_added = 0
        
        for investor_id, investor_name, amount in contributions:
            shares = calculate_shares(amount, current_nav)
            total_shares_added += shares
            
            # Update investor
            populated_db.execute("""
                UPDATE investors
                SET current_shares = current_shares + ?,
                    net_investment = net_investment + ?
                WHERE id = ?
            """, (shares, amount, investor_id))
            
            # Record transaction
            populated_db.execute("""
                INSERT INTO transactions
                (date, investor_id, investor_name, transaction_type, amount,
                 share_price, shares_transacted, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ("2026-01-20", investor_id, investor_name, "Contribution",
                  amount, current_nav, shares, datetime.now().isoformat()))
        
        # Update daily NAV with all contributions
        new_total_value = nav_data['total_portfolio_value'] + total_contributed
        new_total_shares = nav_data['total_shares'] + total_shares_added
        new_nav = calculate_nav(new_total_value, new_total_shares)
        
        populated_db.execute("""
            INSERT INTO daily_nav
            (date, nav_per_share, total_portfolio_value, total_shares,
             daily_change_dollars, daily_change_percent, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("2026-01-20", new_nav, new_total_value, new_total_shares,
              total_contributed, 0, datetime.now().isoformat()))
        
        populated_db.commit()
        
        # Verify NAV stayed same
        assert_close(new_nav, current_nav, 0.0001)
        
        # Verify all transactions recorded
        cursor = populated_db.execute("""
            SELECT COUNT(*) as count
            FROM transactions
            WHERE date = '2026-01-20' AND transaction_type = 'Contribution'
        """)
        assert cursor.fetchone()['count'] == 3
        
        # Verify database consistency
        assert_database_consistency(populated_db)


@pytest.mark.integration
class TestContributionImpact:
    """Test contribution impact on investor positions."""
    
    def test_investor_percentage_changes(self, populated_db):
        """Investor percentages change after contribution."""
        # Get percentages before
        cursor = populated_db.execute("""
            SELECT id, current_shares,
                   (current_shares * 100.0 / (SELECT SUM(current_shares) 
                    FROM investors WHERE status = 'Active')) as percentage
            FROM investors
            WHERE status = 'Active'
        """)
        before = {row['id']: row['percentage'] for row in cursor.fetchall()}
        
        # Investor 1 makes large contribution
        cursor = populated_db.execute("""
            SELECT nav_per_share FROM daily_nav
            ORDER BY date DESC LIMIT 1
        """)
        nav = cursor.fetchone()['nav_per_share']
        
        contribution = 10000
        shares = calculate_shares(contribution, nav)
        
        populated_db.execute("""
            UPDATE investors
            SET current_shares = current_shares + ?
            WHERE id = '20260101-01A'
        """, (shares,))
        populated_db.commit()
        
        # Get percentages after
        cursor = populated_db.execute("""
            SELECT id, current_shares,
                   (current_shares * 100.0 / (SELECT SUM(current_shares)
                    FROM investors WHERE status = 'Active')) as percentage
            FROM investors
            WHERE status = 'Active'
        """)
        after = {row['id']: row['percentage'] for row in cursor.fetchall()}
        
        # Investor 1's percentage should increase
        assert after['20260101-01A'] > before['20260101-01A']
        
        # Other investors' percentages should decrease
        assert after['20260101-02A'] < before['20260101-02A']
        assert after['20260101-03A'] < before['20260101-03A']
    
    def test_contribution_increases_unrealized_gain(self, populated_db):
        """Contribution at price > $1.00 creates immediate unrealized gain."""
        # Setup: Ensure NAV > 1.00
        populated_db.execute("""
            UPDATE daily_nav
            SET nav_per_share = 1.20,
                total_portfolio_value = 45600,
                total_shares = 38000
            WHERE date = (SELECT MAX(date) FROM daily_nav)
        """)
        populated_db.commit()
        
        # Investor makes contribution at $1.20
        nav = 1.20
        contribution = 6000
        shares = calculate_shares(contribution, nav)  # 5000 shares
        
        # Update investor
        populated_db.execute("""
            UPDATE investors
            SET current_shares = 10000 + ?,
                net_investment = 10000 + ?
            WHERE id = '20260101-01A'
        """, (shares, contribution))
        populated_db.commit()
        
        # Calculate their position
        cursor = populated_db.execute("""
            SELECT current_shares, net_investment
            FROM investors
            WHERE id = '20260101-01A'
        """)
        inv = cursor.fetchone()
        
        current_value = inv['current_shares'] * nav
        unrealized_gain = current_value - inv['net_investment']
        
        # Should have unrealized gain from original $10k
        # Original: $10k at $1.00 = 10k shares, now worth $12k (+$2k gain)
        # New: $6k at $1.20 = 5k shares, now worth $6k (no gain)
        # Total: 15k shares worth $18k, invested $16k, gain = $2k
        assert unrealized_gain > 0
        assert_close(unrealized_gain, 2000, 10)


@pytest.mark.unit
class TestContributionEdgeCases:
    """Test edge cases in contribution processing."""
    
    def test_very_small_contribution(self):
        """Handle very small contribution amounts."""
        amount = 0.01
        nav = 1.0
        shares = calculate_shares(amount, nav)
        assert shares == 0.01
    
    def test_very_large_contribution(self):
        """Handle very large contribution amounts."""
        amount = 1000000
        nav = 1.25
        shares = calculate_shares(amount, nav)
        assert shares == 800000
    
    def test_contribution_at_high_nav(self):
        """Contribution when NAV is high results in fewer shares."""
        amount = 5000
        
        # At $1.00 NAV
        shares_low = calculate_shares(amount, 1.0)
        
        # At $2.00 NAV
        shares_high = calculate_shares(amount, 2.0)
        
        # Should get half as many shares at 2x NAV
        assert shares_high == shares_low / 2


@pytest.mark.calculations
@pytest.mark.critical
class TestContributionScenarios:
    """Test contribution scenarios from Test Scenarios Guide."""
    
    def test_scenario_2_single_contribution(self):
        """Verify calculations from Scenario 2."""
        # Portfolio before: $40,000, 38,000 shares, NAV $1.0526
        nav = 1.0526
        contribution = 5000
        
        # Calculate shares
        shares = calculate_shares(contribution, nav)
        expected_shares = 4750
        
        assert_close(shares, expected_shares, 1)
        
        # Verify NAV stays same
        new_value = 40000 + 5000  # $45,000
        new_shares = 38000 + shares  # 42,750
        new_nav = calculate_nav(new_value, new_shares)
        
        assert_close(new_nav, nav, 0.0001)
    
    def test_scenario_3_multiple_contributions(self):
        """Verify calculations from Scenario 3."""
        # Portfolio before: $47,000, 42,750 shares, NAV $1.0994
        nav = 1.0994
        contributions = [
            ("Investor 1", 3000, 2729),
            ("Investor 2", 4500, 4093.49),
            ("Investor 4", 2000, 1819.33),
        ]
        
        total_amount = sum(c[1] for c in contributions)
        total_shares_expected = sum(c[2] for c in contributions)
        
        # Calculate shares for each
        total_shares_calculated = sum(
            calculate_shares(amount, nav)
            for _, amount, _ in contributions
        )
        
        # Should match expected
        assert_close(total_shares_calculated, total_shares_expected, 10)
        
        # Verify NAV stays same
        new_value = 47000 + total_amount
        new_shares = 42750 + total_shares_calculated
        new_nav = calculate_nav(new_value, new_shares)
        
        assert_close(new_nav, nav, 0.0001)
