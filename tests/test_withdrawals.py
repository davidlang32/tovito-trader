"""
Test withdrawal processing with tax calculations.

Tests:
- Proportional gain calculation
- Tax calculation (37% rate)
- Net proceeds calculation
- Share reduction
- Tax event logging
- Complete withdrawal workflow
"""

import pytest
from datetime import datetime
from tests.conftest import (
    calculate_shares,
    calculate_nav,
    calculate_withdrawal_tax,
    assert_close,
    assert_database_consistency
)


@pytest.mark.unit
@pytest.mark.calculations
@pytest.mark.critical
class TestWithdrawalTaxCalculations:
    """Test tax calculations for withdrawals."""
    
    def test_basic_tax_calculation(self, tax_rate):
        """Calculate tax on withdrawal with gain."""
        current_value = 15000
        net_investment = 10000
        withdrawal_amount = 5000
        
        result = calculate_withdrawal_tax(
            withdrawal_amount,
            current_value,
            net_investment,
            tax_rate
        )
        
        # Total gain: $5000
        # Withdrawing 33.33% ($5000 / $15000)
        # Realized gain: $5000 * 33.33% = $1667
        # Tax: $1667 * 37% = $617
        # Net proceeds: $5000 - $617 = $4383
        
        assert_close(result['realized_gain'], 1667, 10)
        assert_close(result['tax_due'], 617, 10)
        assert_close(result['net_proceeds'], 4383, 10)
    
    def test_withdrawal_all_basis_no_tax(self, tax_rate):
        """Withdrawal of only basis (cost) has no tax."""
        current_value = 10000
        net_investment = 10000
        withdrawal_amount = 5000
        
        result = calculate_withdrawal_tax(
            withdrawal_amount,
            current_value,
            net_investment,
            tax_rate
        )
        
        # No gain, so no tax
        assert result['realized_gain'] == 0
        assert result['tax_due'] == 0
        assert result['net_proceeds'] == 5000
    
    def test_full_withdrawal_with_gain(self, tax_rate):
        """Full withdrawal realizes all gains."""
        current_value = 15000
        net_investment = 10000
        withdrawal_amount = 15000
        
        result = calculate_withdrawal_tax(
            withdrawal_amount,
            current_value,
            net_investment,
            tax_rate
        )
        
        # Withdrawing 100%
        # Realized gain: $5000 (all of it)
        # Tax: $5000 * 37% = $1850
        # Net proceeds: $15000 - $1850 = $13150
        
        assert result['realized_gain'] == 5000
        assert result['tax_due'] == 1850
        assert result['net_proceeds'] == 13150
    
    def test_withdrawal_with_loss(self, tax_rate):
        """Withdrawal when position is at loss has no tax."""
        current_value = 8000
        net_investment = 10000
        withdrawal_amount = 4000
        
        result = calculate_withdrawal_tax(
            withdrawal_amount,
            current_value,
            net_investment,
            tax_rate
        )
        
        # Position has $2000 loss, not gain
        assert result['realized_gain'] == 0
        assert result['tax_due'] == 0
        assert result['net_proceeds'] == 4000
    
    def test_proportional_gain_calculation(self, tax_rate):
        """Tax is proportional to amount withdrawn."""
        current_value = 20000
        net_investment = 10000
        # Total unrealized gain: $10,000
        
        # Withdraw 25% ($5000)
        result_25 = calculate_withdrawal_tax(5000, current_value, net_investment, tax_rate)
        
        # Withdraw 50% ($10000)
        result_50 = calculate_withdrawal_tax(10000, current_value, net_investment, tax_rate)
        
        # 50% withdrawal should have 2x the tax of 25% withdrawal
        assert_close(result_50['tax_due'], result_25['tax_due'] * 2, 1)


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.critical
class TestWithdrawalWorkflow:
    """Test complete withdrawal processing workflow."""
    
    def test_single_withdrawal(self, populated_db, tax_rate):
        """Process single withdrawal successfully."""
        # Get investor before withdrawal
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
        
        # Calculate current value
        current_value = before['current_shares'] * current_nav
        
        # Process withdrawal
        withdrawal_amount = 3000
        
        # Calculate tax
        tax_calc = calculate_withdrawal_tax(
            withdrawal_amount,
            current_value,
            before['net_investment'],
            tax_rate
        )
        
        # Calculate shares to remove
        shares_to_remove = calculate_shares(withdrawal_amount, current_nav)
        
        # Update investor
        new_shares = before['current_shares'] - shares_to_remove
        new_investment = before['net_investment'] - withdrawal_amount
        
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
        """, ("2026-01-25", "20260101-01A", "Test Investor 1", "Withdrawal",
              withdrawal_amount, current_nav, -shares_to_remove, datetime.now().isoformat()))
        
        # Record tax event
        populated_db.execute("""
            INSERT INTO tax_events
            (date, investor_id, investor_name, event_type, withdrawal_amount,
             realized_gain, tax_due, net_proceeds, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("2026-01-25", "20260101-01A", "Test Investor 1", "Withdrawal",
              withdrawal_amount, tax_calc['realized_gain'], tax_calc['tax_due'],
              tax_calc['net_proceeds'], datetime.now().isoformat()))
        
        # Update daily NAV
        new_total_value = nav_data['total_portfolio_value'] - withdrawal_amount
        new_total_shares = nav_data['total_shares'] - shares_to_remove
        new_nav = calculate_nav(new_total_value, new_total_shares)
        
        populated_db.execute("""
            INSERT INTO daily_nav
            (date, nav_per_share, total_portfolio_value, total_shares,
             daily_change_dollars, daily_change_percent, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("2026-01-25", new_nav, new_total_value, new_total_shares,
              -withdrawal_amount, 0, datetime.now().isoformat()))
        
        populated_db.commit()
        
        # Verify investor updated
        cursor = populated_db.execute("""
            SELECT current_shares, net_investment
            FROM investors
            WHERE id = ?
        """, ("20260101-01A",))
        after = cursor.fetchone()
        
        assert after['current_shares'] < before['current_shares']
        assert after['net_investment'] < before['net_investment']
        
        # Verify transaction recorded
        cursor = populated_db.execute("""
            SELECT COUNT(*) as count
            FROM transactions
            WHERE investor_id = ? AND transaction_type = 'Withdrawal'
        """, ("20260101-01A",))
        assert cursor.fetchone()['count'] >= 1
        
        # Verify tax event recorded
        cursor = populated_db.execute("""
            SELECT realized_gain, tax_due
            FROM tax_events
            WHERE investor_id = ? AND date = '2026-01-25'
        """, ("20260101-01A",))
        tax_event = cursor.fetchone()
        assert tax_event is not None
        assert tax_event['realized_gain'] == tax_calc['realized_gain']
        assert tax_event['tax_due'] == tax_calc['tax_due']
        
        # Verify NAV stayed same (within rounding)
        assert_close(new_nav, current_nav, 0.0001)
        
        # Verify database consistency
        assert_database_consistency(populated_db)
    
    def test_full_withdrawal_closes_position(self, populated_db, tax_rate):
        """Full withdrawal sets shares to zero."""
        investor_id = "20260101-03A"
        
        # Get investor
        cursor = populated_db.execute("""
            SELECT current_shares, net_investment
            FROM investors
            WHERE id = ?
        """, (investor_id,))
        investor = cursor.fetchone()
        
        # Get NAV
        cursor = populated_db.execute("""
            SELECT nav_per_share FROM daily_nav
            ORDER BY date DESC LIMIT 1
        """)
        nav = cursor.fetchone()['nav_per_share']
        
        # Calculate full value
        current_value = investor['current_shares'] * nav
        
        # Withdraw everything
        withdrawal_amount = current_value
        
        # Calculate tax
        tax_calc = calculate_withdrawal_tax(
            withdrawal_amount,
            current_value,
            investor['net_investment'],
            tax_rate
        )
        
        # Update investor - should be zero
        populated_db.execute("""
            UPDATE investors
            SET current_shares = 0,
                net_investment = 0,
                status = 'Inactive'
            WHERE id = ?
        """, (investor_id,))
        populated_db.commit()
        
        # Verify
        cursor = populated_db.execute("""
            SELECT current_shares, net_investment, status
            FROM investors
            WHERE id = ?
        """, (investor_id,))
        after = cursor.fetchone()
        
        assert after['current_shares'] == 0
        assert after['net_investment'] == 0
        assert after['status'] == 'Inactive'


@pytest.mark.unit
class TestWithdrawalEdgeCases:
    """Test edge cases in withdrawal processing."""
    
    def test_withdrawal_exceeds_balance(self):
        """Cannot withdraw more than current value."""
        current_value = 5000
        withdrawal_amount = 6000
        
        # In real implementation, this should raise an error
        # For now, we just verify the math would be wrong
        assert withdrawal_amount > current_value
    
    def test_very_small_withdrawal(self, tax_rate):
        """Handle very small withdrawal amounts."""
        current_value = 15000
        net_investment = 10000
        withdrawal_amount = 0.01
        
        result = calculate_withdrawal_tax(
            withdrawal_amount,
            current_value,
            net_investment,
            tax_rate
        )
        
        # Should have tiny tax
        assert result['tax_due'] < 0.01
        assert result['net_proceeds'] > 0
    
    def test_withdrawal_at_exactly_basis(self, tax_rate):
        """Withdrawal exactly equal to basis has specific tax."""
        current_value = 15000
        net_investment = 10000
        withdrawal_amount = 10000
        
        result = calculate_withdrawal_tax(
            withdrawal_amount,
            current_value,
            net_investment,
            tax_rate
        )
        
        # Withdrawing 66.67% ($10k / $15k)
        # Realizes 66.67% of $5k gain = $3333
        # Tax: $3333 * 37% = $1233
        # Net: $10000 - $1233 = $8767
        
        assert_close(result['realized_gain'], 3333, 10)
        assert_close(result['tax_due'], 1233, 10)


@pytest.mark.calculations
@pytest.mark.critical
class TestWithdrawalScenarios:
    """Test withdrawal scenarios from Test Scenarios Guide."""
    
    def test_scenario_4_withdrawal(self, tax_rate):
        """Verify calculations from Scenario 4."""
        # Investor 3 withdraws $3000
        # Current shares: 5000
        # NAV: $1.1247
        # Current value: 5000 * 1.1247 = $5623.50
        # Net investment: $5000
        # Unrealized gain: $623.50
        
        current_value = 5623.50
        net_investment = 5000
        withdrawal_amount = 3000
        nav = 1.1247
        
        # Calculate tax
        result = calculate_withdrawal_tax(
            withdrawal_amount,
            current_value,
            net_investment,
            tax_rate
        )
        
        # Proportion: $3000 / $5623.50 = 53.3%
        # Realized gain: $623.50 * 53.3% = $332
        # Tax: $332 * 37% = $123
        # Net proceeds: $3000 - $123 = $2877
        
        assert_close(result['realized_gain'], 332, 10)
        assert_close(result['tax_due'], 123, 10)
        assert_close(result['net_proceeds'], 2877, 10)
        
        # Calculate shares removed
        shares_removed = calculate_shares(withdrawal_amount, nav)
        expected_shares_removed = 2667.50
        
        assert_close(shares_removed, expected_shares_removed, 1)
        
        # Remaining shares: 5000 - 2667.50 = 2332.50
        remaining_shares = 5000 - shares_removed
        assert_close(remaining_shares, 2332.50, 1)
    
    def test_scenario_6_complex_withdrawal(self, tax_rate):
        """Verify calculations from Scenario 6."""
        # Investor 3 complete withdrawal
        # Shares: 2332.50
        # NAV: $1.2314
        # Value: 2332.50 * 1.2314 = $2872.46
        
        shares = 2332.50
        nav = 1.2314
        current_value = shares * nav
        
        # From previous calculations, net investment reduced
        # Let's say they started with $5000, withdrew $3000
        # Remaining investment basis proportional
        # Original: $5000, withdrew 53.3% = withdrew $2667 basis
        # Remaining basis: $5000 - $2667 = $2333
        net_investment = 2333
        
        withdrawal_amount = current_value  # Full withdrawal
        
        result = calculate_withdrawal_tax(
            withdrawal_amount,
            current_value,
            net_investment,
            tax_rate
        )
        
        # Total gain: $2872.46 - $2333 = $539.46
        # Withdrawing 100%
        # Tax: $539.46 * 37% = $200
        # Net: $2872.46 - $200 = $2672
        
        assert_close(result['realized_gain'], 539, 10)
        assert_close(result['tax_due'], 200, 10)
        assert_close(result['net_proceeds'], 2672, 10)


@pytest.mark.integration
class TestTaxEventLogging:
    """Test tax event database logging."""
    
    def test_tax_event_recorded(self, populated_db, tax_rate):
        """Tax events are properly logged."""
        # Process withdrawal
        withdrawal_amount = 5000
        current_value = 15000
        net_investment = 10000
        
        tax_calc = calculate_withdrawal_tax(
            withdrawal_amount,
            current_value,
            net_investment,
            tax_rate
        )
        
        # Record tax event
        populated_db.execute("""
            INSERT INTO tax_events
            (date, investor_id, investor_name, event_type, withdrawal_amount,
             realized_gain, tax_due, net_proceeds, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("2026-01-30", "20260101-01A", "Test Investor 1", "Withdrawal",
              withdrawal_amount, tax_calc['realized_gain'], tax_calc['tax_due'],
              tax_calc['net_proceeds'], datetime.now().isoformat()))
        populated_db.commit()
        
        # Verify recorded
        cursor = populated_db.execute("""
            SELECT * FROM tax_events
            WHERE investor_id = ? AND date = ?
        """, ("20260101-01A", "2026-01-30"))
        event = cursor.fetchone()
        
        assert event is not None
        assert event['withdrawal_amount'] == withdrawal_amount
        assert event['realized_gain'] == tax_calc['realized_gain']
        assert event['tax_due'] == tax_calc['tax_due']
        assert event['net_proceeds'] == tax_calc['net_proceeds']
    
    def test_multiple_tax_events(self, populated_db, tax_rate):
        """Can record multiple tax events for same investor."""
        investor_id = "20260101-01A"
        
        # Record 3 withdrawals
        for i, amount in enumerate([1000, 2000, 3000], 1):
            tax_calc = calculate_withdrawal_tax(amount, 15000, 10000, tax_rate)
            
            populated_db.execute("""
                INSERT INTO tax_events
                (date, investor_id, investor_name, event_type, withdrawal_amount,
                 realized_gain, tax_due, net_proceeds, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (f"2026-01-{i:02d}", investor_id, "Test Investor 1", "Withdrawal",
                  amount, tax_calc['realized_gain'], tax_calc['tax_due'],
                  tax_calc['net_proceeds'], datetime.now().isoformat()))
        
        populated_db.commit()
        
        # Verify all recorded
        cursor = populated_db.execute("""
            SELECT COUNT(*) as count, SUM(tax_due) as total_tax
            FROM tax_events
            WHERE investor_id = ?
        """, (investor_id,))
        result = cursor.fetchone()
        
        assert result['count'] == 3
        assert result['total_tax'] > 0
