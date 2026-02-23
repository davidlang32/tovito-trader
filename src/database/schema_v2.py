#!/usr/bin/env python3
"""
Tovito Trader - Improved Database Schema v2.0
==============================================

This module defines an enhanced database schema with:
- Better data integrity (foreign keys, constraints)
- Audit logging
- Soft deletes
- Performance indexes
- Views for common queries
- Triggers for automatic calculations

Schema Changes from v1:
-----------------------
1. Added 'created_at' and 'updated_at' to all tables
2. Added 'is_deleted' soft delete flag
3. Added audit_log table for change tracking
4. Added proper foreign key constraints
5. Added CHECK constraints for data validation
6. Added views for common reporting needs
7. Added triggers for automatic calculations
8. Improved indexes for query performance
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# SCHEMA DEFINITIONS
# ============================================================

SCHEMA_VERSION = "2.3.0"

# Core tables
INVESTORS_TABLE = """
CREATE TABLE IF NOT EXISTS investors (
    -- Primary identifier
    investor_id TEXT PRIMARY KEY,
    
    -- Basic info
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    
    -- Financial data
    initial_capital REAL NOT NULL DEFAULT 0,
    current_shares REAL NOT NULL DEFAULT 0,
    net_investment REAL NOT NULL DEFAULT 0,
    
    -- Status
    status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive', 'Suspended')),
    join_date DATE NOT NULL,
    
    -- Metadata
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    
    -- Constraints
    CHECK (current_shares >= 0),
    CHECK (initial_capital >= 0)
);
"""

TRANSACTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS transactions (
    -- Primary identifier
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Transaction details
    date DATE NOT NULL,
    investor_id TEXT NOT NULL,
    transaction_type TEXT NOT NULL CHECK (
        transaction_type IN ('Initial', 'Contribution', 'Withdrawal', 'Tax_Payment', 'Fee', 'Adjustment')
    ),
    
    -- Financial data
    amount REAL NOT NULL,
    shares_transacted REAL NOT NULL DEFAULT 0,
    nav_per_share REAL NOT NULL,
    
    -- Additional info
    description TEXT,
    notes TEXT,
    reference_id TEXT,  -- External reference (e.g., ACH transaction ID)
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
    
    -- Foreign key
    FOREIGN KEY (investor_id) REFERENCES investors(investor_id)
);
"""

DAILY_NAV_TABLE = """
CREATE TABLE IF NOT EXISTS daily_nav (
    -- Primary identifier
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL UNIQUE,
    
    -- Portfolio data
    total_portfolio_value REAL NOT NULL,
    total_shares REAL NOT NULL,
    nav_per_share REAL NOT NULL,
    
    -- Change tracking
    daily_change_value REAL,
    daily_change_percent REAL,
    
    -- Source data
    tradier_balance REAL,
    cash_balance REAL,
    equity_value REAL,
    
    -- Metadata
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CHECK (total_portfolio_value >= 0),
    CHECK (total_shares >= 0),
    CHECK (nav_per_share > 0)
);
"""

