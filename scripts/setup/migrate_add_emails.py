"""
Database Migration: Add Email Column to Investors Table

This script adds an email column to the investors table to support
email communication features.
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
from pathlib import Path
import sys

def check_column_exists(cursor, table, column):
    """Check if column already exists"""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

def add_email_column():
    """Add email column to investors table"""
    
    print("=" * 60)
    print("DATABASE MIGRATION: ADD EMAIL COLUMN")
    print("=" * 60)
    print()
    
    # Database path
    db_path = Path(__file__).parent.parent / "data" / "tovito.db"
    
    if not db_path.exists():
        print("❌ ERROR: Database not found!")
        print(f"   Looking for: {db_path}")
        print()
        print("💡 TIP: Make sure you're in the tovito-trader directory")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current schema
        print("📊 Checking current schema...")
        cursor.execute("PRAGMA table_info(investors)")
        current_columns = [row[1] for row in cursor.fetchall()]
        print(f"   Current columns: {', '.join(current_columns)}")
        print()
        
        # Check if email column already exists
        if 'email' in current_columns:
            print("✅ Email column already exists!")
            print("   No migration needed.")
            print()
            print("📝 Next steps:")
            print("   1. Add/update emails: python scripts/update_investor_emails.py")
            print("   2. Test email system: python run.py email --test")
            conn.close()
            return True
        
        # Add email column
        print("🔧 Adding email column...")
        print("   SQL: ALTER TABLE investors ADD COLUMN email TEXT")
        cursor.execute("ALTER TABLE investors ADD COLUMN email TEXT")
        conn.commit()
        print()
        print("✅ Email column added successfully!")
        print()
        
        # Verify migration
        print("🔍 Verifying migration...")
        cursor.execute("PRAGMA table_info(investors)")
        new_columns = [row[1] for row in cursor.fetchall()]
        print(f"   New columns: {', '.join(new_columns)}")
        print()
        
        if 'email' in new_columns:
            print("✅ MIGRATION COMPLETE!")
            print()
            print("📝 Next steps:")
            print("   1. Add email addresses: python scripts/update_investor_emails.py")
            print("   2. Test email system: python run.py email --test")
            print("   3. Start using automated emails!")
        else:
            print("❌ ERROR: Migration verification failed!")
            print("   Email column not found after migration")
            return False
        
        conn.close()
        print()
        print("=" * 60)
        return True
        
    except sqlite3.Error as e:
        print(f"❌ DATABASE ERROR: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    success = add_email_column()
    sys.exit(0 if success else 1)
