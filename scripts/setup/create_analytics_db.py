#!/usr/bin/env python3
"""
Create Analytics Database Schema
=================================

Creates a fresh analytics.db for the Market Monitor application.

This database stores:
- Real-time quote snapshots
- Alert configurations and history
- Intraday portfolio snapshots

Usage:
    python create_analytics_db.py
    
Output:
    analytics/analytics.db
"""

import sqlite3
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================

ANALYTICS_DB_PATH = Path('analytics/analytics.db')

# ============================================================
# SCHEMA DEFINITION
# ============================================================

SCHEMA = """
-- ============================================================
-- ANALYTICS DATABASE SCHEMA
-- For Market Monitor Application
-- ============================================================

-- Quote History: Snapshots of real-time quotes
CREATE TABLE IF NOT EXISTS quote_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    price REAL NOT NULL,
    bid REAL,
    ask REAL,
    volume INTEGER,
    change_dollars REAL,
    change_percent REAL,
    last_trade_time TEXT,
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source TEXT DEFAULT 'tradier'
);

CREATE INDEX IF NOT EXISTS idx_quote_history_symbol ON quote_history(symbol);
CREATE INDEX IF NOT EXISTS idx_quote_history_captured ON quote_history(captured_at);


-- Alert Rules: Configured price/condition alerts
CREATE TABLE IF NOT EXISTS alert_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    symbol TEXT,
    alert_type TEXT NOT NULL,  -- 'price_above', 'price_below', 'percent_change', 'portfolio_value', etc.
    condition TEXT NOT NULL,   -- JSON: {"threshold": 100, "direction": "above"}
    priority TEXT DEFAULT 'medium',  -- 'low', 'medium', 'high', 'critical'
    is_active INTEGER DEFAULT 1,
    notify_email INTEGER DEFAULT 0,
    notify_sound INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- Alert History: Log of triggered alerts
CREATE TABLE IF NOT EXISTS alert_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER,
    alert_type TEXT NOT NULL,
    priority TEXT NOT NULL,
    symbol TEXT,
    message TEXT NOT NULL,
    details TEXT,  -- JSON with additional context
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP,
    acknowledged_by TEXT,
    notes TEXT,
    FOREIGN KEY (rule_id) REFERENCES alert_rules(id)
);

CREATE INDEX IF NOT EXISTS idx_alert_history_triggered ON alert_history(triggered_at);
CREATE INDEX IF NOT EXISTS idx_alert_history_type ON alert_history(alert_type);


-- Portfolio Snapshots: Intraday portfolio value tracking
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_time TIMESTAMP NOT NULL,
    total_value REAL NOT NULL,
    cash_balance REAL,
    positions_value REAL,
    day_change_dollars REAL,
    day_change_percent REAL,
    positions_json TEXT,  -- JSON array of position details
    source TEXT DEFAULT 'tradier',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_time ON portfolio_snapshots(snapshot_time);


-- Position Snapshots: Individual position tracking
CREATE TABLE IF NOT EXISTS position_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    quantity REAL NOT NULL,
    cost_basis REAL,
    current_price REAL,
    current_value REAL,
    day_change_dollars REAL,
    day_change_percent REAL,
    FOREIGN KEY (snapshot_id) REFERENCES portfolio_snapshots(id)
);

CREATE INDEX IF NOT EXISTS idx_position_snapshots_snapshot ON position_snapshots(snapshot_id);


-- Streaming Sessions: Track WebSocket connection history
CREATE TABLE IF NOT EXISTS streaming_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_start TIMESTAMP NOT NULL,
    session_end TIMESTAMP,
    symbols_subscribed TEXT,  -- Comma-separated list
    quotes_received INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    disconnect_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- System Config (Analytics-specific)
CREATE TABLE IF NOT EXISTS analytics_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- DEFAULT DATA
-- ============================================================

-- Default alert rules
INSERT OR IGNORE INTO alert_rules (name, symbol, alert_type, condition, priority) VALUES
    ('TQQQ Major Drop', 'TQQQ', 'percent_change', '{"threshold": -5, "direction": "below", "timeframe": "day"}', 'high'),
    ('Portfolio Down 3%', NULL, 'portfolio_change', '{"threshold": -3, "direction": "below", "timeframe": "day"}', 'high'),
    ('Market Hours Start', NULL, 'time', '{"time": "09:30", "timezone": "America/New_York"}', 'low'),
    ('Market Hours End', NULL, 'time', '{"time": "16:00", "timezone": "America/New_York"}', 'low');

-- Default config
INSERT OR IGNORE INTO analytics_config (key, value, description) VALUES
    ('schema_version', '1.0.0', 'Analytics database schema version'),
    ('snapshot_interval_minutes', '5', 'How often to capture portfolio snapshots'),
    ('quote_retention_days', '30', 'Days to keep quote history'),
    ('alert_retention_days', '90', 'Days to keep alert history');
"""


# ============================================================
# MAIN
# ============================================================

def create_analytics_database():
    """Create the analytics database with schema"""
    
    print("\n" + "="*60)
    print(" CREATE ANALYTICS DATABASE")
    print("="*60 + "\n")
    
    # Create directory if needed
    ANALYTICS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    if ANALYTICS_DB_PATH.exists():
        print(f"⚠️  Database already exists: {ANALYTICS_DB_PATH}")
        response = input("   Overwrite? (yes/no): ")
        if response.lower() != 'yes':
            print("   Aborted.")
            return
        ANALYTICS_DB_PATH.unlink()
        print(f"   Deleted existing database.")
    
    # Create database
    print(f"\n📁 Creating: {ANALYTICS_DB_PATH}")
    
    conn = sqlite3.connect(ANALYTICS_DB_PATH)
    cursor = conn.cursor()
    
    # Execute schema
    cursor.executescript(SCHEMA)
    conn.commit()
    
    # Verify tables created
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"\n✅ Database created with {len(tables)} tables:\n")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"   • {table} ({count} rows)")
    
    conn.close()
    
    print(f"\n✅ Analytics database ready: {ANALYTICS_DB_PATH}")
    print(f"   Size: {ANALYTICS_DB_PATH.stat().st_size:,} bytes")
    
    print("""
NEXT STEPS:
-----------
1. Update Market Monitor to use: analytics/analytics.db
2. The Fund Manager continues using: data/tovito.db
3. Run reorganize_project.py to move files

Database purposes:
  • data/tovito.db      = Fund data (investors, NAV, transactions)
  • analytics/analytics.db = Market data (quotes, alerts, snapshots)
""")


if __name__ == '__main__':
    create_analytics_database()