TAX_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS tax_events (
    -- Primary identifier
    tax_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Event details
    date DATE NOT NULL,
    investor_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (
        event_type IN ('Realized_Gain', 'Realized_Loss', 'Tax_Withheld', 'Tax_Refund', 'Year_End_Settlement')
    ),
    
    -- Financial data
    amount REAL NOT NULL,
    tax_rate REAL NOT NULL DEFAULT 0.37,
    tax_amount REAL NOT NULL,
    
    -- Related transaction
    related_transaction_id INTEGER,
    
    -- Notes
    description TEXT,
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    
    -- Foreign keys
    FOREIGN KEY (investor_id) REFERENCES investors(investor_id),
    FOREIGN KEY (related_transaction_id) REFERENCES transactions(transaction_id)
);
"""

TRADES_TABLE = """
CREATE TABLE IF NOT EXISTS trades (
    -- Primary identifier
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Trade details
    date DATE NOT NULL,
    trade_type TEXT NOT NULL CHECK (
        trade_type IN ('buy', 'sell', 'buy_to_open', 'sell_to_close', 'buy_to_close', 'sell_to_open', 
                       'dividend', 'interest', 'ach', 'fee', 'journal', 'other')
    ),
    
    -- Symbol info
    symbol TEXT,
    quantity REAL,
    price REAL,
    amount REAL NOT NULL,
    
    -- Options specific
    option_type TEXT CHECK (option_type IN ('call', 'put', NULL)),
    strike REAL,
    expiration_date DATE,
    
    -- Fees
    commission REAL DEFAULT 0,
    fees REAL DEFAULT 0,
    
    -- Categorization
    category TEXT,
    subcategory TEXT,
    
    -- Notes
    description TEXT,
    notes TEXT,

    -- Brokerage source tracking
    source TEXT NOT NULL DEFAULT 'tradier',
    brokerage_transaction_id TEXT,

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0
);
"""

HOLDINGS_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS holdings_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    source TEXT NOT NULL,
    snapshot_time TIMESTAMP NOT NULL,
    total_positions INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, source)
);
"""

POSITION_SNAPSHOTS_TABLE = """
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
    expiration_date DATE,
    multiplier INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id) REFERENCES holdings_snapshots(snapshot_id)
);
"""

BROKERAGE_TRANSACTIONS_RAW_TABLE = """
CREATE TABLE IF NOT EXISTS brokerage_transactions_raw (
    -- Primary identifier
    raw_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Source tracking
    source TEXT NOT NULL,                    -- 'tradier' or 'tastytrade'
    brokerage_transaction_id TEXT NOT NULL,  -- Original ID from brokerage API

    -- Raw data (JSON blob preserving everything the API returned)
    raw_data TEXT NOT NULL,

    -- Extracted key fields (for querying without parsing JSON)
    transaction_date DATE NOT NULL,
    transaction_type TEXT NOT NULL,          -- Original brokerage type
    transaction_subtype TEXT,                -- Original subtype
    symbol TEXT,
    amount REAL,
    description TEXT,

    -- ETL tracking
    etl_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (etl_status IN ('pending', 'transformed', 'skipped', 'error')),
    etl_transformed_at TIMESTAMP,
    etl_trade_id INTEGER,                   -- FK to trades.trade_id after transform
    etl_error TEXT,                          -- Error message if transform failed

    -- Metadata
    ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Deduplication
    UNIQUE(source, brokerage_transaction_id)
);
"""

FUND_FLOW_REQUESTS_TABLE = """
CREATE TABLE IF NOT EXISTS fund_flow_requests (
    -- Primary identifier
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Request details
    investor_id TEXT NOT NULL,
    flow_type TEXT NOT NULL CHECK (flow_type IN ('contribution', 'withdrawal')),
    requested_amount REAL NOT NULL CHECK (requested_amount > 0),
    request_date DATE NOT NULL,
    request_method TEXT NOT NULL DEFAULT 'portal'
        CHECK (request_method IN ('portal', 'email', 'verbal', 'admin', 'other')),

    -- Lifecycle status
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'awaiting_funds', 'matched',
                          'processed', 'rejected', 'cancelled')),

    -- Approval
    approved_by TEXT,
    approved_date TIMESTAMP,
    rejection_reason TEXT,

    -- Brokerage matching (links to actual money movement)
    matched_trade_id INTEGER,              -- FK to trades.trade_id (the ACH record)
    matched_raw_id INTEGER,                -- FK to brokerage_transactions_raw.raw_id
    matched_date TIMESTAMP,
    matched_by TEXT,                        -- Who confirmed the match

    -- Processing (share accounting)
    processed_date TIMESTAMP,
    actual_amount REAL,                    -- May differ from requested (e.g., fees)
    shares_transacted REAL,
    nav_per_share REAL,
    transaction_id INTEGER,                -- FK to transactions.transaction_id

    -- Withdrawal-specific tax fields
    realized_gain REAL,
    tax_withheld REAL DEFAULT 0,
    net_proceeds REAL,

    -- Notes
    notes TEXT,

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (investor_id) REFERENCES investors(investor_id),
    FOREIGN KEY (matched_trade_id) REFERENCES trades(trade_id),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);
"""

