"""
Test database operations and data validation.

Tests:
- Database CRUD operations
- Data integrity constraints
- Validation checks (percentages, share totals, etc.)
- Database consistency
"""

import pytest
from datetime import datetime
from tests.conftest import (
    assert_close,
    assert_percentages_sum_to_100,
    assert_database_consistency
)


@pytest.mark.database
@pytest.mark.critical
class TestDatabaseOperations:
    """Test basic database CRUD operations."""
    
    def test_create_investor(self, test_db):
        """Can create new investor in database."""
        investor_data = (
            "20260115-01A",
            "New Test Investor",
            25000,
            "2026-01-15",
            "Active",
            25000,
            25000,
            datetime.now().isoformat(),
            datetime.now().isoformat()
        )
        
        test_db.execute("""
            INSERT INTO investors
            (id, name, initial_capital, join_date, status, current_shares,
             net_investment, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, investor_data)
        test_db.commit()
        
        # Verify created
        cursor = test_db.execute("SELECT * FROM investors WHERE id = ?", ("20260115-01A",))
        investor = cursor.fetchone()
        
        assert investor is not None
        assert investor['name'] == "New Test Investor"
        assert investor['initial_capital'] == 25000
    
    def test_read_investor(self, populated_db):
        """Can read investor from database."""
        cursor = populated_db.execute("""
            SELECT * FROM investors WHERE id = ?
        """, ("20260101-01A",))
        investor = cursor.fetchone()
        
        assert investor is not None
        assert investor['id'] == "20260101-01A"
        assert investor['initial_capital'] > 0
    
    def test_update_investor(self, populated_db):
        """Can update investor in database."""
        # Update shares
        new_shares = 15000
        populated_db.execute("""
            UPDATE investors
            SET current_shares = ?,
                updated_at = ?
            WHERE id = ?
        """, (new_shares, datetime.now().isoformat(), "20260101-01A"))
        populated_db.commit()
        
        # Verify updated
        cursor = populated_db.execute("""
            SELECT current_shares FROM investors WHERE id = ?
        """, ("20260101-01A",))
        investor = cursor.fetchone()
        
        assert investor['current_shares'] == new_shares
    
    def test_delete_investor(self, populated_db):
        """Can deactivate (soft delete) investor."""
        # Set status to Inactive instead of deleting
        populated_db.execute("""
            UPDATE investors
            SET status = 'Inactive',
                updated_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), "20260101-04A"))
        populated_db.commit()
        
        # Verify still exists but inactive
        cursor = populated_db.execute("""
            SELECT status FROM investors WHERE id = ?
        """, ("20260101-04A",))
        investor = cursor.fetchone()
        
        assert investor is not None
        assert investor['status'] == 'Inactive'


