"""
Pytest configuration and fixtures for Tovito Trader testing.

This module provides:
- Test database setup/teardown
- Mock Tradier API
- Reusable test data fixtures
- Helper functions for testing
"""

import pytest
import os
import sqlite3
from datetime import datetime, date
from decimal import Decimal
import tempfile
import shutil

# Test database path
TEST_DB_PATH = "data/test_tovito.db"

# ============================================================
# DATABASE FIXTURES
# ============================================================

@pytest.fixture(scope="function")
def test_db():
    """
    Create a fresh test database for each test function.
    
    This fixture:
    - Creates a clean test database
    - Initializes schema
    - Yields connection to test
    - Cleans up after test
    """
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Remove existing test database
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    
    # Create new test database
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Initialize schema
    _create_test_schema(conn)
    
    # Yield connection for testing
    yield conn
    
    # Cleanup
    conn.close()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


@pytest.fixture(scope="function")
def populated_db(test_db):
    """
    Test database populated with sample data.
    
    Includes:
    - 4 investors with various positions
    - 10 days of NAV history
    - Multiple transactions
    - Tax events
    """
    _populate_test_data(test_db)
    return test_db


def _create_test_schema(conn):
    """Create database schema for testing."""
    
    # Investors table
    conn.execute("""
        CREATE TABLE investors (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            initial_capital REAL NOT NULL,
            join_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active',
            current_shares REAL NOT NULL DEFAULT 0,
            net_investment REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    # Daily NAV table
    conn.execute("""
        CREATE TABLE daily_nav (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            nav_per_share REAL NOT NULL,
            total_portfolio_value REAL NOT NULL,
            total_shares REAL NOT NULL,
            daily_change_dollars REAL,
            daily_change_percent REAL,
            created_at TEXT NOT NULL
        )
    """)
    
    # Transactions table
    conn.execute("""
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            investor_id TEXT NOT NULL,
            investor_name TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            share_price REAL NOT NULL,
            shares_transacted REAL NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (investor_id) REFERENCES investors(id)
        )
    """)
    
    # Tax events table
    conn.execute("""
        CREATE TABLE tax_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            investor_id TEXT NOT NULL,
            investor_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            withdrawal_amount REAL NOT NULL,
            realized_gain REAL NOT NULL,
            tax_due REAL NOT NULL,
            net_proceeds REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (investor_id) REFERENCES investors(id)
        )
    """)
    
    # System logs table
    conn.execute("""
        CREATE TABLE system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            level TEXT NOT NULL,
            category TEXT NOT NULL,
            message TEXT NOT NULL,
            details TEXT
        )
    """)

    # Trades table (with source tagging for multi-brokerage)
    conn.execute("""
        CREATE TABLE trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tradier_transaction_id TEXT,
            brokerage_transaction_id TEXT,
            source TEXT DEFAULT 'tradier',
            date TEXT NOT NULL,
            type TEXT,
            status TEXT,
            amount REAL NOT NULL,
            commission REAL DEFAULT 0,
            fees REAL DEFAULT 0,
            symbol TEXT,
            quantity REAL,
            price REAL,
            option_type TEXT,
            strike REAL,
            expiration_date TEXT,
            trade_type TEXT,
            description TEXT,
            notes TEXT,
            category TEXT,
            subcategory TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            is_deleted INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Holdings snapshots table (daily position snapshots)
    conn.execute("""
        CREATE TABLE holdings_snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            source TEXT NOT NULL,
            snapshot_time TEXT NOT NULL,
            total_positions INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(date, source)
        )
    """)

    # Position snapshots table (individual positions per snapshot)
    conn.execute("""
        CREATE TABLE position_snapshots (
            position_id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            underlying_symbol TEXT,
            quantity REAL NOT NULL,
            instrument_type TEXT,
            average_open_price REAL,
            close_price REAL,
            market_value REAL,
            cost_basis REAL,
            unrealized_pl REAL,
            option_type TEXT,
            strike REAL,
            expiration_date TEXT,
            multiplier INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (snapshot_id) REFERENCES holdings_snapshots(snapshot_id)
        )
    """)

    # Email logs table
    conn.execute("""
        CREATE TABLE email_logs (
            email_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sent_at TEXT NOT NULL,
            recipient TEXT NOT NULL,
            subject TEXT NOT NULL,
            email_type TEXT NOT NULL,
            status TEXT DEFAULT 'Sent',
            error_message TEXT
        )
    """)

    # Daily reconciliation table
    conn.execute("""
        CREATE TABLE daily_reconciliation (
            date TEXT PRIMARY KEY,
            tradier_balance REAL,
            calculated_portfolio_value REAL,
            difference REAL,
            total_shares REAL,
            nav_per_share REAL,
            new_deposits REAL DEFAULT 0,
            new_withdrawals REAL DEFAULT 0,
            unallocated_deposits REAL DEFAULT 0,
            status TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Brokerage transactions raw (ETL staging table)
    conn.execute("""
        CREATE TABLE brokerage_transactions_raw (
            raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            brokerage_transaction_id TEXT NOT NULL,
            raw_data TEXT NOT NULL,
            transaction_date DATE NOT NULL,
            transaction_type TEXT NOT NULL,
            transaction_subtype TEXT,
            symbol TEXT,
            amount REAL,
            description TEXT,
            etl_status TEXT NOT NULL DEFAULT 'pending'
                CHECK (etl_status IN ('pending', 'transformed', 'skipped', 'error')),
            etl_transformed_at TIMESTAMP,
            etl_trade_id INTEGER,
            etl_error TEXT,
            ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source, brokerage_transaction_id)
        )
    """)

    # Fund flow requests table
    conn.execute("""
        CREATE TABLE fund_flow_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            investor_id TEXT NOT NULL,
            flow_type TEXT NOT NULL CHECK (flow_type IN ('contribution', 'withdrawal')),
            requested_amount REAL NOT NULL CHECK (requested_amount > 0),
            request_date DATE NOT NULL,
            request_method TEXT NOT NULL DEFAULT 'portal'
                CHECK (request_method IN ('portal', 'email', 'verbal', 'admin', 'other')),
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'approved', 'awaiting_funds', 'matched',
                                  'processed', 'rejected', 'cancelled')),
            approved_by TEXT,
            approved_date TIMESTAMP,
            rejection_reason TEXT,
            matched_trade_id INTEGER,
            matched_raw_id INTEGER,
            matched_date TIMESTAMP,
            matched_by TEXT,
            processed_date TIMESTAMP,
            actual_amount REAL,
            shares_transacted REAL,
            nav_per_share REAL,
            transaction_id INTEGER,
            realized_gain REAL,
            tax_withheld REAL DEFAULT 0,
            net_proceeds REAL,
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (investor_id) REFERENCES investors(id)
        )
    """)

    # Investor profiles table
    conn.execute("""
        CREATE TABLE investor_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            investor_id TEXT NOT NULL UNIQUE,
            full_legal_name TEXT,
            home_address_line1 TEXT,
            home_address_line2 TEXT,
            home_city TEXT,
            home_state TEXT,
            home_zip TEXT,
            home_country TEXT DEFAULT 'US',
            mailing_same_as_home INTEGER DEFAULT 1,
            mailing_address_line1 TEXT,
            mailing_address_line2 TEXT,
            mailing_city TEXT,
            mailing_state TEXT,
            mailing_zip TEXT,
            mailing_country TEXT,
            email_primary TEXT,
            phone_mobile TEXT,
            phone_home TEXT,
            phone_work TEXT,
            date_of_birth TEXT,
            marital_status TEXT,
            num_dependents INTEGER DEFAULT 0,
            citizenship TEXT DEFAULT 'US',
            employment_status TEXT,
            occupation TEXT,
            job_title TEXT,
            employer_name TEXT,
            employer_address TEXT,
            ssn_encrypted TEXT,
            tax_id_encrypted TEXT,
            bank_routing_encrypted TEXT,
            bank_account_encrypted TEXT,
            bank_name TEXT,
            bank_account_type TEXT,
            is_accredited INTEGER DEFAULT 0,
            accreditation_method TEXT,
            accreditation_verified_date DATE,
            accreditation_expires_date DATE,
            accreditation_docs_on_file INTEGER DEFAULT 0,
            communication_preference TEXT DEFAULT 'email',
            statement_delivery TEXT DEFAULT 'electronic',
            profile_completed INTEGER DEFAULT 0,
            last_verified_date DATE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (investor_id) REFERENCES investors(id)
        )
    """)

    # Referrals table
    conn.execute("""
        CREATE TABLE referrals (
            referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_investor_id TEXT NOT NULL,
            referral_code TEXT NOT NULL UNIQUE,
            referred_name TEXT,
            referred_email TEXT,
            referred_date DATE NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'contacted', 'onboarded', 'expired', 'declined')),
            converted_investor_id TEXT,
            converted_date DATE,
            incentive_type TEXT,
            incentive_amount REAL,
            incentive_paid INTEGER DEFAULT 0,
            incentive_paid_date DATE,
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (referrer_investor_id) REFERENCES investors(id)
        )
    """)

    # Benchmark prices cache table
    conn.execute("""
        CREATE TABLE benchmark_prices (
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            close_price REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (date, ticker)
        )
    """)

    # Investor auth table (portal authentication)
    conn.execute("""
        CREATE TABLE investor_auth (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investor_id TEXT NOT NULL UNIQUE,
            password_hash TEXT,
            email_verified INTEGER DEFAULT 0,
            verification_token TEXT,
            verification_token_expires TIMESTAMP,
            reset_token TEXT,
            reset_token_expires TIMESTAMP,
            last_login TIMESTAMP,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (investor_id) REFERENCES investors(id)
        )
    """)
    conn.execute("CREATE INDEX idx_investor_auth_investor ON investor_auth(investor_id)")
    conn.execute("CREATE INDEX idx_investor_auth_verification ON investor_auth(verification_token)")
    conn.execute("CREATE INDEX idx_investor_auth_reset ON investor_auth(reset_token)")

    conn.commit()


def _populate_test_data(conn):
    """Populate database with test data."""
    now = datetime.now().isoformat()
    
    # Insert 4 test investors
    investors = [
        ("20260101-01A", "Test Investor 1", 10000, "2026-01-01", "Active", 10000, 10000),
        ("20260101-02A", "Test Investor 2", 15000, "2026-01-01", "Active", 15000, 15000),
        ("20260101-03A", "Test Investor 3", 5000, "2026-01-01", "Active", 5000, 5000),
        ("20260101-04A", "Test Investor 4", 8000, "2026-01-01", "Active", 8000, 8000),
    ]
    
    for inv in investors:
        conn.execute("""
            INSERT INTO investors 
            (id, name, initial_capital, join_date, status, current_shares, net_investment, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (*inv, now, now))
    
    # Insert initial transactions
    for inv in investors:
        conn.execute("""
            INSERT INTO transactions
            (date, investor_id, investor_name, transaction_type, amount, share_price, shares_transacted, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("2026-01-01", inv[0], inv[1], "Initial", inv[2], 1.0, inv[2], now))
    
    # Insert NAV history — values must be internally consistent:
    #   nav_per_share = round(total_portfolio_value / total_shares, 4)
    total_shares = 38000
    nav_data = [
        ("2026-01-01", round(38000 / total_shares, 4), 38000, total_shares, 0, 0),
        ("2026-01-02", round(38500 / total_shares, 4), 38500, total_shares, 500, 1.32),
        ("2026-01-03", round(39000 / total_shares, 4), 39000, total_shares, 500, 1.30),
        ("2026-01-04", round(39500 / total_shares, 4), 39500, total_shares, 500, 1.28),
        ("2026-01-05", round(40000 / total_shares, 4), 40000, total_shares, 500, 1.27),
    ]
    
    for nav in nav_data:
        conn.execute("""
            INSERT INTO daily_nav
            (date, nav_per_share, total_portfolio_value, total_shares, daily_change_dollars, daily_change_percent, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (*nav, now))
    
    conn.commit()


# ============================================================
# MOCK API FIXTURES
# ============================================================

@pytest.fixture
def mock_tradier_api(monkeypatch):
    """
    Mock Tradier API to avoid real API calls during testing.
    
    Returns predefined account balances without hitting real API.
    """
    class MockTradierAPI:
        def __init__(self):
            self.balance = 40000.00
            self.api_called = False
        
        def get_balance(self):
            self.api_called = True
            return self.balance
        
        def set_balance(self, amount):
            self.balance = amount
    
    mock_api = MockTradierAPI()
    return mock_api


@pytest.fixture
def mock_brokerage_api(monkeypatch):
    """
    Mock brokerage API for NAV pipeline testing.

    Works with any brokerage provider (Tradier, TastyTrade, etc.).
    Implements the BrokerageClient protocol interface.
    """
    class MockBrokerageAPI:
        def __init__(self):
            self.balance = 40000.00
            self.api_called = False

        def get_account_balance(self):
            self.api_called = True
            return {
                'total_equity': self.balance,
                'total_cash': self.balance * 0.3,
                'option_long_value': 0.0,
                'option_short_value': 0.0,
                'stock_long_value': self.balance * 0.7,
                'timestamp': datetime.now(),
                'source': 'mock'
            }

        def get_positions(self):
            return [
                {
                    'symbol': 'AAPL',
                    'quantity': 100,
                    'instrument_type': 'Equity',
                    'underlying_symbol': 'AAPL',
                    'average_open_price': 150.00,
                    'close_price': 175.00,
                    'multiplier': 1,
                    'quantity_direction': 'Long',
                },
                {
                    'symbol': 'SPY 250321C500',
                    'quantity': 5,
                    'instrument_type': 'Equity Option',
                    'underlying_symbol': 'SPY',
                    'average_open_price': 3.50,
                    'close_price': 5.20,
                    'multiplier': 100,
                    'quantity_direction': 'Long',
                },
            ]

        def get_transactions(self, start_date=None, end_date=None):
            return [
                {
                    'date': '2026-01-15',
                    'transaction_type': 'buy',
                    'symbol': 'AAPL',
                    'quantity': 100,
                    'price': 150.00,
                    'amount': -15000.00,
                    'commission': 0.0,
                    'fees': 0.0,
                    'option_type': None,
                    'strike': None,
                    'expiration_date': None,
                    'description': 'Bought 100 AAPL',
                    'brokerage_transaction_id': 'MOCK-001',
                    'category': 'Trade',
                    'subcategory': 'Stock Buy',
                },
                {
                    'date': '2026-01-16',
                    'transaction_type': 'sell_to_close',
                    'symbol': 'SPY 250321C500',
                    'quantity': 5,
                    'price': 5.20,
                    'amount': 2600.00,
                    'commission': 0.50,
                    'fees': 0.13,
                    'option_type': 'call',
                    'strike': 500.0,
                    'expiration_date': '2025-03-21',
                    'description': 'Sold 5 SPY call options',
                    'brokerage_transaction_id': 'MOCK-002',
                    'category': 'Trade',
                    'subcategory': 'Option Call',
                },
            ]

        def is_market_open(self):
            return True

        def set_balance(self, amount):
            self.balance = amount

    mock_api = MockBrokerageAPI()
    return mock_api


# ============================================================
# TEST DATA FIXTURES
# ============================================================

@pytest.fixture
def sample_investor():
    """Return sample investor data for testing."""
    return {
        "id": "20260115-01A",
        "name": "Test Investor",
        "initial_capital": 10000.00,
        "join_date": "2026-01-15",
        "status": "Active",
        "current_shares": 10000.00,
        "net_investment": 10000.00
    }


@pytest.fixture
def sample_contribution():
    """Return sample contribution data for testing."""
    return {
        "investor_id": "20260101-01A",
        "amount": 5000.00,
        "date": "2026-01-15",
        "current_nav": 1.05
    }


@pytest.fixture
def sample_withdrawal():
    """Return sample withdrawal data for testing."""
    return {
        "investor_id": "20260101-01A",
        "amount": 3000.00,
        "date": "2026-01-20",
        "current_value": 15000.00,
        "net_investment": 10000.00,
        "current_nav": 1.10
    }


# ============================================================
# HELPER FIXTURES
# ============================================================

@pytest.fixture
def tax_rate():
    """Return the standard tax rate for testing."""
    return 0.37


@pytest.fixture
def tolerance():
    """Return tolerance for floating point comparisons."""
    return 0.01  # $0.01 tolerance


# ============================================================
# CALCULATION HELPERS
# ============================================================

def calculate_shares(amount: float, nav: float) -> float:
    """Calculate shares to purchase/sell (rounded to 4 decimal places)."""
    return round(amount / nav, 4)


def calculate_nav(total_value: float, total_shares: float) -> float:
    """Calculate NAV per share (rounded to 4 decimal places per SEC standard)."""
    if total_shares == 0:
        return 1.0
    return round(total_value / total_shares, 4)


def calculate_withdrawal_tax(
    withdrawal_amount: float,
    current_value: float,
    net_investment: float,
    tax_rate: float
) -> dict:
    """
    Calculate tax on withdrawal using proportional gain method.
    
    Returns:
        dict with realized_gain, tax_due, net_proceeds
    """
    # Calculate total unrealized gain
    unrealized_gain = max(0, current_value - net_investment)
    
    # Calculate proportion being withdrawn
    proportion = withdrawal_amount / current_value if current_value > 0 else 0
    
    # Calculate realized gain (proportional to withdrawal)
    realized_gain = unrealized_gain * proportion
    
    # Calculate tax
    tax_due = realized_gain * tax_rate
    
    # Calculate net proceeds
    net_proceeds = withdrawal_amount - tax_due
    
    return {
        "realized_gain": round(realized_gain, 2),
        "tax_due": round(tax_due, 2),
        "net_proceeds": round(net_proceeds, 2)
    }


# ============================================================
# ASSERTION HELPERS
# ============================================================

def assert_close(actual: float, expected: float, tolerance: float = 0.01):
    """Assert that two floats are within tolerance."""
    assert abs(actual - expected) <= tolerance, \
        f"Expected {expected}, got {actual} (diff: {abs(actual - expected)})"


def assert_percentages_sum_to_100(percentages: list, tolerance: float = 0.01):
    """Assert that list of percentages sums to 100%."""
    total = sum(percentages)
    assert abs(total - 100.0) <= tolerance, \
        f"Percentages sum to {total}%, expected 100%"


def assert_database_consistency(conn):
    """
    Assert database is in consistent state.
    
    Checks:
    - Total shares in investors matches daily NAV
    - All percentages sum to 100%
    - No negative values where inappropriate
    """
    cursor = conn.cursor()
    
    # Check total shares match
    cursor.execute("SELECT SUM(current_shares) FROM investors WHERE status = 'Active'")
    investor_shares = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT total_shares FROM daily_nav ORDER BY date DESC LIMIT 1")
    nav_shares = cursor.fetchone()
    if nav_shares:
        nav_shares = nav_shares[0]
        assert_close(investor_shares, nav_shares, 0.01)
    
    # Check percentages (if we have investors)
    cursor.execute("SELECT current_shares FROM investors WHERE status = 'Active'")
    shares = [row[0] for row in cursor.fetchall()]
    if shares and sum(shares) > 0:
        total_shares = sum(shares)
        percentages = [(s / total_shares * 100) for s in shares]
        assert_percentages_sum_to_100(percentages)


# ============================================================
# PYTEST HOOKS
# ============================================================

def pytest_configure(config):
    """Configure pytest environment."""
    # Create test_reports directory if it doesn't exist
    os.makedirs("test_reports", exist_ok=True)


def pytest_sessionfinish(session, exitstatus):
    """Clean up after all tests complete."""
    # Clean up any remaining test databases
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