INVESTOR_PROFILES_TABLE = """
CREATE TABLE IF NOT EXISTS investor_profiles (
    -- Primary identifier
    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
    investor_id TEXT NOT NULL UNIQUE,

    -- Contact Information (Section 1)
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

    -- Personal Information (Section 2)
    date_of_birth TEXT,                     -- Encrypted (Fernet) if sensitive
    marital_status TEXT CHECK (marital_status IN (
        'single', 'married', 'divorced', 'widowed', 'domestic_partnership', NULL
    )),
    num_dependents INTEGER DEFAULT 0,
    citizenship TEXT DEFAULT 'US',

    -- Employment Information (Section 3)
    employment_status TEXT CHECK (employment_status IN (
        'employed', 'self_employed', 'retired', 'unemployed', 'student', NULL
    )),
    occupation TEXT,
    job_title TEXT,
    employer_name TEXT,
    employer_address TEXT,

    -- Sensitive PII — Application-level encrypted (Fernet)
    ssn_encrypted TEXT,                     -- Social Security Number
    tax_id_encrypted TEXT,                  -- Tax ID (if different from SSN)
    bank_routing_encrypted TEXT,            -- Bank routing number
    bank_account_encrypted TEXT,            -- Bank account number
    bank_name TEXT,                         -- Not encrypted (not sensitive alone)
    bank_account_type TEXT CHECK (bank_account_type IN ('checking', 'savings', NULL)),

    -- Accreditation
    is_accredited INTEGER DEFAULT 0,
    accreditation_method TEXT,
    accreditation_verified_date DATE,
    accreditation_expires_date DATE,
    accreditation_docs_on_file INTEGER DEFAULT 0,

    -- Preferences
    communication_preference TEXT DEFAULT 'email'
        CHECK (communication_preference IN ('email', 'phone', 'mail')),
    statement_delivery TEXT DEFAULT 'electronic'
        CHECK (statement_delivery IN ('electronic', 'paper', 'both')),

    -- Metadata
    profile_completed INTEGER DEFAULT 0,
    last_verified_date DATE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (investor_id) REFERENCES investors(investor_id)
);
"""

REFERRALS_TABLE = """
CREATE TABLE IF NOT EXISTS referrals (
    -- Primary identifier
    referral_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Referrer (existing investor)
    referrer_investor_id TEXT NOT NULL,
    referral_code TEXT NOT NULL UNIQUE,

    -- Referred person
    referred_name TEXT,
    referred_email TEXT,
    referred_date DATE NOT NULL,

    -- Outcome tracking
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'contacted', 'onboarded', 'expired', 'declined')),
    converted_investor_id TEXT,
    converted_date DATE,

    -- Incentive tracking
    incentive_type TEXT,
    incentive_amount REAL,
    incentive_paid INTEGER DEFAULT 0,
    incentive_paid_date DATE,

    -- Metadata
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (referrer_investor_id) REFERENCES investors(investor_id),
    FOREIGN KEY (converted_investor_id) REFERENCES investors(investor_id)
);
"""

BENCHMARK_PRICES_TABLE = """
CREATE TABLE IF NOT EXISTS benchmark_prices (
    -- Cache for benchmark daily close prices (SPY, QQQ, BTC-USD)
    -- Used by the NAV vs Benchmarks comparison chart
    date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    close_price REAL NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (date, ticker)
);
"""

AUDIT_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS audit_log (
    -- Primary identifier
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Action details
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    table_name TEXT NOT NULL,
    record_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    
    -- Change data (JSON)
    old_values TEXT,  -- JSON of old values
    new_values TEXT,  -- JSON of new values
    
    -- User/context
    performed_by TEXT DEFAULT 'system',
    ip_address TEXT,
    notes TEXT
);
"""

SYSTEM_CONFIG_TABLE = """
CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

# ============================================================
# INDEXES
# ============================================================

