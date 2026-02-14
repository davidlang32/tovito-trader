"""
Database Migration - Communications Tracking

Adds tables for tracking:
- Prospects (potential investors)
- Prospect communications (emails sent to prospects)  
- Investor communications (emails sent to current investors)

Run once to add the tables to your database.
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
    """Add communication tracking tables"""
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    print("=" * 70)
    print("DATABASE MIGRATION - COMMUNICATIONS TRACKING")
    print("=" * 70)
    print()
    print("This will add 3 new tables:")
    print("  1. prospects - Track potential investors")
    print("  2. prospect_communications - Log emails to prospects")
    print("  3. investor_communications - Log emails to current investors")
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
        
        # Check if tables already exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('prospects', 'prospect_communications', 'investor_communications')
        """)
        existing = cursor.fetchall()
        
        if existing:
            print(f"⚠️  Warning: Some tables already exist: {[t[0] for t in existing]}")
            overwrite = input("Continue anyway? (yes/no): ").strip().lower()
            if overwrite not in ['yes', 'y']:
                print("Migration cancelled.")
                conn.close()
                return False
            print()
        
        # 1. PROSPECTS TABLE
        print("📊 Creating prospects table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prospects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT,
                date_added TEXT NOT NULL,
                status TEXT DEFAULT 'Active',
                source TEXT,
                notes TEXT,
                last_contact_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("   ✅ prospects table created")
        
        # 2. PROSPECT COMMUNICATIONS TABLE
        print("📧 Creating prospect_communications table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prospect_communications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prospect_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                communication_type TEXT NOT NULL,
                subject TEXT,
                report_period TEXT,
                status TEXT DEFAULT 'Sent',
                error_message TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (prospect_id) REFERENCES prospects(id)
            )
        """)
        print("   ✅ prospect_communications table created")
        
        # 3. INVESTOR COMMUNICATIONS TABLE
        print("📨 Creating investor_communications table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS investor_communications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investor_id TEXT NOT NULL,
                date TEXT NOT NULL,
                communication_type TEXT NOT NULL,
                subject TEXT,
                report_period TEXT,
                status TEXT DEFAULT 'Sent',
                error_message TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (investor_id) REFERENCES investors(investor_id)
            )
        """)
        print("   ✅ investor_communications table created")
        
        # Create indexes for performance
        print("🔍 Creating indexes...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_prospects_email 
            ON prospects(email)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_prospects_status 
            ON prospects(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_prospect_comms_prospect 
            ON prospect_communications(prospect_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_prospect_comms_date 
            ON prospect_communications(date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_investor_comms_investor 
            ON investor_communications(investor_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_investor_comms_date 
            ON investor_communications(date)
        """)
        print("   ✅ Indexes created")
        
        conn.commit()
        
        # Verify tables
        print()
        print("🔍 Verifying migration...")
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('prospects', 'prospect_communications', 'investor_communications')
            ORDER BY name
        """)
        tables = cursor.fetchall()
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"   ✅ {table[0]}: {count} rows")
        
        conn.close()
        
        print()
        print("=" * 70)
        print("✅ MIGRATION COMPLETE!")
        print("=" * 70)
        print()
        print("New tables added:")
        print("  • prospects - Track potential investors")
        print("  • prospect_communications - Email history for prospects")
        print("  • investor_communications - Email history for investors")
        print()
        print("Next steps:")
        print("  1. Add prospects: python scripts/add_prospect.py")
        print("  2. Send prospect report: python scripts/send_prospect_report.py")
        print("  3. View communications: python scripts/view_communications.py")
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
