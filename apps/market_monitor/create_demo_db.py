"""
Generate Demo Database for Testing
Creates a sample tovito.db with realistic test data
"""

import sqlite3
from datetime import datetime, timedelta
import random
import os

def create_demo_database(db_path="demo_data/tovito.db"):
    """Create a demo database with sample data"""
    
    # Create directory if needed
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Remove existing demo db
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Creating demo database...")
    
    # Create tables
    cursor.execute("""
        CREATE TABLE investors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investor_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            shares REAL DEFAULT 0,
            net_investment REAL DEFAULT 0,
            status TEXT DEFAULT 'Active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE daily_nav (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,
            total_portfolio_value REAL NOT NULL,
            total_shares REAL NOT NULL,
            nav_per_share REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            investor_id TEXT NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            shares REAL,
            nav_per_share REAL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tradier_transaction_id TEXT UNIQUE,
            date TEXT NOT NULL,
            type TEXT,
            amount REAL,
            commission REAL DEFAULT 0,
            symbol TEXT,
            quantity REAL,
            price REAL,
            option_type TEXT,
            strike REAL,
            expiration_date TEXT,
            category TEXT,
            subcategory TEXT,
            description TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE tax_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            investor_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            realized_gain REAL,
            tax_due REAL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Insert demo investors
    investors = [
        ("20260101-01A", "David Lang", 18432.62, 19000.00, "Active"),
        ("20260101-02A", "Ken Smith", 987.65, 1000.00, "Active"),
        ("20260101-03A", "Beth Johnson", 987.65, 1000.00, "Active"),
    ]
    
    cursor.executemany("""
        INSERT INTO investors (investor_id, name, shares, net_investment, status)
        VALUES (?, ?, ?, ?, ?)
    """, investors)
    
    print("✅ Created 3 demo investors")
    
    # Generate 60 days of NAV history
    base_date = datetime(2025, 12, 30)
    nav_per_share = 0.8824
    total_shares = 17000.00
    portfolio_value = total_shares * nav_per_share
    
    nav_data = []
    transactions_data = []
    
    # Initial transactions
    transactions_data.append((
        base_date.strftime("%Y-%m-%d"),
        "20260101-01A",
        "Initial",
        15000.00,
        15000.00 / nav_per_share,
        nav_per_share,
        "Initial investment"
    ))
    
    for i in range(60):
        current_date = base_date + timedelta(days=i)
        
        # Skip weekends
        if current_date.weekday() >= 5:
            continue
        
        # Random daily movement (-2% to +3%)
        daily_return = random.uniform(-0.02, 0.03)
        nav_per_share = nav_per_share * (1 + daily_return)
        
        # Add some contributions
        if i == 3:  # Jan 2
            contrib_shares = 1000.00 / nav_per_share
            total_shares += contrib_shares
            transactions_data.append((
                current_date.strftime("%Y-%m-%d"),
                "20260101-02A",
                "Initial",
                1000.00,
                contrib_shares,
                nav_per_share,
                "Initial - Ken"
            ))
            transactions_data.append((
                current_date.strftime("%Y-%m-%d"),
                "20260101-03A",
                "Initial",
                1000.00,
                contrib_shares,
                nav_per_share,
                "Initial - Beth"
            ))
            total_shares += contrib_shares
        
        if i == 15:  # Jan 21
            contrib_shares = 4000.00 / nav_per_share
            total_shares += contrib_shares
            transactions_data.append((
                current_date.strftime("%Y-%m-%d"),
                "20260101-01A",
                "Contribution",
                4000.00,
                contrib_shares,
                nav_per_share,
                "Additional contribution"
            ))
        
        portfolio_value = total_shares * nav_per_share
        
        nav_data.append((
            current_date.strftime("%Y-%m-%d"),
            round(portfolio_value, 2),
            round(total_shares, 4),
            round(nav_per_share, 6)
        ))
    
    cursor.executemany("""
        INSERT INTO daily_nav (date, total_portfolio_value, total_shares, nav_per_share)
        VALUES (?, ?, ?, ?)
    """, nav_data)
    
    print(f"✅ Created {len(nav_data)} days of NAV history")
    
    cursor.executemany("""
        INSERT INTO transactions (date, investor_id, type, amount, shares, nav_per_share, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, transactions_data)
    
    print(f"✅ Created {len(transactions_data)} transactions")
    
    # Generate demo trades
    symbols = ["SGOV", "TQQQ", "SPY", "QQQ"]
    trade_types = ["buy", "sell"]
    
    trades_data = []
    for i in range(50):
        trade_date = base_date + timedelta(days=random.randint(0, 40))
        symbol = random.choice(symbols)
        trade_type = random.choice(trade_types)
        quantity = random.randint(10, 500)
        price = random.uniform(50, 200)
        
        if trade_type == "buy":
            amount = -quantity * price
        else:
            amount = quantity * price
        
        commission = random.uniform(0.50, 2.00)
        
        trades_data.append((
            f"TXN{i:05d}",
            trade_date.strftime("%Y-%m-%d"),
            trade_type,
            round(amount, 2),
            round(commission, 2),
            symbol,
            quantity,
            round(price, 2),
            "Trade",
            f"Market {trade_type} of {symbol}"
        ))
    
    # Add some ACH deposits
    trades_data.append((
        "ACH001",
        "2025-12-30",
        "ach_deposit",
        15000.00,
        0,
        None,
        None,
        None,
        "ACH",
        "Initial deposit"
    ))
    trades_data.append((
        "ACH002",
        "2026-01-02",
        "ach_deposit",
        2000.00,
        0,
        None,
        None,
        None,
        "ACH",
        "Ken and Beth deposits"
    ))
    trades_data.append((
        "ACH003",
        "2026-01-21",
        "ach_deposit",
        4000.00,
        0,
        None,
        None,
        None,
        "ACH",
        "David additional"
    ))
    
    cursor.executemany("""
        INSERT INTO trades (tradier_transaction_id, date, type, amount, commission, 
                           symbol, quantity, price, category, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, trades_data)
    
    print(f"✅ Created {len(trades_data)} trades")
    
    # Add some tax events
    tax_events = [
        ("2026-01-14", "20260101-01A", "Test Withdrawal", 50.00, 18.50, "Small test withdrawal"),
    ]
    
    cursor.executemany("""
        INSERT INTO tax_events (date, investor_id, event_type, realized_gain, tax_due, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, tax_events)
    
    print("✅ Created tax events")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Demo database created: {db_path}")
    print("\nTo run dashboard with demo data:")
    print(f"  python tovito_dashboard.py {db_path}")


if __name__ == "__main__":
    create_demo_database()