INDEXES = [
    # Investors
    "CREATE INDEX IF NOT EXISTS idx_investors_status ON investors(status) WHERE is_deleted = 0",
    "CREATE INDEX IF NOT EXISTS idx_investors_join_date ON investors(join_date)",
    
    # Transactions
    "CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date)",
    "CREATE INDEX IF NOT EXISTS idx_transactions_investor ON transactions(investor_id)",
    "CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(transaction_type)",
    "CREATE INDEX IF NOT EXISTS idx_transactions_investor_date ON transactions(investor_id, date)",
    
    # Daily NAV
    "CREATE INDEX IF NOT EXISTS idx_daily_nav_date ON daily_nav(date)",
    
    # Tax Events
    "CREATE INDEX IF NOT EXISTS idx_tax_events_date ON tax_events(date)",
    "CREATE INDEX IF NOT EXISTS idx_tax_events_investor ON tax_events(investor_id)",
    
    # Trades
    "CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date)",
    "CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_trades_type ON trades(trade_type)",
    "CREATE INDEX IF NOT EXISTS idx_trades_brokerage_id ON trades(brokerage_transaction_id)",
    
    "CREATE INDEX IF NOT EXISTS idx_trades_source ON trades(source)",
    "CREATE INDEX IF NOT EXISTS idx_trades_date_source ON trades(date, source)",

    # Holdings Snapshots
    "CREATE INDEX IF NOT EXISTS idx_holdings_snapshots_date ON holdings_snapshots(date)",

    # Position Snapshots
    "CREATE INDEX IF NOT EXISTS idx_position_snapshots_snapshot ON position_snapshots(snapshot_id)",
    "CREATE INDEX IF NOT EXISTS idx_position_snapshots_symbol ON position_snapshots(symbol)",

    # Brokerage Transactions Raw (ETL staging)
    "CREATE INDEX IF NOT EXISTS idx_raw_txn_source_brokerage_id ON brokerage_transactions_raw(source, brokerage_transaction_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_txn_etl_status ON brokerage_transactions_raw(etl_status)",
    "CREATE INDEX IF NOT EXISTS idx_raw_txn_date ON brokerage_transactions_raw(transaction_date)",
    "CREATE INDEX IF NOT EXISTS idx_raw_txn_source_date ON brokerage_transactions_raw(source, transaction_date)",

    # Fund Flow Requests
    "CREATE INDEX IF NOT EXISTS idx_fund_flow_investor ON fund_flow_requests(investor_id)",
    "CREATE INDEX IF NOT EXISTS idx_fund_flow_status ON fund_flow_requests(status)",
    "CREATE INDEX IF NOT EXISTS idx_fund_flow_type ON fund_flow_requests(flow_type)",
    "CREATE INDEX IF NOT EXISTS idx_fund_flow_matched_trade ON fund_flow_requests(matched_trade_id)",

    # Investor Profiles
    "CREATE INDEX IF NOT EXISTS idx_investor_profiles_investor ON investor_profiles(investor_id)",

    # Referrals
    "CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_investor_id)",
    "CREATE INDEX IF NOT EXISTS idx_referrals_code ON referrals(referral_code)",
    "CREATE INDEX IF NOT EXISTS idx_referrals_status ON referrals(status)",

    # Benchmark Prices
    "CREATE INDEX IF NOT EXISTS idx_benchmark_ticker_date ON benchmark_prices(ticker, date)",

    # Audit Log
    "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_audit_table ON audit_log(table_name)",
]

# ============================================================
# VIEWS
# ============================================================

