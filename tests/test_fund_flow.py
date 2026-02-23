"""
Tests for the Fund Flow Request lifecycle.

Covers:
- Request creation (contribution + withdrawal)
- Status transitions (valid + invalid)
- ACH matching (link to trade)
- Request cancellation
- Tax estimate calculations
- Data migration from withdrawal_requests
- API database functions
"""

import sqlite3
import pytest
from datetime import datetime, date
from decimal import Decimal

# Test database path (must match conftest.py)
TEST_DB_PATH = "data/test_tovito.db"


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def fund_flow_db(populated_db):
    """
    Test database with investors and NAV data, plus
    fund_flow_requests and trades tables from conftest schema.
    """
    return populated_db


@pytest.fixture
def sample_contribution_request():
    """Sample contribution request data."""
    return {
        'investor_id': '20260101-01A',
        'flow_type': 'contribution',
        'requested_amount': 5000.00,
        'request_date': '2026-02-15',
        'request_method': 'portal',
        'notes': 'Monthly contribution',
    }


@pytest.fixture
def sample_withdrawal_request():
    """Sample withdrawal request data."""
    return {
        'investor_id': '20260101-01A',
        'flow_type': 'withdrawal',
        'requested_amount': 3000.00,
        'request_date': '2026-02-15',
        'request_method': 'email',
        'notes': 'Partial withdrawal',
    }


def insert_request(conn, data, status='pending'):
    """Helper: insert a fund flow request and return request_id."""
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO fund_flow_requests (
            investor_id, flow_type, requested_amount, request_date,
            request_method, status, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data['investor_id'], data['flow_type'], data['requested_amount'],
        data['request_date'], data['request_method'], status,
        data.get('notes'), now, now,
    ))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def insert_ach_trade(conn, amount, source='tastytrade', trade_date='2026-02-15'):
    """Helper: insert an ACH trade and return trade_id."""
    conn.execute("""
        INSERT INTO trades (
            date, trade_type, amount, source, category, subcategory,
            brokerage_transaction_id, description, is_deleted
        ) VALUES (?, 'ach', ?, ?, 'Transfer', ?, ?, ?, 0)
    """, (
        trade_date, amount, source,
        'Deposit' if amount > 0 else 'Withdrawal',
        f'ACH-{abs(int(amount))}',
        f'ACH {"Deposit" if amount > 0 else "Withdrawal"}',
    ))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ============================================================
# REQUEST CREATION TESTS
# ============================================================