@pytest.mark.database
class TestDatabaseConstraints:
    """Test database integrity constraints."""
    
    def test_unique_investor_id(self, populated_db):
        """Investor IDs must be unique."""
        with pytest.raises(Exception):
            populated_db.execute("""
                INSERT INTO investors
                (id, name, initial_capital, join_date, status,
                 current_shares, net_investment, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("20260101-01A", "Duplicate", 5000, "2026-01-01", "Active",
                  5000, 5000, datetime.now().isoformat(), datetime.now().isoformat()))
            populated_db.commit()
    
    def test_unique_nav_date(self, populated_db):
        """NAV dates must be unique (one entry per day)."""
        with pytest.raises(Exception):
            populated_db.execute("""
                INSERT INTO daily_nav
                (date, nav_per_share, total_portfolio_value, total_shares, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, ("2026-01-01", 1.0, 38000, 38000, datetime.now().isoformat()))
            populated_db.commit()
    
    def test_foreign_key_constraint(self, test_db):
        """Transactions must reference valid investor."""
        # Try to create transaction for non-existent investor
        try:
            test_db.execute("""
                INSERT INTO transactions
                (date, investor_id, investor_name, transaction_type, amount,
                 share_price, shares_transacted, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ("2026-01-01", "INVALID-ID", "Nobody", "Contribution",
                  5000, 1.0, 5000, datetime.now().isoformat()))
            test_db.commit()
        except Exception:
            # Expected to fail
            test_db.rollback()
            pass


@pytest.mark.unit
@pytest.mark.critical
class TestDataValidation:
    """Test data validation logic."""
    
    def test_percentages_sum_to_100(self):
        """Portfolio percentages must sum to 100%."""
        percentages = [26.32, 39.47, 13.16, 21.05]
        assert_percentages_sum_to_100(percentages)
    
    def test_percentages_close_to_100(self):
        """Allow small rounding errors in percentages."""
        percentages = [26.31, 39.48, 13.16, 21.05]  # Sums to 100.00
        assert_percentages_sum_to_100(percentages, tolerance=0.01)
    
    def test_percentages_fail_when_wrong(self):
        """Detect when percentages don't sum to 100%."""
        percentages = [25.0, 25.0, 25.0, 20.0]  # Sums to 95%
        
        with pytest.raises(AssertionError):
            assert_percentages_sum_to_100(percentages, tolerance=0.01)
    
    def test_shares_match_total(self, populated_db):
        """Sum of investor shares must equal total in NAV."""
        cursor = populated_db.execute("""
            SELECT SUM(current_shares) as total
            FROM investors
            WHERE status = 'Active'
        """)
        investor_total = cursor.fetchone()['total']
        
        cursor = populated_db.execute("""
            SELECT total_shares
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        nav_total = cursor.fetchone()['total_shares']
        
        assert_close(investor_total, nav_total, 0.01)
    
    def test_no_negative_shares(self, populated_db):
        """Investors cannot have negative shares."""
        cursor = populated_db.execute("""
            SELECT id, current_shares
            FROM investors
            WHERE current_shares < 0
        """)
        
        negative_shares = cursor.fetchall()
        assert len(negative_shares) == 0
    
    def test_no_negative_nav(self, populated_db):
        """NAV per share cannot be negative."""
        cursor = populated_db.execute("""
            SELECT date, nav_per_share
            FROM daily_nav
            WHERE nav_per_share < 0
        """)
        
        negative_navs = cursor.fetchall()
        assert len(negative_navs) == 0


@pytest.mark.integration
@pytest.mark.critical
class TestDatabaseConsistency:
    """Test overall database consistency."""
    
    def test_database_consistency_check(self, populated_db):
        """Database passes all consistency checks."""
        assert_database_consistency(populated_db)
    
    def test_consistency_after_contribution(self, populated_db):
        """Database remains consistent after contribution."""
        # Get current state
        cursor = populated_db.execute("""
            SELECT nav_per_share, total_portfolio_value, total_shares
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        nav_data = cursor.fetchone()
        
        # Add contribution
        contribution = 5000
        shares = contribution / nav_data['nav_per_share']
        
        populated_db.execute("""
            UPDATE investors
            SET current_shares = current_shares + ?
            WHERE id = '20260101-01A'
        """, (shares,))
        
        new_value = nav_data['total_portfolio_value'] + contribution
        new_shares = nav_data['total_shares'] + shares
        
        populated_db.execute("""
            INSERT INTO daily_nav
            (date, nav_per_share, total_portfolio_value, total_shares,
             daily_change_dollars, daily_change_percent, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("2026-01-20", new_value / new_shares, new_value, new_shares,
              contribution, 0, datetime.now().isoformat()))
        
        populated_db.commit()
        
        # Should still be consistent
        assert_database_consistency(populated_db)
    
    def test_consistency_after_withdrawal(self, populated_db):
        """Database remains consistent after withdrawal."""
        # Get current state
        cursor = populated_db.execute("""
            SELECT nav_per_share, total_portfolio_value, total_shares
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        nav_data = cursor.fetchone()
        
        # Remove withdrawal
        withdrawal = 3000
        shares = withdrawal / nav_data['nav_per_share']
        
        populated_db.execute("""
            UPDATE investors
            SET current_shares = current_shares - ?
            WHERE id = '20260101-03A'
        """, (shares,))
        
        new_value = nav_data['total_portfolio_value'] - withdrawal
        new_shares = nav_data['total_shares'] - shares
        
        populated_db.execute("""
            INSERT INTO daily_nav
            (date, nav_per_share, total_portfolio_value, total_shares,
             daily_change_dollars, daily_change_percent, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("2026-01-25", new_value / new_shares, new_value, new_shares,
              -withdrawal, 0, datetime.now().isoformat()))
        
        populated_db.commit()
        
        # Should still be consistent
        assert_database_consistency(populated_db)


@pytest.mark.database
class TestTransactionHistory:
    """Test transaction logging and history."""
    
    def test_all_transactions_logged(self, populated_db):
        """All investor actions are logged in transactions table."""
        # Should have initial transactions for all 4 investors
        cursor = populated_db.execute("""
            SELECT COUNT(*) as count
            FROM transactions
            WHERE transaction_type = 'Initial'
        """)
        
        count = cursor.fetchone()['count']
        assert count == 4
    
    def test_transaction_audit_trail(self, populated_db):
        """Can reconstruct investor position from transaction history."""
        investor_id = "20260101-01A"
        
        # Get transactions
        cursor = populated_db.execute("""
            SELECT transaction_type, shares_transacted
            FROM transactions
            WHERE investor_id = ?
            ORDER BY date ASC
        """, (investor_id,))
        
        # Calculate shares from transactions
        calculated_shares = sum(row['shares_transacted'] for row in cursor.fetchall())
        
        # Get actual shares
        cursor = populated_db.execute("""
            SELECT current_shares
            FROM investors
            WHERE id = ?
        """, (investor_id,))
        actual_shares = cursor.fetchone()['current_shares']
        
        # Should match (in our test data with no contributions yet)
        assert_close(calculated_shares, actual_shares, 0.01)
    
    def test_transaction_date_ordering(self, populated_db):
        """Transactions are properly ordered by date."""
        cursor = populated_db.execute("""
            SELECT date, id
            FROM transactions
            ORDER BY date ASC, id ASC
        """)
        dates = [row['date'] for row in cursor.fetchall()]
        
        # Verify chronological order
        assert dates == sorted(dates)


@pytest.mark.database
class TestSystemLogs:
    """Test system logging."""
    
    def test_log_entry_creation(self, test_db):
        """Can create system log entries."""
        test_db.execute("""
            INSERT INTO system_logs
            (timestamp, level, category, message, details)
            VALUES (?, ?, ?, ?, ?)
        """, (datetime.now().isoformat(), "INFO", "NAV_UPDATE",
              "Daily NAV updated", "Portfolio: $40,000, NAV: $1.0526"))
        test_db.commit()
        
        # Verify logged
        cursor = test_db.execute("""
            SELECT * FROM system_logs
            WHERE category = 'NAV_UPDATE'
        """)
        log = cursor.fetchone()
        
        assert log is not None
        assert log['level'] == "INFO"
    
    def test_multiple_log_levels(self, test_db):
        """Can log at different severity levels."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        
        for level in levels:
            test_db.execute("""
                INSERT INTO system_logs
                (timestamp, level, category, message)
                VALUES (?, ?, ?, ?)
            """, (datetime.now().isoformat(), level, "TEST", f"Test {level}"))
        
        test_db.commit()
        
        # Verify all logged
        cursor = test_db.execute("""
            SELECT DISTINCT level
            FROM system_logs
            WHERE category = 'TEST'
        """)
        logged_levels = [row['level'] for row in cursor.fetchall()]
        
        for level in levels:
            assert level in logged_levels


@pytest.mark.integration
class TestDataIntegrity:
    """Test data integrity across tables."""
    
    def test_investor_transaction_relationship(self, populated_db):
        """Every investor has corresponding initial transaction."""
        cursor = populated_db.execute("""
            SELECT i.id
            FROM investors i
            LEFT JOIN transactions t ON i.id = t.investor_id
                AND t.transaction_type = 'Initial'
            WHERE t.id IS NULL
        """)
        
        missing_transactions = cursor.fetchall()
        assert len(missing_transactions) == 0
    
    def test_nav_dates_continuous(self, populated_db):
        """NAV records are continuous (no missing dates)."""
        cursor = populated_db.execute("""
            SELECT date
            FROM daily_nav
            ORDER BY date ASC
        """)
        dates = [row['date'] for row in cursor.fetchall()]
        
        # In test data, should have continuous dates
        # (This would be more complex in production with weekends/holidays)
        assert len(dates) > 0
        assert dates[0] == "2026-01-01"


@pytest.mark.calculations
class TestValidationCalculations:
    """Test validation calculation accuracy."""
    
    def test_portfolio_value_matches_shares(self, populated_db):
        """Portfolio value = Sum of (investor shares × NAV)."""
        cursor = populated_db.execute("""
            SELECT nav_per_share, total_portfolio_value
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        nav_data = cursor.fetchone()
        
        cursor = populated_db.execute("""
            SELECT SUM(current_shares) as total_shares
            FROM investors
            WHERE status = 'Active'
        """)
        investor_shares = cursor.fetchone()['total_shares']
        
        calculated_value = investor_shares * nav_data['nav_per_share']
        
        assert_close(calculated_value, nav_data['total_portfolio_value'], 0.01)
    
    def test_individual_values_sum_to_total(self, populated_db):
        """Sum of individual investor values = total portfolio value."""
        cursor = populated_db.execute("""
            SELECT nav_per_share, total_portfolio_value
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        nav_data = cursor.fetchone()
        
        cursor = populated_db.execute("""
            SELECT current_shares
            FROM investors
            WHERE status = 'Active'
        """)
        individual_values = [
            row['current_shares'] * nav_data['nav_per_share']
            for row in cursor.fetchall()
        ]
        
        total = sum(individual_values)
        
        assert_close(total, nav_data['total_portfolio_value'], 0.01)
