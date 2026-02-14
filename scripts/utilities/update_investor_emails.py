"""
Update Investor Emails

Interactive script to add/update email addresses for investors.

Usage:
    python scripts/update_investor_emails.py
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import re
from pathlib import Path


def validate_email(email):
    """Validate email format"""
    if not email or email.strip() == '':
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email.strip()) is not None


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def display_investors(conn):
    """Display all investors with current email status"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT investor_id, name, email, status
        FROM investors
        ORDER BY investor_id
    """)
    
    investors = cursor.fetchall()
    
    print("\n" + "=" * 70)
    print("CURRENT INVESTORS")
    print("=" * 70)
    print()
    
    if not investors:
        print("No investors found in database.")
        return []
    
    print(f"{'#':<4} {'ID':<15} {'Name':<25} {'Email':<30}")
    print("-" * 70)
    
    for idx, (investor_id, name, email, status) in enumerate(investors, 1):
        email_display = email if email else "(not set)"
        status_icon = "✅" if status == 'Active' else "⏸️"
        print(f"{idx:<4} {investor_id:<15} {name:<25} {email_display:<30} {status_icon}")
    
    print()
    return investors


def update_email(conn, investor_id, email):
    """Update email for an investor"""
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE investors
            SET email = ?, updated_at = CURRENT_TIMESTAMP
            WHERE investor_id = ?
        """, (email, investor_id))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Error updating email: {e}")
        return False


def main():
    print("=" * 70)
    print("UPDATE INVESTOR EMAILS")
    print("=" * 70)
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"\n❌ DATABASE ERROR: Database not found at {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        
        while True:
            # Display current investors
            investors = display_investors(conn)
            
            if not investors:
                break
            
            print("Options:")
            print("  • Enter investor number (1-{}) to update email".format(len(investors)))
            print("  • Enter 'done' to finish")
            print()
            
            choice = input("Select option: ").strip().lower()
            
            if choice == 'done':
                break
            
            # Try to parse as investor number
            try:
                investor_num = int(choice)
                if investor_num < 1 or investor_num > len(investors):
                    print(f"❌ Invalid selection. Please enter 1-{len(investors)}")
                    continue
                
                # Get selected investor
                investor_id, name, current_email, status = investors[investor_num - 1]
                
                print()
                print("-" * 70)
                print(f"Updating email for: {name} ({investor_id})")
                if current_email:
                    print(f"Current email: {current_email}")
                print("-" * 70)
                print()
                
                # Get new email
                new_email = input("Enter email address (or 'cancel' to skip): ").strip()
                
                if new_email.lower() == 'cancel':
                    print("Cancelled.")
                    continue
                
                # Validate email
                if not validate_email(new_email):
                    print("❌ Invalid email format. Please try again.")
                    continue
                
                # Confirm
                print()
                print(f"Set email for {name} to: {new_email}")
                confirm = input("Confirm? (yes/no): ").strip().lower()
                
                if confirm in ['yes', 'y']:
                    if update_email(conn, investor_id, new_email):
                        print(f"✅ Email updated successfully!")
                    else:
                        print("❌ Failed to update email.")
                else:
                    print("Cancelled.")
                
                print()
                
            except ValueError:
                print("❌ Invalid input. Please enter a number or 'done'.")
                continue
        
        # Final summary
        print()
        print("=" * 70)
        print("FINAL STATUS")
        print("=" * 70)
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN email IS NOT NULL AND email != '' THEN 1 ELSE 0 END) as with_email,
                SUM(CASE WHEN status = 'Active' AND (email IS NULL OR email = '') THEN 1 ELSE 0 END) as active_missing
            FROM investors
        """)
        
        total, with_email, active_missing = cursor.fetchone()
        
        print()
        print(f"Total investors: {total}")
        print(f"With email: {with_email}")
        print(f"Active investors without email: {active_missing}")
        print()
        
        if active_missing > 0:
            print(f"⚠️  Warning: {active_missing} active investor(s) still need email addresses!")
        else:
            print("✅ All active investors have email addresses!")
        
        print()
        print("Next steps:")
        print("  • Test email system: python scripts/test_email.py")
        print("  • Process contribution: python scripts/process_contribution.py")
        print("  • Process withdrawal: python scripts/process_withdrawal.py")
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