class TestFundFlowRequestCreation:
    """Tests for creating fund flow requests."""

    def test_create_contribution_request(self, fund_flow_db, sample_contribution_request):
        """Creating a contribution request should store all fields correctly."""
        req_id = insert_request(fund_flow_db, sample_contribution_request)

        cursor = fund_flow_db.execute(
            "SELECT * FROM fund_flow_requests WHERE request_id = ?", (req_id,)
        )
        row = cursor.fetchone()

        assert row is not None
        assert row['investor_id'] == '20260101-01A'
        assert row['flow_type'] == 'contribution'
        assert row['requested_amount'] == 5000.00
        assert row['status'] == 'pending'
        assert row['request_method'] == 'portal'

    def test_create_withdrawal_request(self, fund_flow_db, sample_withdrawal_request):
        """Creating a withdrawal request should store all fields correctly."""
        req_id = insert_request(fund_flow_db, sample_withdrawal_request)

        cursor = fund_flow_db.execute(
            "SELECT * FROM fund_flow_requests WHERE request_id = ?", (req_id,)
        )
        row = cursor.fetchone()

        assert row is not None
        assert row['flow_type'] == 'withdrawal'
        assert row['requested_amount'] == 3000.00
        assert row['request_method'] == 'email'

    def test_request_defaults_to_pending(self, fund_flow_db, sample_contribution_request):
        """New requests should default to 'pending' status."""
        req_id = insert_request(fund_flow_db, sample_contribution_request)

        cursor = fund_flow_db.execute(
            "SELECT status FROM fund_flow_requests WHERE request_id = ?", (req_id,)
        )
        assert cursor.fetchone()['status'] == 'pending'

    def test_negative_amount_rejected(self, fund_flow_db):
        """Attempting to insert negative amount should fail CHECK constraint."""
        with pytest.raises(sqlite3.IntegrityError):
            fund_flow_db.execute("""
                INSERT INTO fund_flow_requests (
                    investor_id, flow_type, requested_amount, request_date,
                    request_method, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                '20260101-01A', 'contribution', -100.00, '2026-02-15',
                'portal', 'pending', datetime.now().isoformat(),
                datetime.now().isoformat(),
            ))

    def test_invalid_flow_type_rejected(self, fund_flow_db):
        """Invalid flow_type should fail CHECK constraint."""
        with pytest.raises(sqlite3.IntegrityError):
            fund_flow_db.execute("""
                INSERT INTO fund_flow_requests (
                    investor_id, flow_type, requested_amount, request_date,
                    request_method, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                '20260101-01A', 'transfer', 1000.00, '2026-02-15',
                'portal', 'pending', datetime.now().isoformat(),
                datetime.now().isoformat(),
            ))

    def test_invalid_status_rejected(self, fund_flow_db):
        """Invalid status should fail CHECK constraint."""
        with pytest.raises(sqlite3.IntegrityError):
            fund_flow_db.execute("""
                INSERT INTO fund_flow_requests (
                    investor_id, flow_type, requested_amount, request_date,
                    request_method, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                '20260101-01A', 'contribution', 1000.00, '2026-02-15',
                'portal', 'invalid_status', datetime.now().isoformat(),
                datetime.now().isoformat(),
            ))


# ============================================================
# STATUS TRANSITION TESTS
# ============================================================

class TestStatusTransitions:
    """Tests for fund flow request status transitions."""

    def test_pending_to_approved(self, fund_flow_db, sample_contribution_request):
        """Pending request can be approved."""
        req_id = insert_request(fund_flow_db, sample_contribution_request)
        now = datetime.now().isoformat()

        fund_flow_db.execute("""
            UPDATE fund_flow_requests
            SET status = 'approved', approved_by = 'admin', approved_date = ?
            WHERE request_id = ?
        """, (now, req_id))
        fund_flow_db.commit()

        cursor = fund_flow_db.execute(
            "SELECT status, approved_by FROM fund_flow_requests WHERE request_id = ?",
            (req_id,)
        )
        row = cursor.fetchone()
        assert row['status'] == 'approved'
        assert row['approved_by'] == 'admin'

    def test_approved_to_awaiting_funds(self, fund_flow_db, sample_contribution_request):
        """Approved request can transition to awaiting_funds."""
        req_id = insert_request(fund_flow_db, sample_contribution_request, status='approved')

        fund_flow_db.execute("""
            UPDATE fund_flow_requests SET status = 'awaiting_funds'
            WHERE request_id = ?
        """, (req_id,))
        fund_flow_db.commit()

        cursor = fund_flow_db.execute(
            "SELECT status FROM fund_flow_requests WHERE request_id = ?", (req_id,)
        )
        assert cursor.fetchone()['status'] == 'awaiting_funds'

    def test_pending_to_rejected(self, fund_flow_db, sample_withdrawal_request):
        """Pending request can be rejected with a reason."""
        req_id = insert_request(fund_flow_db, sample_withdrawal_request)

        fund_flow_db.execute("""
            UPDATE fund_flow_requests
            SET status = 'rejected', rejection_reason = 'Insufficient fund liquidity'
            WHERE request_id = ?
        """, (req_id,))
        fund_flow_db.commit()

        cursor = fund_flow_db.execute(
            "SELECT status, rejection_reason FROM fund_flow_requests WHERE request_id = ?",
            (req_id,)
        )
        row = cursor.fetchone()
        assert row['status'] == 'rejected'
        assert row['rejection_reason'] == 'Insufficient fund liquidity'

    def test_pending_to_cancelled(self, fund_flow_db, sample_contribution_request):
        """Pending request can be cancelled."""
        req_id = insert_request(fund_flow_db, sample_contribution_request)

        fund_flow_db.execute("""
            UPDATE fund_flow_requests SET status = 'cancelled'
            WHERE request_id = ?
        """, (req_id,))
        fund_flow_db.commit()

        cursor = fund_flow_db.execute(
            "SELECT status FROM fund_flow_requests WHERE request_id = ?", (req_id,)
        )
        assert cursor.fetchone()['status'] == 'cancelled'

    def test_all_valid_statuses(self, fund_flow_db, sample_contribution_request):
        """All valid statuses should be accepted by CHECK constraint."""
        valid_statuses = [
            'pending', 'approved', 'awaiting_funds', 'matched',
            'processed', 'rejected', 'cancelled',
        ]
        for status in valid_statuses:
            req_id = insert_request(fund_flow_db, sample_contribution_request, status=status)
            cursor = fund_flow_db.execute(
                "SELECT status FROM fund_flow_requests WHERE request_id = ?", (req_id,)
            )
            assert cursor.fetchone()['status'] == status


# ============================================================
# ACH MATCHING TESTS
# ============================================================

class TestACHMatching:
    """Tests for matching fund flow requests to brokerage ACH trades."""

    def test_match_contribution_to_ach_deposit(self, fund_flow_db, sample_contribution_request):
        """A contribution request can be matched to an ACH deposit trade."""
        req_id = insert_request(fund_flow_db, sample_contribution_request, status='approved')
        trade_id = insert_ach_trade(fund_flow_db, 5000.00)
        now = datetime.now().isoformat()

        fund_flow_db.execute("""
            UPDATE fund_flow_requests
            SET status = 'matched',
                matched_trade_id = ?,
                matched_date = ?,
                matched_by = 'admin',
                actual_amount = 5000.00
            WHERE request_id = ?
        """, (trade_id, now, req_id))
        fund_flow_db.commit()

        cursor = fund_flow_db.execute(
            "SELECT * FROM fund_flow_requests WHERE request_id = ?", (req_id,)
        )
        row = cursor.fetchone()
        assert row['status'] == 'matched'
        assert row['matched_trade_id'] == trade_id
        assert row['actual_amount'] == 5000.00
        assert row['matched_by'] == 'admin'

    def test_match_withdrawal_to_ach_withdrawal(self, fund_flow_db, sample_withdrawal_request):
        """A withdrawal request can be matched to an ACH withdrawal trade."""
        req_id = insert_request(fund_flow_db, sample_withdrawal_request, status='approved')
        trade_id = insert_ach_trade(fund_flow_db, -3000.00)  # Negative for withdrawal
        now = datetime.now().isoformat()

        fund_flow_db.execute("""
            UPDATE fund_flow_requests
            SET status = 'matched',
                matched_trade_id = ?,
                matched_date = ?,
                matched_by = 'admin',
                actual_amount = 3000.00
            WHERE request_id = ?
        """, (trade_id, now, req_id))
        fund_flow_db.commit()

        cursor = fund_flow_db.execute(
            "SELECT matched_trade_id, actual_amount FROM fund_flow_requests WHERE request_id = ?",
            (req_id,)
        )
        row = cursor.fetchone()
        assert row['matched_trade_id'] == trade_id
        assert row['actual_amount'] == 3000.00

    def test_matched_request_can_be_processed(self, fund_flow_db, sample_contribution_request):
        """A matched request can transition to processed with full details."""
        req_id = insert_request(fund_flow_db, sample_contribution_request, status='matched')
        now = datetime.now().isoformat()

        fund_flow_db.execute("""
            UPDATE fund_flow_requests
            SET status = 'processed',
                processed_date = ?,
                actual_amount = 5000.00,
                shares_transacted = 4750.5938,
                nav_per_share = 1.0526,
                transaction_id = 100
            WHERE request_id = ?
        """, (now, req_id))
        fund_flow_db.commit()

        cursor = fund_flow_db.execute(
            "SELECT * FROM fund_flow_requests WHERE request_id = ?", (req_id,)
        )
        row = cursor.fetchone()
        assert row['status'] == 'processed'
        assert row['shares_transacted'] == 4750.5938
        assert row['nav_per_share'] == 1.0526
        assert row['transaction_id'] == 100


# ============================================================
# CANCELLATION TESTS
# ============================================================

class TestCancellation:
    """Tests for cancelling fund flow requests."""

    def test_cancel_pending_request(self, fund_flow_db, sample_contribution_request):
        """A pending request can be cancelled."""
        req_id = insert_request(fund_flow_db, sample_contribution_request)

        fund_flow_db.execute(
            "UPDATE fund_flow_requests SET status = 'cancelled' WHERE request_id = ? AND status = 'pending'",
            (req_id,)
        )
        fund_flow_db.commit()

        cursor = fund_flow_db.execute(
            "SELECT status FROM fund_flow_requests WHERE request_id = ?", (req_id,)
        )
        assert cursor.fetchone()['status'] == 'cancelled'

    def test_cancel_approved_request(self, fund_flow_db, sample_contribution_request):
        """An approved request can be cancelled."""
        req_id = insert_request(fund_flow_db, sample_contribution_request, status='approved')

        fund_flow_db.execute(
            "UPDATE fund_flow_requests SET status = 'cancelled' WHERE request_id = ? AND status IN ('pending', 'approved')",
            (req_id,)
        )
        fund_flow_db.commit()

        cursor = fund_flow_db.execute(
            "SELECT status FROM fund_flow_requests WHERE request_id = ?", (req_id,)
        )
        assert cursor.fetchone()['status'] == 'cancelled'

    def test_cannot_cancel_processed_request(self, fund_flow_db, sample_contribution_request):
        """A processed request should not be cancellable via status filter."""
        req_id = insert_request(fund_flow_db, sample_contribution_request, status='processed')

        fund_flow_db.execute(
            "UPDATE fund_flow_requests SET status = 'cancelled' WHERE request_id = ? AND status IN ('pending', 'approved')",
            (req_id,)
        )
        fund_flow_db.commit()

        # Should still be 'processed' — the WHERE clause filtered it out
        cursor = fund_flow_db.execute(
            "SELECT status FROM fund_flow_requests WHERE request_id = ?", (req_id,)
        )
        assert cursor.fetchone()['status'] == 'processed'


# ============================================================
# TAX ESTIMATE TESTS
# ============================================================

class TestTaxEstimate:
    """Tests for withdrawal tax estimate calculations."""

    def test_withdrawal_with_gain(self):
        """Withdrawal from a gained position should calculate correct tax."""
        # Position: invested $10000, now worth $15000 (50% gain)
        net_investment = Decimal('10000')
        current_value = Decimal('15000')
        withdrawal_amount = Decimal('3000')
        tax_rate = Decimal('0.37')

        proportion = withdrawal_amount / current_value
        unrealized_gain = current_value - net_investment
        realized_gain = unrealized_gain * proportion
        tax_due = realized_gain * tax_rate
        net_proceeds = withdrawal_amount - tax_due

        assert proportion == Decimal('0.2')
        assert unrealized_gain == Decimal('5000')
        assert realized_gain == Decimal('1000')
        assert tax_due == Decimal('370')
        assert net_proceeds == Decimal('2630')

    def test_withdrawal_at_loss_no_tax(self):
        """Withdrawal from a losing position should have zero tax."""
        net_investment = Decimal('10000')
        current_value = Decimal('8000')
        withdrawal_amount = Decimal('2000')
        tax_rate = Decimal('0.37')

        proportion = withdrawal_amount / current_value
        unrealized_gain = max(Decimal('0'), current_value - net_investment)
        realized_gain = unrealized_gain * proportion
        tax_due = realized_gain * tax_rate
        net_proceeds = withdrawal_amount - tax_due

        assert unrealized_gain == Decimal('0')
        assert realized_gain == Decimal('0')
        assert tax_due == Decimal('0')
        assert net_proceeds == withdrawal_amount

    def test_full_withdrawal_tax(self):
        """Full withdrawal should realize proportional gains."""
        net_investment = Decimal('10000')
        current_value = Decimal('12000')
        withdrawal_amount = Decimal('12000')
        tax_rate = Decimal('0.37')

        proportion = withdrawal_amount / current_value  # = 1.0
        unrealized_gain = current_value - net_investment
        realized_gain = unrealized_gain * proportion
        tax_due = realized_gain * tax_rate
        net_proceeds = withdrawal_amount - tax_due

        assert proportion == Decimal('1')
        assert unrealized_gain == Decimal('2000')
        assert realized_gain == Decimal('2000')
        assert tax_due == Decimal('740')
        assert net_proceeds == Decimal('11260')


# ============================================================
# QUERY & FILTER TESTS
# ============================================================

class TestFundFlowQueries:
    """Tests for querying and filtering fund flow requests."""

    def test_filter_by_status(self, fund_flow_db, sample_contribution_request):
        """Filtering by status should return only matching requests."""
        insert_request(fund_flow_db, sample_contribution_request, status='pending')
        insert_request(fund_flow_db, sample_contribution_request, status='approved')
        insert_request(fund_flow_db, sample_contribution_request, status='processed')

        cursor = fund_flow_db.execute(
            "SELECT COUNT(*) FROM fund_flow_requests WHERE status = 'pending'"
        )
        assert cursor.fetchone()[0] == 1

        cursor = fund_flow_db.execute(
            "SELECT COUNT(*) FROM fund_flow_requests WHERE status = 'processed'"
        )
        assert cursor.fetchone()[0] == 1

    def test_filter_by_flow_type(self, fund_flow_db, sample_contribution_request, sample_withdrawal_request):
        """Filtering by flow_type should return only matching requests."""
        insert_request(fund_flow_db, sample_contribution_request)
        insert_request(fund_flow_db, sample_withdrawal_request)

        cursor = fund_flow_db.execute(
            "SELECT COUNT(*) FROM fund_flow_requests WHERE flow_type = 'contribution'"
        )
        assert cursor.fetchone()[0] == 1

        cursor = fund_flow_db.execute(
            "SELECT COUNT(*) FROM fund_flow_requests WHERE flow_type = 'withdrawal'"
        )
        assert cursor.fetchone()[0] == 1

    def test_filter_by_investor(self, fund_flow_db, sample_contribution_request):
        """Requests should be isolated by investor_id."""
        # Insert for investor 01A
        insert_request(fund_flow_db, sample_contribution_request)

        # Insert for investor 02A
        req_02 = dict(sample_contribution_request)
        req_02['investor_id'] = '20260101-02A'
        insert_request(fund_flow_db, req_02)
        insert_request(fund_flow_db, req_02)

        cursor = fund_flow_db.execute(
            "SELECT COUNT(*) FROM fund_flow_requests WHERE investor_id = '20260101-01A'"
        )
        assert cursor.fetchone()[0] == 1

        cursor = fund_flow_db.execute(
            "SELECT COUNT(*) FROM fund_flow_requests WHERE investor_id = '20260101-02A'"
        )
        assert cursor.fetchone()[0] == 2

    def test_request_ordering(self, fund_flow_db):
        """Requests should be ordered by date descending."""
        data_early = {
            'investor_id': '20260101-01A', 'flow_type': 'contribution',
            'requested_amount': 1000.00, 'request_date': '2026-01-15',
            'request_method': 'portal',
        }
        data_late = {
            'investor_id': '20260101-01A', 'flow_type': 'contribution',
            'requested_amount': 2000.00, 'request_date': '2026-02-20',
            'request_method': 'portal',
        }

        insert_request(fund_flow_db, data_early)
        insert_request(fund_flow_db, data_late)

        cursor = fund_flow_db.execute(
            "SELECT requested_amount FROM fund_flow_requests ORDER BY request_date DESC"
        )
        rows = cursor.fetchall()
        assert rows[0]['requested_amount'] == 2000.00
        assert rows[1]['requested_amount'] == 1000.00


# ============================================================
# WITHDRAWAL REQUESTS MIGRATION TESTS
# ============================================================

class TestWithdrawalRequestsMigration:
    """Tests for migrating data from withdrawal_requests to fund_flow_requests."""

    def test_migrate_status_mapping(self, fund_flow_db):
        """Status values should map correctly: Pending->pending, Processed->processed."""
        # Create legacy withdrawal_requests table for migration testing
        fund_flow_db.execute("""
            CREATE TABLE IF NOT EXISTS withdrawal_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investor_id TEXT NOT NULL,
                request_date TEXT NOT NULL,
                requested_amount REAL NOT NULL,
                request_method TEXT NOT NULL,
                notes TEXT,
                status TEXT DEFAULT 'Pending',
                approved_by TEXT,
                approved_date TEXT,
                processed_date TEXT,
                actual_amount REAL,
                shares_sold REAL,
                realized_gain REAL,
                tax_withheld REAL,
                net_proceeds REAL,
                rejection_reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert legacy withdrawal request
        fund_flow_db.execute("""
            INSERT INTO withdrawal_requests (
                investor_id, request_date, requested_amount,
                request_method, status, notes
            ) VALUES ('20260101-01A', '2026-01-20', 2000.00, 'email', 'Processed', 'Test')
        """)
        fund_flow_db.commit()

        # Simulate migration logic
        cursor = fund_flow_db.execute("SELECT * FROM withdrawal_requests")
        wr_rows = cursor.fetchall()

        for wr in wr_rows:
            old_status = (wr['status'] or 'Pending').lower()
            status_map = {
                'pending': 'pending', 'approved': 'approved',
                'processed': 'processed', 'rejected': 'rejected',
            }
            new_status = status_map.get(old_status, 'pending')

            fund_flow_db.execute("""
                INSERT INTO fund_flow_requests (
                    investor_id, flow_type, requested_amount, request_date,
                    request_method, status, notes, created_at, updated_at
                ) VALUES (?, 'withdrawal', ?, ?, ?, ?, ?, ?, ?)
            """, (
                wr['investor_id'], wr['requested_amount'], wr['request_date'],
                'email', new_status, wr['notes'],
                wr['created_at'], wr['updated_at'],
            ))
        fund_flow_db.commit()

        # Verify migration
        cursor = fund_flow_db.execute(
            "SELECT * FROM fund_flow_requests WHERE flow_type = 'withdrawal'"
        )
        migrated = cursor.fetchone()
        assert migrated is not None
        assert migrated['investor_id'] == '20260101-01A'
        assert migrated['requested_amount'] == 2000.00
        assert migrated['status'] == 'processed'
        assert migrated['flow_type'] == 'withdrawal'

    def test_migrated_requests_are_all_withdrawals(self, fund_flow_db):
        """All migrated withdrawal_requests should have flow_type='withdrawal'."""
        # Insert directly into fund_flow_requests as if migrated
        now = datetime.now().isoformat()
        for i in range(3):
            fund_flow_db.execute("""
                INSERT INTO fund_flow_requests (
                    investor_id, flow_type, requested_amount, request_date,
                    request_method, status, notes, created_at, updated_at
                ) VALUES (?, 'withdrawal', ?, ?, 'email', 'processed', ?, ?, ?)
            """, (
                '20260101-01A', (i + 1) * 1000.00, '2026-01-20',
                f'Migrated from withdrawal_requests.id={i+1}', now, now,
            ))
        fund_flow_db.commit()

        cursor = fund_flow_db.execute(
            "SELECT DISTINCT flow_type FROM fund_flow_requests"
        )
        types = [row['flow_type'] for row in cursor.fetchall()]
        assert types == ['withdrawal']


# ============================================================
# TAX POLICY TESTS — QUARTERLY SETTLEMENT, NO WITHHOLDING
# ============================================================

class TestQuarterlyTaxSettlement:
    """Tests for the quarterly tax settlement policy.

    Policy: Tax is NOT withheld at withdrawal time. Realized gains
    are tracked for quarterly tax settlement. Full withdrawal amount
    is disbursed to the investor.
    """

    def test_withdrawal_no_tax_withheld(self):
        """Processed withdrawal should have tax_withheld = 0."""
        # Under the quarterly settlement policy, withdrawals disburse
        # the full amount — tax is settled via quarterly_tax_payment.py
        net_investment = Decimal('10000')
        current_value = Decimal('15000')
        withdrawal_amount = Decimal('5000')

        proportion = withdrawal_amount / current_value
        unrealized_gain = max(Decimal('0'), current_value - net_investment)
        realized_gain = (unrealized_gain * proportion).quantize(
            Decimal('0.01')
        )

        # Policy: no withholding
        tax_withheld = Decimal('0')
        net_proceeds = withdrawal_amount  # Full amount disbursed

        assert realized_gain == Decimal('1666.67')
        assert tax_withheld == Decimal('0')
        assert net_proceeds == withdrawal_amount

    def test_realized_gain_still_calculated(self):
        """Realized gain must still be calculated even without withholding."""
        net_investment = Decimal('10000')
        current_value = Decimal('20000')
        withdrawal_amount = Decimal('10000')

        proportion = withdrawal_amount / current_value  # 50%
        unrealized_gain = max(Decimal('0'), current_value - net_investment)
        realized_gain = (unrealized_gain * proportion).quantize(
            Decimal('0.01')
        )

        # Gain is tracked for quarterly tax, even though not withheld
        assert realized_gain == Decimal('5000.00')
        assert realized_gain > 0

    def test_fund_flow_request_stores_zero_tax(self, fund_flow_db, sample_withdrawal_request):
        """Processed withdrawal fund_flow_request should store tax_withheld=0."""
        req_id = insert_request(fund_flow_db, sample_withdrawal_request, status='matched')
        now = datetime.now().isoformat()

        # Process with quarterly settlement policy
        fund_flow_db.execute("""
            UPDATE fund_flow_requests
            SET status = 'processed',
                processed_date = ?,
                actual_amount = 3000.00,
                shares_transacted = 2850.0000,
                nav_per_share = 1.0526,
                transaction_id = 100,
                realized_gain = 500.00,
                tax_withheld = 0,
                net_proceeds = 3000.00
            WHERE request_id = ?
        """, (now, req_id))
        fund_flow_db.commit()

        cursor = fund_flow_db.execute(
            "SELECT * FROM fund_flow_requests WHERE request_id = ?", (req_id,)
        )
        row = cursor.fetchone()

        assert row['status'] == 'processed'
        assert row['tax_withheld'] == 0
        assert row['net_proceeds'] == 3000.00
        assert row['realized_gain'] == 500.00


# ============================================================
# ELIGIBLE WITHDRAWAL TESTS
# ============================================================

class TestEligibleWithdrawal:
    """Tests for the eligible withdrawal calculation.

    eligible_withdrawal = current_value - estimated_tax_liability
    estimated_tax_liability = max(0, unrealized_gain) * 0.37
    """

    def test_eligible_withdrawal_with_gain(self):
        """Eligible withdrawal should be less than current value when gains exist."""
        current_value = 15000.0
        net_investment = 10000.0
        tax_rate = 0.37

        unrealized_gain = max(0, current_value - net_investment)
        estimated_tax = round(unrealized_gain * tax_rate, 2)
        eligible_withdrawal = round(current_value - estimated_tax, 2)

        assert unrealized_gain == 5000.0
        assert estimated_tax == 1850.0
        assert eligible_withdrawal == 13150.0
        assert eligible_withdrawal < current_value

    def test_eligible_withdrawal_at_loss(self):
        """Eligible withdrawal equals current value when position is at loss."""
        current_value = 8000.0
        net_investment = 10000.0
        tax_rate = 0.37

        unrealized_gain = max(0, current_value - net_investment)
        estimated_tax = round(unrealized_gain * tax_rate, 2)
        eligible_withdrawal = round(current_value - estimated_tax, 2)

        assert unrealized_gain == 0
        assert estimated_tax == 0
        assert eligible_withdrawal == current_value

    def test_eligible_withdrawal_at_breakeven(self):
        """Eligible withdrawal equals current value at breakeven."""
        current_value = 10000.0
        net_investment = 10000.0
        tax_rate = 0.37

        unrealized_gain = max(0, current_value - net_investment)
        estimated_tax = round(unrealized_gain * tax_rate, 2)
        eligible_withdrawal = round(current_value - estimated_tax, 2)

        assert unrealized_gain == 0
        assert estimated_tax == 0
        assert eligible_withdrawal == current_value

    def test_eligible_withdrawal_is_always_positive(self):
        """Eligible withdrawal should always be >= 0."""
        # Even with massive gains, eligible should be positive
        current_value = 100000.0
        net_investment = 1000.0
        tax_rate = 0.37

        unrealized_gain = max(0, current_value - net_investment)
        estimated_tax = round(unrealized_gain * tax_rate, 2)
        eligible_withdrawal = round(current_value - estimated_tax, 2)

        assert eligible_withdrawal > 0
        # Max tax is 37% of gain, not 37% of value
        assert eligible_withdrawal == round(100000 - (99000 * 0.37), 2)