VIEWS = {
    # Active investors with calculated values
    "v_investor_positions": """
    CREATE VIEW IF NOT EXISTS v_investor_positions AS
    SELECT 
        i.investor_id,
        i.name,
        i.current_shares,
        i.net_investment,
        i.status,
        (SELECT nav_per_share FROM daily_nav ORDER BY date DESC LIMIT 1) as current_nav,
        i.current_shares * (SELECT nav_per_share FROM daily_nav ORDER BY date DESC LIMIT 1) as current_value,
        i.current_shares * (SELECT nav_per_share FROM daily_nav ORDER BY date DESC LIMIT 1) - i.net_investment as unrealized_gain,
        CASE 
            WHEN i.net_investment > 0 THEN 
                (i.current_shares * (SELECT nav_per_share FROM daily_nav ORDER BY date DESC LIMIT 1) - i.net_investment) / i.net_investment * 100
            ELSE 0
        END as return_pct,
        CASE 
            WHEN (SELECT SUM(current_shares) FROM investors WHERE status = 'Active' AND is_deleted = 0) > 0 THEN
                i.current_shares / (SELECT SUM(current_shares) FROM investors WHERE status = 'Active' AND is_deleted = 0) * 100
            ELSE 0
        END as portfolio_pct
    FROM investors i
    WHERE i.status = 'Active' AND i.is_deleted = 0
    """,
    
    # Transaction summary by investor
    "v_investor_transactions": """
    CREATE VIEW IF NOT EXISTS v_investor_transactions AS
    SELECT 
        investor_id,
        SUM(CASE WHEN transaction_type = 'Initial' THEN amount ELSE 0 END) as initial_investment,
        SUM(CASE WHEN transaction_type = 'Contribution' THEN amount ELSE 0 END) as total_contributions,
        SUM(CASE WHEN transaction_type = 'Withdrawal' THEN ABS(amount) ELSE 0 END) as total_withdrawals,
        SUM(CASE WHEN transaction_type = 'Tax_Payment' THEN ABS(amount) ELSE 0 END) as total_tax_paid,
        COUNT(*) as transaction_count,
        MIN(date) as first_transaction,
        MAX(date) as last_transaction
    FROM transactions
    WHERE is_deleted = 0
    GROUP BY investor_id
    """,
    
    # Daily NAV with change calculations
    "v_nav_history": """
    CREATE VIEW IF NOT EXISTS v_nav_history AS
    SELECT 
        n.date,
        n.total_portfolio_value,
        n.total_shares,
        n.nav_per_share,
        n.daily_change_value,
        n.daily_change_percent,
        LAG(n.nav_per_share) OVER (ORDER BY n.date) as prev_nav,
        n.nav_per_share - LAG(n.nav_per_share) OVER (ORDER BY n.date) as nav_change
    FROM daily_nav n
    ORDER BY n.date
    """,
    
    # ACH summary (deposits and withdrawals)
    "v_ach_summary": """
    CREATE VIEW IF NOT EXISTS v_ach_summary AS
    SELECT 
        date,
        SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as deposits,
        SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as withdrawals,
        SUM(amount) as net_flow,
        COUNT(*) as transaction_count
    FROM trades
    WHERE trade_type = 'ach' AND is_deleted = 0
    GROUP BY date
    ORDER BY date
    """,
    
    # Trade summary by symbol
    "v_trade_summary_by_symbol": """
    CREATE VIEW IF NOT EXISTS v_trade_summary_by_symbol AS
    SELECT 
        symbol,
        COUNT(*) as trade_count,
        SUM(CASE WHEN trade_type IN ('buy', 'buy_to_open') THEN quantity ELSE 0 END) as total_bought,
        SUM(CASE WHEN trade_type IN ('sell', 'sell_to_close') THEN quantity ELSE 0 END) as total_sold,
        SUM(amount) as total_amount,
        SUM(commission) as total_commission,
        MIN(date) as first_trade,
        MAX(date) as last_trade
    FROM trades
    WHERE symbol IS NOT NULL AND is_deleted = 0
    GROUP BY symbol
    ORDER BY total_amount DESC
    """,
    
    # Tax liability summary
    "v_tax_summary": """
    CREATE VIEW IF NOT EXISTS v_tax_summary AS
    SELECT 
        i.investor_id,
        i.name,
        i.net_investment,
        i.current_shares * (SELECT nav_per_share FROM daily_nav ORDER BY date DESC LIMIT 1) as current_value,
        i.current_shares * (SELECT nav_per_share FROM daily_nav ORDER BY date DESC LIMIT 1) - i.net_investment as unrealized_gain,
        (i.current_shares * (SELECT nav_per_share FROM daily_nav ORDER BY date DESC LIMIT 1) - i.net_investment) * 
            CAST((SELECT value FROM system_config WHERE key = 'tax_rate') AS REAL) as estimated_tax,
        COALESCE(te.total_tax_paid, 0) as tax_already_paid
    FROM investors i
    LEFT JOIN (
        SELECT investor_id, SUM(tax_amount) as total_tax_paid
        FROM tax_events
        WHERE event_type = 'Tax_Withheld' AND is_deleted = 0
        GROUP BY investor_id
    ) te ON i.investor_id = te.investor_id
    WHERE i.status = 'Active' AND i.is_deleted = 0
    """,
    
    # Monthly performance
    "v_monthly_performance": """
    CREATE VIEW IF NOT EXISTS v_monthly_performance AS
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
    """
}

