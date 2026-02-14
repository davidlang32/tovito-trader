"""
Trades Table Schema - Complete Trading Activity Tracker

Stores ALL Tradier transactions for:
- Individual trade tracking
- Performance analysis
- Strategy evaluation
- Trading journal

Separate from investor transactions (which track capital flows).

This table is populated from Tradier API and contains:
- Stock trades (buy/sell)
- Options trades
- ACH deposits/withdrawals
- Fees and commissions
- Dividends
- Everything from Tradier!
"""

CREATE_TRADES_TABLE = """
CREATE TABLE IF NOT EXISTS trades (
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Tradier transaction details
    tradier_transaction_id TEXT,
    date DATE NOT NULL,
    type TEXT NOT NULL,  -- trade, option, ach, wire, dividend, fee, etc.
    status TEXT,  -- completed, pending, etc.
    
    -- Financial details
    amount REAL NOT NULL,  -- Total dollar amount (+ or -)
    commission REAL DEFAULT 0,
    
    -- Security details (for trades)
    symbol TEXT,
    quantity REAL,
    price REAL,
    
    -- Option details (if option trade)
    option_type TEXT,  -- call or put
    strike REAL,
    expiration_date DATE,
    
    -- Trade classification
    trade_type TEXT,  -- buy, sell, buy_to_open, sell_to_close, etc.
    
    -- Description and notes
    description TEXT,
    notes TEXT,
    
    -- Categorization (auto-generated)
    category TEXT,  -- Trade, Transfer, Income, Fee, Other
    subcategory TEXT,  -- Stock Buy, Option Call, Deposit, etc.
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Index for faster queries
    UNIQUE(tradier_transaction_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date);
CREATE INDEX IF NOT EXISTS idx_trades_type ON trades(type);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_category ON trades(category);

-- View: ACH Summary (for validation against investor transactions)
CREATE VIEW IF NOT EXISTS ach_summary AS
SELECT 
    date,
    SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total_deposits,
    SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_withdrawals,
    SUM(amount) as net_ach,
    COUNT(*) as ach_count
FROM trades
WHERE type IN ('ach', 'wire', 'journal')
GROUP BY date
ORDER BY date;

-- View: Trade Summary by Symbol
CREATE VIEW IF NOT EXISTS trade_summary_by_symbol AS
SELECT 
    symbol,
    COUNT(*) as trade_count,
    SUM(quantity) as net_quantity,
    SUM(amount) as total_amount,
    SUM(commission) as total_commission,
    MIN(date) as first_trade,
    MAX(date) as last_trade
FROM trades
WHERE category = 'Trade' AND symbol IS NOT NULL
GROUP BY symbol
ORDER BY total_amount DESC;

-- View: Monthly Trading Activity
CREATE VIEW IF NOT EXISTS monthly_trading_activity AS
SELECT 
    strftime('%Y-%m', date) as month,
    category,
    subcategory,
    COUNT(*) as transaction_count,
    SUM(amount) as total_amount,
    SUM(commission) as total_commission
FROM trades
GROUP BY month, category, subcategory
ORDER BY month DESC, category;

-- View: Performance Summary
CREATE VIEW IF NOT EXISTS trading_performance AS
SELECT 
    COUNT(CASE WHEN category = 'Trade' THEN 1 END) as total_trades,
    COUNT(DISTINCT symbol) as unique_symbols,
    SUM(CASE WHEN type IN ('ach', 'wire') AND amount > 0 THEN amount ELSE 0 END) as total_deposits,
    SUM(CASE WHEN type IN ('ach', 'wire') AND amount < 0 THEN ABS(amount) ELSE 0 END) as total_withdrawals,
    SUM(CASE WHEN category = 'Income' THEN amount ELSE 0 END) as total_income,
    SUM(CASE WHEN category = 'Fee' THEN ABS(amount) ELSE 0 END) as total_fees,
    MIN(date) as first_transaction,
    MAX(date) as last_transaction
FROM trades;
"""

# Usage:
# import sqlite3
# conn = sqlite3.connect('data/tovito.db')
# cursor = conn.cursor()
# cursor.executescript(CREATE_TRADES_TABLE)
# conn.commit()
