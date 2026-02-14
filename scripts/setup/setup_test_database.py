"""
Test Database Setup Script

Creates a fresh test database with sample data for testing workflows.

Usage:
    python scripts/setup_test_database.py
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

def create_test_database():
    """Create fresh test database with sample data"""
    
    print("=" * 70)
    print("TEST DATABASE SETUP")
    print("=" * 70)
    print()
    
    # Database path
    test_db = Path(__file__).parent.parent / "data" / "tovito_test.db"
    
    # Delete existing test database
    if test_db.exists():
        print(f"⚠️  Removing existing test database: {test_db}")
        test_db.unlink()
        print()
    
    print(f"📁 Creating test database: {test_db}")
    print()
    
    # Create database
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    
    # Create tables
    print("🔨 Creating tables...")
    
    # Investors table
    cursor.execute("""
        CREATE TABLE investors (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            initial_capital REAL NOT NULL,
            join_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active',
            email TEXT,
            current_shares REAL NOT NULL DEFAULT 0,
            net_investment REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("   ✅ investors table created")
    
    # NAV history table
    cursor.execute("""
        CREATE TABLE nav_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            nav_per_share REAL NOT NULL,
            total_portfolio_value REAL NOT NULL,
            total_shares REAL NOT NULL,
            daily_change_pct REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("   ✅ nav_history table created")
    
    # Transactions table
    cursor.execute("""
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investor_id TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            share_price REAL NOT NULL,
            shares REAL NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (investor_id) REFERENCES investors(id)
        )
    """)
    print("   ✅ transactions table created")
    
    # Tax events table
    cursor.execute("""
        CREATE TABLE tax_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investor_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            amount REAL NOT NULL,
            realized_gain REAL NOT NULL,
            tax_due REAL NOT NULL,
            FOREIGN KEY (investor_id) REFERENCES investors(id)
        )
    """)
    print("   ✅ tax_events table created")
    
    # System logs table
    cursor.execute("""
        CREATE TABLE system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            log_level TEXT NOT NULL,
            message TEXT NOT NULL,
            details TEXT
        )
    """)
    print("   ✅ system_logs table created")
    
    # Email history table
    cursor.execute("""
        CREATE TABLE email_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,
            error_message TEXT
        )
    """)
    print("   ✅ email_history table created")
    
    print()
    print("👥 Adding test investors...")
    
    # Add test investors
    today = datetime.now().strftime("%Y%m%d")
    
    investors = [
        ("20260101-01A", "Test Investor 1", 10000.00, "2026-01-01", "youremail+test1@gmail.com"),
        ("20260101-02A", "Test Investor 2", 15000.00, "2026-01-01", "youremail+test2@gmail.com"),
        ("20260101-03A", "Test Investor 3", 5000.00, "2026-01-01", "youremail+test3@gmail.com"),
    ]
    
    for inv_id, name, capital, join_date, email in investors:
        cursor.execute("""
            INSERT INTO investors 
            (id, name, initial_capital, join_date, status, email, current_shares, net_investment)
            VALUES (?, ?, ?, ?, 'Active', ?, ?, ?)
        """, (inv_id, name, capital, join_date, email, capital, capital))
        print(f"   ✅ Added: {name} (${capital:,.2f})")
    
    print()
    print("📈 Setting initial NAV...")
    
    # Initial NAV
    total_capital = sum(i[2] for i in investors)
    initial_nav = 1.00
    
    cursor.execute("""
        INSERT INTO nav_history 
        (date, nav_per_share, total_portfolio_value, total_shares)
        VALUES (?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d"), initial_nav, total_capital, total_capital))
    print(f"   ✅ NAV per share: ${initial_nav:.4f}")
    print(f"   ✅ Total portfolio: ${total_capital:,.2f}")
    print(f"   ✅ Total shares: {total_capital:,.4f}")
    
    print()
    print("📝 Recording initial transactions...")
    
    # Initial capital transactions
    for inv_id, name, capital, join_date, email in investors:
        cursor.execute("""
            INSERT INTO transactions 
            (investor_id, transaction_type, amount, share_price, shares, date)
            VALUES (?, 'Initial', ?, ?, ?, ?)
        """, (inv_id, capital, initial_nav, capital, join_date))
        print(f"   ✅ Recorded initial capital: {name}")
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print()
    print("=" * 70)
    print("✅ TEST DATABASE CREATED SUCCESSFULLY!")
    print("=" * 70)
    print()
    print("📊 Database Summary:")
    print(f"   Location: {test_db}")
    print(f"   Investors: {len(investors)}")
    print(f"   Total Capital: ${total_capital:,.2f}")
    print(f"   Initial NAV: ${initial_nav:.4f}")
    print()
    print("⚠️  NOTE: Test emails are configured as youremail+testN@gmail.com")
    print("   Please update these in the database or via update_investor_emails.py")
    print()
    print("📝 Next steps:")
    print("   1. Update .env to point to test database (optional)")
    print("   2. Update test investor emails: python scripts/update_investor_emails.py")
    print("   3. Run tests: python scripts/run_tests.py data/tovito_test.db")
    print("   4. Test workflows: python scripts/process_contribution.py")
    print()
    print("🗑️  To remove test database:")
    print(f"   del {test_db}")
    print()

if __name__ == "__main__":
    try:
        create_test_database()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