# ============================================================
# TRIGGERS
# ============================================================

TRIGGERS = [
    # Update timestamp on investors
    """
    CREATE TRIGGER IF NOT EXISTS trg_investors_updated_at
    AFTER UPDATE ON investors
    FOR EACH ROW
    BEGIN
        UPDATE investors SET updated_at = CURRENT_TIMESTAMP WHERE investor_id = NEW.investor_id;
    END
    """,
    
    # Update timestamp on transactions
    """
    CREATE TRIGGER IF NOT EXISTS trg_transactions_updated_at
    AFTER UPDATE ON transactions
    FOR EACH ROW
    BEGIN
        UPDATE transactions SET updated_at = CURRENT_TIMESTAMP WHERE transaction_id = NEW.transaction_id;
    END
    """,
    
    # Audit log for investor changes
    """
    CREATE TRIGGER IF NOT EXISTS trg_audit_investors_insert
    AFTER INSERT ON investors
    FOR EACH ROW
    BEGIN
        INSERT INTO audit_log (table_name, record_id, action, new_values)
        VALUES ('investors', NEW.investor_id, 'INSERT', 
                json_object('name', NEW.name, 'initial_capital', NEW.initial_capital, 'status', NEW.status));
    END
    """,
    
    """
    CREATE TRIGGER IF NOT EXISTS trg_audit_investors_update
    AFTER UPDATE ON investors
    FOR EACH ROW
    BEGIN
        INSERT INTO audit_log (table_name, record_id, action, old_values, new_values)
        VALUES ('investors', NEW.investor_id, 'UPDATE',
                json_object('current_shares', OLD.current_shares, 'net_investment', OLD.net_investment, 'status', OLD.status),
                json_object('current_shares', NEW.current_shares, 'net_investment', NEW.net_investment, 'status', NEW.status));
    END
    """,
    
    # Audit log for transactions
    """
    CREATE TRIGGER IF NOT EXISTS trg_audit_transactions_insert
    AFTER INSERT ON transactions
    FOR EACH ROW
    BEGIN
        INSERT INTO audit_log (table_name, record_id, action, new_values)
        VALUES ('transactions', NEW.transaction_id, 'INSERT',
                json_object('investor_id', NEW.investor_id, 'type', NEW.transaction_type, 
                           'amount', NEW.amount, 'shares', NEW.shares_transacted));
    END
    """
]

# ============================================================
# DEFAULT DATA
# ============================================================

DEFAULT_CONFIG = [
    ('schema_version', SCHEMA_VERSION, 'Database schema version'),
    ('tax_rate', '0.37', 'Federal tax rate for gain calculations'),
    ('fund_name', 'Tovito Trader', 'Fund display name'),
    ('base_currency', 'USD', 'Base currency for all amounts'),
    ('trading_enabled', 'true', 'Whether trading is currently enabled'),
]


# ============================================================
# DATABASE MANAGER
# ============================================================

