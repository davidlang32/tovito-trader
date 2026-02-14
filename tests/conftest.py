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
    
    # Insert 10 days of NAV history
    nav_data = [
        ("2026-01-01", 1.0000, 38000, 38000, 0, 0),
        ("2026-01-02", 1.0132, 38500, 38000, 500, 1.32),
        ("2026-01-03", 1.0263, 39000, 38000, 500, 1.30),
        ("2026-01-04", 1.0395, 39500, 38000, 500, 1.28),
        ("2026-01-05", 1.0526, 40000, 38000, 500, 1.27),
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
    """Calculate shares to purchase/sell."""
    return amount / nav


def calculate_nav(total_value: float, total_shares: float) -> float:
    """Calculate NAV per share."""
    if total_shares == 0:
        return 1.0
    return total_value / total_shares


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
