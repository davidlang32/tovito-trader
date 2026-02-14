"""
Add Prospect - Add potential investor to database

Interactive script to add a single prospect to tracking.
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


def add_prospect():
    """Add a prospect to the database"""
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    print("=" * 70)
    print("ADD PROSPECT TO DATABASE")
    print("=" * 70)
    print()
    
    # Get prospect information
    name = input("Prospect name: ").strip()
    if not name:
        print("❌ Name is required.")
        return False
    
    email = input("Email address: ").strip()
    if not email:
        print("❌ Email is required.")
        return False
    
    phone = input("Phone (optional): ").strip() or None
    source = input("Source (e.g., 'Referral', 'LinkedIn', optional): ").strip() or None
    notes = input("Notes (optional): ").strip() or None
    
    print()
    print("Prospect Information:")
    print(f"  Name:   {name}")
    print(f"  Email:  {email}")
    print(f"  Phone:  {phone or '(none)'}")
    print(f"  Source: {source or '(none)'}")
    print(f"  Notes:  {notes or '(none)'}")
    print()
    
    confirm = input("Add this prospect? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y']:
        print("Cancelled.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if email already exists
        cursor.execute("SELECT name FROM prospects WHERE email = ?", (email,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"\n⚠️  Email already exists for: {existing[0]}")
            overwrite = input("Update this prospect? (yes/no): ").strip().lower()
            if overwrite not in ['yes', 'y']:
                print("Cancelled.")
                conn.close()
                return False
            
            # Update existing prospect
            cursor.execute("""
                UPDATE prospects
                SET name = ?, phone = ?, source = ?, notes = ?, updated_at = ?
                WHERE email = ?
            """, (name, phone, source, notes, datetime.now().isoformat(), email))
            
            print(f"\n✅ Prospect updated: {name}")
        else:
            # Insert new prospect
            cursor.execute("""
                INSERT INTO prospects (name, email, phone, date_added, source, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, email, phone, datetime.now().date().isoformat(), source, notes))
            
            print(f"\n✅ Prospect added: {name}")
        
        conn.commit()
        
        # Show total prospects
        cursor.execute("SELECT COUNT(*) FROM prospects WHERE status = 'Active'")
        total = cursor.fetchone()[0]
        print(f"   Total active prospects: {total}")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"\n❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = add_prospect()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
