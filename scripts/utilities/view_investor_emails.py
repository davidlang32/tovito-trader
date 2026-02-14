"""
View Investor Emails

Display all investor email addresses.

Usage:
    python scripts/view_investor_emails.py
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
from pathlib import Path


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def main():
    print("=" * 70)
    print("INVESTOR EMAIL ADDRESSES")
    print("=" * 70)
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"\n❌ DATABASE ERROR: Database not found at {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all investors with emails
        cursor.execute("""
            SELECT investor_id, name, email, status
            FROM investors
            ORDER BY investor_id
        """)
        
        investors = cursor.fetchall()
        
        if not investors:
            print("\nNo investors found in database.")
            conn.close()
            return
        
        print()
        print(f"{'ID':<15} {'Name':<30} {'Email':<35} {'Status':<10}")
        print("-" * 70)
        
        for investor_id, name, email, status in investors:
            email_display = email if email else "(not set)"
            status_icon = "✅" if status == 'Active' else "⏸️"
            print(f"{investor_id:<15} {name:<30} {email_display:<35} {status_icon} {status:<10}")
        
        # Summary
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN email IS NOT NULL AND email != '' THEN 1 ELSE 0 END) as with_email,
                SUM(CASE WHEN email IS NULL OR email = '' THEN 1 ELSE 0 END) as without_email,
                SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN status = 'Active' AND (email IS NULL OR email = '') THEN 1 ELSE 0 END) as active_missing
            FROM investors
        """)
        
        total, with_email, without_email, active, active_missing = cursor.fetchone()
        
        print()
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print()
        print(f"Total investors:              {total}")
        print(f"Active investors:             {active}")
        print(f"With email:                   {with_email}")
        print(f"Without email:                {without_email}")
        print()
        
        if active_missing > 0:
            print(f"⚠️  Active investors missing email: {active_missing}")
            print()
            print("To add emails: python scripts/update_investor_emails.py")
        else:
            print("✅ All active investors have email addresses!")
        
        print()
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"\n❌ DATABASE ERROR: {e}")
        return
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