class DatabaseManager:
    """Manage database schema and migrations"""
    
    def __init__(self, db_path: str = "data/tovito.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with proper settings"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_schema(self):
        """Create all tables, indexes, views, and triggers"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Create tables
            logger.info("Creating tables...")
            cursor.execute(INVESTORS_TABLE)
            cursor.execute(TRANSACTIONS_TABLE)
            cursor.execute(DAILY_NAV_TABLE)
            cursor.execute(TAX_EVENTS_TABLE)
            cursor.execute(TRADES_TABLE)
            cursor.execute(HOLDINGS_SNAPSHOTS_TABLE)
            cursor.execute(POSITION_SNAPSHOTS_TABLE)
            cursor.execute(BENCHMARK_PRICES_TABLE)
            cursor.execute(AUDIT_LOG_TABLE)
            cursor.execute(SYSTEM_CONFIG_TABLE)

            # Create indexes
            logger.info("Creating indexes...")
            for idx in INDEXES:
                cursor.execute(idx)
            
            # Create views
            logger.info("Creating views...")
            for view_name, view_sql in VIEWS.items():
                cursor.execute(f"DROP VIEW IF EXISTS {view_name}")
                cursor.execute(view_sql)
            
            # Create triggers
            logger.info("Creating triggers...")
            for trigger in TRIGGERS:
                try:
                    cursor.execute(trigger)
                except sqlite3.OperationalError as e:
                    if "already exists" not in str(e):
                        raise
            
            # Insert default config
            logger.info("Inserting default configuration...")
            for key, value, desc in DEFAULT_CONFIG:
                cursor.execute("""
                    INSERT OR REPLACE INTO system_config (key, value, description, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (key, value, desc))
            
            conn.commit()
            logger.info("✅ Schema created successfully!")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Schema creation failed: {e}")
            raise
        finally:
            conn.close()
    
    def migrate_from_v1(self):
        """Migrate existing v1 database to v2 schema"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        logger.info("Starting migration from v1 to v2...")
        
        try:
            # Check if we need to migrate
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='investors'")
            if not cursor.fetchone():
                logger.info("No existing database found - creating fresh schema")
                conn.close()
                self.create_schema()
                return
            
            # Add new columns to investors if they don't exist
            cursor.execute("PRAGMA table_info(investors)")
            existing_cols = {row['name'] for row in cursor.fetchall()}
            
            new_cols = [
                ('email', 'TEXT'),
                ('phone', 'TEXT'),
                ('created_at', "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ('updated_at', "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ('is_deleted', "INTEGER DEFAULT 0"),
            ]
            
            for col_name, col_type in new_cols:
                if col_name not in existing_cols:
                    logger.info(f"  Adding column: investors.{col_name}")
                    cursor.execute(f"ALTER TABLE investors ADD COLUMN {col_name} {col_type}")
            
            # Add new columns to transactions
            cursor.execute("PRAGMA table_info(transactions)")
            existing_cols = {row['name'] for row in cursor.fetchall()}
            
            new_cols = [
                ('description', 'TEXT'),
                ('reference_id', 'TEXT'),
                ('created_at', "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ('updated_at', "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ('is_deleted', "INTEGER DEFAULT 0"),
            ]
            
            for col_name, col_type in new_cols:
                if col_name not in existing_cols:
                    logger.info(f"  Adding column: transactions.{col_name}")
                    cursor.execute(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_type}")
            
            # Add new columns to daily_nav
            cursor.execute("PRAGMA table_info(daily_nav)")
            existing_cols = {row['name'] for row in cursor.fetchall()}
            
            new_cols = [
                ('daily_change_value', 'REAL'),
                ('daily_change_percent', 'REAL'),
                ('tradier_balance', 'REAL'),
                ('cash_balance', 'REAL'),
                ('equity_value', 'REAL'),
                ('created_at', "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ('updated_at', "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ]
            
            for col_name, col_type in new_cols:
                if col_name not in existing_cols:
                    logger.info(f"  Adding column: daily_nav.{col_name}")
                    cursor.execute(f"ALTER TABLE daily_nav ADD COLUMN {col_name} {col_type}")
            
            # Create new tables if they don't exist
            cursor.execute(TAX_EVENTS_TABLE)
            cursor.execute(TRADES_TABLE)
            cursor.execute(HOLDINGS_SNAPSHOTS_TABLE)
            cursor.execute(POSITION_SNAPSHOTS_TABLE)
            cursor.execute(BENCHMARK_PRICES_TABLE)
            cursor.execute(AUDIT_LOG_TABLE)
            cursor.execute(SYSTEM_CONFIG_TABLE)
            
            # Create indexes
            for idx in INDEXES:
                try:
                    cursor.execute(idx)
                except sqlite3.OperationalError:
                    pass  # Index might already exist
            
            # Create views
            for view_name, view_sql in VIEWS.items():
                cursor.execute(f"DROP VIEW IF EXISTS {view_name}")
                cursor.execute(view_sql)
            
            # Insert config
            for key, value, desc in DEFAULT_CONFIG:
                cursor.execute("""
                    INSERT OR IGNORE INTO system_config (key, value, description)
                    VALUES (?, ?, ?)
                """, (key, value, desc))
            
            # Update schema version
            cursor.execute("""
                UPDATE system_config SET value = ?, updated_at = CURRENT_TIMESTAMP
                WHERE key = 'schema_version'
            """, (SCHEMA_VERSION,))
            
            conn.commit()
            logger.info("✅ Migration completed successfully!")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Migration failed: {e}")
            raise
        finally:
            conn.close()
    
    def validate_schema(self) -> bool:
        """Validate that schema is correct"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        issues = []
        
        try:
            # Check required tables
            required_tables = ['investors', 'transactions', 'daily_nav', 'system_config']
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = {row['name'] for row in cursor.fetchall()}
            
            for table in required_tables:
                if table not in existing_tables:
                    issues.append(f"Missing table: {table}")
            
            # Check schema version
            cursor.execute("SELECT value FROM system_config WHERE key = 'schema_version'")
            row = cursor.fetchone()
            if row:
                version = row['value']
                if version != SCHEMA_VERSION:
                    issues.append(f"Schema version mismatch: {version} vs {SCHEMA_VERSION}")
            else:
                issues.append("Schema version not found")
            
            if issues:
                logger.warning("Schema validation issues:")
                for issue in issues:
                    logger.warning(f"  - {issue}")
                return False
            
            logger.info("✅ Schema validation passed")
            return True
            
        finally:
            conn.close()
    
    def get_stats(self) -> dict:
        """Get database statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        try:
            # Count records in each table
            tables = ['investors', 'transactions', 'daily_nav', 'tax_events', 'trades', 'audit_log']
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[f"{table}_count"] = cursor.fetchone()[0]
                except sqlite3.OperationalError:
                    stats[f"{table}_count"] = 0
            
            # Get schema version
            cursor.execute("SELECT value FROM system_config WHERE key = 'schema_version'")
            row = cursor.fetchone()
            stats['schema_version'] = row['value'] if row else 'Unknown'
            
            # Get database file size
            stats['file_size_mb'] = self.db_path.stat().st_size / (1024 * 1024)
            
            return stats
            
        finally:
            conn.close()


# ============================================================
# CLI
# ============================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Tovito Trader Database Manager")
    parser.add_argument('command', choices=['create', 'migrate', 'validate', 'stats'],
                        help='Command to run')
    parser.add_argument('--db', default='data/tovito.db', help='Database path')
    
    args = parser.parse_args()
    
    db = DatabaseManager(args.db)
    
    if args.command == 'create':
        print("Creating fresh database schema...")
        db.create_schema()
        
    elif args.command == 'migrate':
        print("Migrating database to v2 schema...")
        db.migrate_from_v1()
        
    elif args.command == 'validate':
        print("Validating database schema...")
        if db.validate_schema():
            print("✅ Schema is valid")
        else:
            print("❌ Schema has issues")
            
    elif args.command == 'stats':
        print("\n📊 Database Statistics:")
        print("-" * 40)
        stats = db.get_stats()
        for key, value in stats.items():
            if 'count' in key:
                print(f"  {key.replace('_count', '')}: {value:,} records")
            elif 'size' in key:
                print(f"  File size: {value:.2f} MB")
            else:
                print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
