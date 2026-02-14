"""
Database Migration: Enhanced NAV System
Adds tables for transaction tracking, reconciliation, and staging

Run this ONCE to add new tables to your database.

Usage:
    python scripts/migrate_enhanced_nav_system.py
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
from pathlib import Path
from datetime import datetime


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def migrate_database():
    """Add new tables for enhanced NAV system"""
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 70)
        print("DATABASE MIGRATION - ENHANCED NAV SYSTEM")
        print("=" * 70)
        print()
        
        # Table 1: Tradier Transactions
        print("Creating table: tradier_transactions...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tradier_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                transaction_type TEXT NOT NULL,
                amount FLOAT NOT NULL,
                description TEXT,
                tradier_transaction_id TEXT UNIQUE,
                timestamp DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ tradier_transactions created")
        
        # Index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tradier_trans_date 
            ON tradier_transactions(date)
        """)
        
        # Table 2: Pending Contributions
        print("Creating table: pending_contributions...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_contributions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_date DATE NOT NULL,
                amount FLOAT NOT NULL,
                tradier_transaction_id TEXT,
                investor_id TEXT,
                status TEXT DEFAULT 'pending',
                shares_allocated FLOAT,
                nav_at_allocation FLOAT,
                admin_notified_at DATETIME,
                allocated_at DATETIME,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (investor_id) REFERENCES investors(investor_id)
            )
        """)
        print("✅ pending_contributions created")
        
        # Table 3: Daily Reconciliation
        print("Creating table: daily_reconciliation...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_reconciliation (
                date DATE PRIMARY KEY,
                tradier_balance FLOAT,
                calculated_portfolio_value FLOAT,
                difference FLOAT,
                total_shares FLOAT,
                nav_per_share FLOAT,
                new_deposits FLOAT DEFAULT 0,
                new_withdrawals FLOAT DEFAULT 0,
                unallocated_deposits INTEGER DEFAULT 0,
                status TEXT,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ daily_reconciliation created")
        
        # Table 4: Transaction Sync Status
        print("Creating table: transaction_sync_status...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transaction_sync_status (
                sync_date DATE PRIMARY KEY,
                last_sync_time DATETIME,
                transactions_found INTEGER DEFAULT 0,
                deposits_count INTEGER DEFAULT 0,
                withdrawals_count INTEGER DEFAULT 0,
                trades_count INTEGER DEFAULT 0,
                status TEXT,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ transaction_sync_status created")
        
        # Table 5: Staged Contributions (for future use)
        print("Creating table: staged_contributions...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staged_contributions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investor_id TEXT NOT NULL,
                amount FLOAT NOT NULL,
                requested_date DATE,
                approved_nav FLOAT,
                approved_shares FLOAT,
                status TEXT DEFAULT 'requested',
                deposit_received_date DATE,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                approved_at DATETIME,
                completed_at DATETIME,
                FOREIGN KEY (investor_id) REFERENCES investors(investor_id)
            )
        """)
        print("✅ staged_contributions created")
        
        conn.commit()
        
        # Verify all tables exist
        print()
        print("Verifying tables...")
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name IN (
                'tradier_transactions',
                'pending_contributions',
                'daily_reconciliation',
                'transaction_sync_status',
                'staged_contributions'
            )
            ORDER BY name
        """)
        
        tables = cursor.fetchall()
        
        print()
        print("=" * 70)
        print("MIGRATION SUMMARY")
        print("=" * 70)
        print()
        print(f"Tables created: {len(tables)}/5")
        for table in tables:
            print(f"  ✅ {table[0]}")
        
        if len(tables) == 5:
            print()
            print("🎉 Migration completed successfully!")
            print()
            print("New capabilities:")
            print("  • Tradier transaction tracking")
            print("  • Pending contribution management")
            print("  • Daily reconciliation")
            print("  • Transaction sync monitoring")
            print("  • Staged contribution system")
            print()
            return True
        else:
            print()
            print("⚠️  Warning: Not all tables created")
            return False
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"\n❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print()
    print("This will add 5 new tables to your database:")
    print()
    print("  1. tradier_transactions - Track all Tradier activity")
    print("  2. pending_contributions - Manage unallocated deposits")
    print("  3. daily_reconciliation - Daily validation checks")
    print("  4. transaction_sync_status - Monitor sync process")
    print("  5. staged_contributions - Pre-approved deposit requests")
    print()
    
    confirm = input("Proceed with migration? (yes/no): ").strip().lower()
    
    if confirm not in ['yes', 'y']:
        print("Migration cancelled.")
        return
    
    print()
    success = migrate_database()
    
    if success:
        print()
        print("=" * 70)
        print("NEXT STEPS:")
        print("=" * 70)
        print()
        print("1. Run transaction sync:")
        print("   python scripts/sync_tradier_transactions.py")
        print()
        print("2. Run enhanced daily NAV update:")
        print("   python scripts/daily_nav_enhanced.py")
        print()
        print("3. Check for pending contributions:")
        print("   python scripts/view_pending_contributions.py")
        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
