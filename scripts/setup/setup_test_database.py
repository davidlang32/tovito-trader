"""
Dev/Test Database Setup Script
==============================

Creates a fresh database with synthetic sample data for development
or testing. Uses the same full schema as production (from conftest.py)
but with generated test data only.

Usage:
    python scripts/setup/setup_test_database.py              # Creates dev database
    python scripts/setup/setup_test_database.py --env test    # Creates test database
    python scripts/setup/setup_test_database.py --env dev     # Creates dev database (same as default)
    python scripts/setup/setup_test_database.py --env dev --reset-prospects  # Clear prospect data only
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import os
import sys
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import math

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Database path per environment
ENV_DB_PATHS = {
    'dev': PROJECT_ROOT / 'data' / 'dev_tovito.db',
    'test': PROJECT_ROOT / 'data' / 'test_tovito.db',
}


def create_schema(conn):
    """
    Create the full production-equivalent database schema.

    This mirrors tests/conftest.py _create_test_schema() and must be
    kept in sync with any production schema changes.
    """

    # Investors table (mirrors production schema_v2.py -- PK is investor_id)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS investors (
            investor_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            initial_capital REAL NOT NULL,
            join_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active',
            current_shares REAL NOT NULL DEFAULT 0,
            net_investment REAL NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Daily NAV table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_nav (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            nav_per_share REAL NOT NULL,
            total_portfolio_value REAL NOT NULL,
            total_shares REAL NOT NULL,
            daily_change_dollars REAL,
            daily_change_percent REAL,
            source TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # Transactions table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            investor_id TEXT NOT NULL,
            investor_name TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            share_price REAL NOT NULL,
            shares_transacted REAL NOT NULL,
            reference_id TEXT,
            notes TEXT,
            is_deleted INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (investor_id) REFERENCES investors(investor_id)
        )
    """)

    # Tax events table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tax_events (
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
            FOREIGN KEY (investor_id) REFERENCES investors(investor_id)
        )
    """)

    # System logs table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            level TEXT NOT NULL,
            category TEXT NOT NULL,
            message TEXT NOT NULL,
            details TEXT
        )
    """)

    # Trades table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            brokerage_transaction_id TEXT,
            source TEXT DEFAULT 'tastytrade',
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

    # Holdings snapshots table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS holdings_snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            source TEXT NOT NULL,
            snapshot_time TEXT NOT NULL,
            total_positions INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(date, source)
        )
    """)

    # Position snapshots table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS position_snapshots (
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
        CREATE TABLE IF NOT EXISTS email_logs (
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
        CREATE TABLE IF NOT EXISTS daily_reconciliation (
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
        CREATE TABLE IF NOT EXISTS brokerage_transactions_raw (
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
        CREATE TABLE IF NOT EXISTS fund_flow_requests (
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
            FOREIGN KEY (investor_id) REFERENCES investors(investor_id)
        )
    """)

    # Investor profiles table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS investor_profiles (
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
            FOREIGN KEY (investor_id) REFERENCES investors(investor_id)
        )
    """)

    # Referrals table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
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
            FOREIGN KEY (referrer_investor_id) REFERENCES investors(investor_id)
        )
    """)

    # System config table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TEXT
        )
    """)

    # Alert events table (used by market monitor)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alert_events (
            alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            message TEXT NOT NULL,
            details TEXT,
            acknowledged_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Investor auth table (used by investor portal)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS investor_auth (
            auth_id INTEGER PRIMARY KEY AUTOINCREMENT,
            investor_id TEXT NOT NULL UNIQUE,
            password_hash TEXT,
            email_verified INTEGER DEFAULT 0,
            verification_token TEXT,
            verification_token_expires TIMESTAMP,
            reset_token TEXT,
            reset_token_expires TIMESTAMP,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TIMESTAMP,
            last_login TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (investor_id) REFERENCES investors(investor_id)
        )
    """)

    # Prospects table (with email verification columns)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prospects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            source TEXT DEFAULT 'website',
            status TEXT DEFAULT 'new',
            notes TEXT,
            email_verified INTEGER DEFAULT 0,
            verification_token TEXT,
            verification_token_expires TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Prospect communications table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prospect_communications (
            comm_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER NOT NULL,
            comm_type TEXT NOT NULL,
            subject TEXT,
            body TEXT,
            status TEXT DEFAULT 'sent',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prospect_id) REFERENCES prospects(id)
        )
    """)

    # Prospect access tokens table (gated fund preview)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prospect_access_tokens (
            token_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            last_accessed_at TIMESTAMP,
            access_count INTEGER DEFAULT 0,
            is_revoked INTEGER DEFAULT 0,
            created_by TEXT DEFAULT 'admin',
            FOREIGN KEY (prospect_id) REFERENCES prospects(id)
        )
    """)

    # Benchmark prices cache table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS benchmark_prices (
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            close_price REAL NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (date, ticker)
        )
    """)

    # Plan daily performance table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS plan_daily_performance (
            date TEXT NOT NULL,
            plan_id TEXT NOT NULL,
            market_value REAL NOT NULL DEFAULT 0,
            cost_basis REAL NOT NULL DEFAULT 0,
            unrealized_pl REAL NOT NULL DEFAULT 0,
            allocation_pct REAL NOT NULL DEFAULT 0,
            position_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (date, plan_id)
        )
    """)

    # Audit log table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            table_name TEXT NOT NULL,
            record_id TEXT NOT NULL,
            action TEXT NOT NULL,
            old_values TEXT,
            new_values TEXT
        )
    """)

    # PII access log table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pii_access_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            investor_id TEXT NOT NULL,
            field_name TEXT NOT NULL,
            access_type TEXT NOT NULL CHECK (access_type IN ('read', 'write')),
            performed_by TEXT NOT NULL DEFAULT 'system',
            ip_address TEXT,
            context TEXT
        )
    """)

    conn.commit()


