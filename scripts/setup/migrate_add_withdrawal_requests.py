"""
Database Migration - Withdrawal Requests Tracking

Adds table for tracking withdrawal requests with approval workflow.

Run once to add the table to your database.
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
from pathlib import Path
from datetime import datetime


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def migrate():
    """Add withdrawal requests table"""
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    print("=" * 70)
    print("DATABASE MIGRATION - WITHDRAWAL REQUESTS")
    print("=" * 70)
    print()
    print("This will add the withdrawal_requests table for tracking:")
    print("  • Withdrawal requests from investors")
    print("  • Manual approval workflow")
    print("  • Request method tracking (email/form/verbal)")
    print("  • Processing history")
    print()
    
    confirm = input("Proceed with migration? (yes/no): ").strip().lower()
    
    if confirm not in ['yes', 'y']:
        print("Migration cancelled.")
        return False
    
    print()
    print("Running migration...")
    print()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name = 'withdrawal_requests'
        """)
        existing = cursor.fetchone()
        
        if existing:
            print("⚠️  Warning: withdrawal_requests table already exists")
            overwrite = input("Continue anyway? (yes/no): ").strip().lower()
            if overwrite not in ['yes', 'y']:
                print("Migration cancelled.")
                conn.close()
                return False
            print()
        
        # Create withdrawal_requests table
        print("💰 Creating withdrawal_requests table...")
        cursor.execute("""
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
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (investor_id) REFERENCES investors(investor_id)
            )
        """)
        print("   ✅ withdrawal_requests table created")
        
        # Create indexes
        print("🔍 Creating indexes...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_withdrawal_requests_investor 
            ON withdrawal_requests(investor_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_withdrawal_requests_status 
            ON withdrawal_requests(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_withdrawal_requests_date 
            ON withdrawal_requests(request_date)
        """)
        print("   ✅ Indexes created")
        
        conn.commit()
        
        # Verify table
        print()
        print("🔍 Verifying migration...")
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name = 'withdrawal_requests'
        """)
        table = cursor.fetchone()
        
        if table:
            cursor.execute("SELECT COUNT(*) FROM withdrawal_requests")
            count = cursor.fetchone()[0]
            print(f"   ✅ withdrawal_requests: {count} rows")
        
        conn.close()
        
        print()
        print("=" * 70)
        print("✅ MIGRATION COMPLETE!")
        print("=" * 70)
        print()
        print("New table added:")
        print("  • withdrawal_requests - Track withdrawal requests and approvals")
        print()
        print("Request Statuses:")
        print("  • Pending - Awaiting your approval")
        print("  • Approved - Approved, ready to process")
        print("  • Processed - Completed")
        print("  • Rejected - Denied")
        print()
        print("Next steps:")
        print("  1. Submit request: python scripts/submit_withdrawal_request.py")
        print("  2. View pending: python scripts/view_pending_withdrawals.py")
        print("  3. Process: python scripts/process_withdrawal_enhanced.py")
        print()
        
        return True
        
    except sqlite3.Error as e:
        print(f"\n❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = migrate()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