def populate_sample_data(conn):
    """
    Populate the database with realistic synthetic data for dev/test.

    All data is completely synthetic -- no real investor information.
    """
    now = datetime.now().isoformat()

    # --- Test Investors ---
    investors = [
        ("20260101-01A", "Alpha Investor", "alpha@test.com", 10000, "2026-01-01"),
        ("20260101-02A", "Beta Investor", "beta@test.com", 15000, "2026-01-01"),
        ("20260101-03A", "Gamma Investor", "gamma@test.com", 5000, "2026-01-01"),
        ("20260115-01A", "Delta Investor", "delta@test.com", 8000, "2026-01-15"),
    ]

    for inv_id, name, email, capital, join_date in investors:
        conn.execute("""
            INSERT INTO investors
            (investor_id, name, email, initial_capital, join_date, status, current_shares, net_investment, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'Active', ?, ?, ?, ?)
        """, (inv_id, name, email, capital, join_date, capital, capital, now, now))

    # --- Initial Transactions ---
    for inv_id, name, email, capital, join_date in investors:
        conn.execute("""
            INSERT INTO transactions
            (date, investor_id, investor_name, transaction_type, amount, share_price, shares_transacted, created_at)
            VALUES (?, ?, ?, 'Initial', ?, 1.0, ?, ?)
        """, (join_date, inv_id, name, capital, capital, now))

    # --- NAV history from Jan 1 through today ---
    # Generate ~57 trading days of realistic NAV data
    base_date = datetime(2026, 1, 1)
    today = datetime.now()
    total_shares = 30000  # First 3 investors
    nav = 1.0
    nav_data = []
    prev_value = nav * total_shares
    day_count = 0

    d = base_date
    while d <= today:
        if d.weekday() >= 5:  # Skip weekends
            d += timedelta(days=1)
            continue

        # Deterministic growth pattern: mostly up with periodic dips
        # Creates a realistic-looking equity curve
        day_count += 1
        daily_change = 0.004 * math.sin(day_count * 0.3) + 0.002
        # Add some larger moves on specific days
        if day_count % 7 == 0:
            daily_change = -0.008  # Weekly pullback
        elif day_count % 13 == 0:
            daily_change = 0.012  # Strong rally
        nav = round(nav * (1 + daily_change), 4)

        # Add Delta investor shares on Jan 15
        if d >= datetime(2026, 1, 15) and total_shares == 30000:
            total_shares += 8000

        total_value = round(nav * total_shares, 2)
        change_dollars = round(total_value - prev_value, 2) if day_count > 1 else 0
        change_pct = round(daily_change * 100, 2) if day_count > 1 else 0
        prev_value = total_value

        nav_data.append((
            d.strftime("%Y-%m-%d"), nav, total_value, total_shares,
            change_dollars, change_pct,
        ))

        d += timedelta(days=1)

    for nd in nav_data:
        conn.execute("""
            INSERT INTO daily_nav
            (date, nav_per_share, total_portfolio_value, total_shares,
             daily_change_dollars, daily_change_percent, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'tastytrade', ?)
        """, (*nd, now))

    # --- Sample Trades ---
    trades = [
        ("2026-01-02", "buy", "buy", "AAPL", 50, 185.50, -9275.00, "tastytrade", "TT-DEV-001"),
        ("2026-01-03", "buy", "buy_to_open", "SPY 260320C500", 5, 3.20, -1600.00, "tastytrade", "TT-DEV-002"),
        ("2026-01-06", "sell", "sell_to_close", "SPY 260320C500", 5, 4.80, 2400.00, "tastytrade", "TT-DEV-003"),
        ("2026-01-07", "sell", "sell", "AAPL", 25, 190.00, 4750.00, "tastytrade", "TT-DEV-004"),
        ("2026-01-10", "buy", "buy", "MSFT", 30, 420.00, -12600.00, "tastytrade", "TT-DEV-005"),
        ("2026-01-15", "buy", "buy", "SGOV", 100, 100.50, -10050.00, "tastytrade", "TT-DEV-006"),
        ("2026-01-22", "buy", "buy", "SPY", 20, 590.00, -11800.00, "tastytrade", "TT-DEV-007"),
        ("2026-02-03", "sell", "sell", "MSFT", 15, 435.00, 6525.00, "tastytrade", "TT-DEV-008"),
        ("2026-02-10", "buy", "buy_to_open", "QQQ 260320C520", 10, 5.50, -5500.00, "tastytrade", "TT-DEV-009"),
    ]

    for t in trades:
        conn.execute("""
            INSERT INTO trades
            (date, type, trade_type, symbol, quantity, price, amount,
             source, brokerage_transaction_id, category, subcategory)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Trade', 'Stock')
        """, t)

    # --- Benchmark Prices (SPY, QQQ, BTC-USD) ---
    # Generate synthetic benchmark data matching NAV dates
    spy_base, qqq_base, btc_base = 590.0, 520.0, 95000.0
    d = base_date
    day_idx = 0
    while d <= today:
        if d.weekday() >= 5:
            d += timedelta(days=1)
            continue

        day_idx += 1
        date_str = d.strftime("%Y-%m-%d")

        # Correlated but different movement patterns
        spy_change = 0.003 * math.sin(day_idx * 0.25) + 0.0015
        qqq_change = 0.004 * math.sin(day_idx * 0.28) + 0.0018
        btc_change = 0.008 * math.sin(day_idx * 0.2) + 0.002

        spy_base = round(spy_base * (1 + spy_change), 2)
        qqq_base = round(qqq_base * (1 + qqq_change), 2)
        btc_base = round(btc_base * (1 + btc_change), 2)

        for ticker, price in [("SPY", spy_base), ("QQQ", qqq_base), ("BTC-USD", btc_base)]:
            conn.execute("""
                INSERT INTO benchmark_prices (date, ticker, close_price)
                VALUES (?, ?, ?)
            """, (date_str, ticker, price))

        d += timedelta(days=1)

    # --- Plan Daily Performance ---
    # Generate plan allocation data matching NAV dates
    d = base_date
    while d <= today:
        if d.weekday() >= 5:
            d += timedelta(days=1)
            continue

        date_str = d.strftime("%Y-%m-%d")
        # Simulate plan allocations (roughly: 30% cash, 40% ETF, 30% plan A)
        total_val = total_shares * nav  # approximate
        cash_val = round(total_val * 0.30, 2)
        etf_val = round(total_val * 0.40, 2)
        plan_a_val = round(total_val * 0.30, 2)

        plans = [
            (date_str, "plan_cash", cash_val, cash_val * 0.99, cash_val * 0.01, 30.0, 2),
            (date_str, "plan_etf", etf_val, etf_val * 0.95, etf_val * 0.05, 40.0, 3),
            (date_str, "plan_a", plan_a_val, plan_a_val * 0.90, plan_a_val * 0.10, 30.0, 4),
        ]

        for p in plans:
            conn.execute("""
                INSERT INTO plan_daily_performance
                (date, plan_id, market_value, cost_basis, unrealized_pl, allocation_pct, position_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, p)

        d += timedelta(days=1)

    # --- System Config ---
    config = [
        ("schema_version", "2.4.0", "Database schema version"),
        ("tax_rate", "0.37", "Federal tax rate"),
        ("fund_name", "Tovito Trader DEV", "Fund display name"),
    ]
    for key, value, desc in config:
        conn.execute("""
            INSERT INTO system_config (key, value, description, updated_at)
            VALUES (?, ?, ?, ?)
        """, (key, value, desc, now))

    # --- Investor Auth Records (for portal login testing) ---
    try:
        import bcrypt
        test_password = 'TestPass123!'
        password_hash = bcrypt.hashpw(test_password.encode(), bcrypt.gensalt()).decode()

        test_emails = {
            "20260101-01A": "alpha@test.com",
            "20260101-02A": "beta@test.com",
            "20260101-03A": "gamma@test.com",
            "20260115-01A": "delta@test.com",
        }

        for inv_id in test_emails:
            conn.execute("""
                INSERT INTO investor_auth
                (investor_id, password_hash, email_verified, created_at, updated_at)
                VALUES (?, ?, 1, ?, ?)
            """, (inv_id, password_hash, now, now))
    except ImportError:
        pass  # bcrypt not installed -- skip auth records

    # --- Investor Profiles ---
    profiles = [
        ("20260101-01A", "Alpha Investor", "alpha@test.com", "555-0101"),
        ("20260101-02A", "Beta Investor", "beta@test.com", "555-0102"),
    ]
    for inv_id, name, email, phone in profiles:
        conn.execute("""
            INSERT INTO investor_profiles
            (investor_id, full_legal_name, email_primary, phone_mobile, communication_preference, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'email', ?, ?)
        """, (inv_id, name, email, phone, now, now))

    # --- Sample System Log ---
    conn.execute("""
        INSERT INTO system_logs (timestamp, level, category, message, details)
        VALUES (?, 'INFO', 'Setup', 'Dev/test database initialized', ?)
    """, (now, f"Created with setup_test_database.py at {now}"))

    conn.commit()


def reset_prospects(env='dev'):
    """Clear all prospect-related data without rebuilding the entire database."""

    db_path = ENV_DB_PATHS.get(env)
    if not db_path:
        print(f"Unknown environment: {env}")
        sys.exit(1)

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        print(f"Run without --reset-prospects first to create it.")
        sys.exit(1)

    conn = sqlite3.connect(db_path)

    tables_to_clear = [
        'prospect_access_tokens',
        'prospect_communications',
        'prospects',
    ]

    print("=" * 60)
    print("RESET PROSPECTS")
    print("=" * 60)
    print(f"Database: {db_path}")
    print()

    for table in tables_to_clear:
        try:
            cursor = conn.execute(f"SELECT COUNT(*) FROM [{table}]")
            count = cursor.fetchone()[0]
            conn.execute(f"DELETE FROM [{table}]")
            print(f"  Cleared {table}: {count} rows deleted")
        except Exception as e:
            print(f"  Skipped {table}: {e}")

    conn.commit()
    conn.close()

    print()
    print("Prospect data cleared. Ready for fresh testing.")
    print()


def create_database(env='dev'):
    """Create a fresh dev or test database with sample data."""

    db_path = ENV_DB_PATHS.get(env)
    if not db_path:
        print(f"Unknown environment: {env}")
        print(f"Valid options: {', '.join(ENV_DB_PATHS.keys())}")
        sys.exit(1)

    print("=" * 60)
    print(f"{'DEV' if env == 'dev' else 'TEST'} DATABASE SETUP")
    print("=" * 60)
    print()

    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing database
    if db_path.exists():
        print(f"Removing existing database: {db_path}")
        db_path.unlink()
        print()

    print(f"Creating database: {db_path}")
    print()

    # Create database
    conn = sqlite3.connect(db_path)

    print("Creating schema...")
    create_schema(conn)

    # Count tables
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
    table_count = cursor.fetchone()[0]
    print(f"  Done ({table_count} tables created)")
    print()

    print("Populating sample data...")
    populate_sample_data(conn)

    # Print summary
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cursor.fetchall()]

    print()
    print("Database Summary:")
    print(f"  Location: {db_path}")
    print(f"  Tables: {len(tables)}")
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"    {t}: {count} rows")

    conn.close()

    print()
    print("=" * 60)
    print("DATABASE CREATED SUCCESSFULLY")
    print("=" * 60)
    print()
    if env == 'dev':
        print("Start the dev environment with:")
        print("  python scripts/setup/start_dev.py")
        print()
        print("Or manually:")
        print("  set TOVITO_ENV=development")
        print("  python -m uvicorn apps.investor_portal.api.main:app --reload --port 8000")
        print()
        print("Login credentials:")
        print("  Email: alpha@test.com")
        print("  Password: TestPass123!")
    else:
        print("This database is used automatically by pytest.")
        print("Run tests with: pytest tests/ -v")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Create a fresh dev or test database with synthetic data'
    )
    parser.add_argument(
        '--env', choices=['dev', 'test'], default='dev',
        help='Environment to create database for (default: dev)'
    )
    parser.add_argument(
        '--reset-prospects', action='store_true',
        help='Only clear prospect-related tables (prospects, access tokens, communications)'
    )
    args = parser.parse_args()

    try:
        if args.reset_prospects:
            reset_prospects(args.env)
        else:
            create_database(args.env)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
