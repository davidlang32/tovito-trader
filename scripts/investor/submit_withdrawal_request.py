"""
Submit Withdrawal Request

Log a withdrawal request from an investor for manual approval.
Use when investor requests withdrawal via email, phone, or in person.

Usage:
    python scripts/submit_withdrawal_request.py
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


def get_active_investors(cursor):
    """Get list of active investors"""
    # Get current NAV
    cursor.execute("""
        SELECT nav_per_share
        FROM daily_nav
        ORDER BY date DESC
        LIMIT 1
    """)
    nav_row = cursor.fetchone()
    nav = nav_row[0] if nav_row else 1.0
    
    cursor.execute("""
        SELECT investor_id, name, current_shares, (current_shares * ?) as current_value
        FROM investors
        WHERE status = 'Active'
        ORDER BY name
    """, (nav,))
    return cursor.fetchall()


def submit_withdrawal_request():
    """Submit a withdrawal request"""
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    print("=" * 70)
    print("SUBMIT WITHDRAWAL REQUEST")
    print("=" * 70)
    print()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get active investors
        investors = get_active_investors(cursor)
        
        if not investors:
            print("❌ No active investors found")
            return False
        
        # Show investors
        print("Active Investors:")
        for i, (inv_id, name, shares, value) in enumerate(investors, 1):
            print(f"  {i}. {name} ({inv_id}) - {shares:,.2f} shares, ${value:,.2f}")
        print()
        
        # Select investor
        while True:
            try:
                selection = input("Select investor (number): ").strip()
                idx = int(selection) - 1
                if 0 <= idx < len(investors):
                    investor_id, investor_name, current_shares, current_value = investors[idx]
                    break
                print("Invalid selection. Try again.")
            except ValueError:
                print("Please enter a number.")
        
        print()
        print(f"Selected: {investor_name}")
        print(f"Current value: ${current_value:,.2f}")
        print(f"Current shares: {current_shares:,.4f}")
        print()
        
        # Get withdrawal amount
        while True:
            try:
                amount_str = input("Withdrawal amount requested: $").strip().replace(',', '')
                amount = float(amount_str)
                if amount > 0:
                    if amount > current_value:
                        print(f"⚠️  Amount exceeds current value (${current_value:,.2f})")
                        confirm = input("Continue anyway? (yes/no): ").strip().lower()
                        if confirm not in ['yes', 'y']:
                            continue
                    break
                print("Amount must be positive.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Get request method
        print()
        print("Request method:")
        print("  1. Email")
        print("  2. Phone")
        print("  3. In Person")
        print("  4. Form Submission")
        print("  5. Other")
        
        method_map = {
            '1': 'Email',
            '2': 'Phone',
            '3': 'In Person',
            '4': 'Form',
            '5': 'Other'
        }
        
        while True:
            method_choice = input("Select method (number): ").strip()
            if method_choice in method_map:
                request_method = method_map[method_choice]
                break
            print("Invalid selection.")
        
        # Get notes
        print()
        notes = input("Notes (optional): ").strip() or None
        
        # Show summary
        print()
        print("=" * 70)
        print("WITHDRAWAL REQUEST SUMMARY")
        print("=" * 70)
        print(f"Investor:        {investor_name} ({investor_id})")
        print(f"Amount:          ${amount:,.2f}")
        print(f"Current Value:   ${current_value:,.2f}")
        print(f"Request Method:  {request_method}")
        print(f"Request Date:    {datetime.now().date()}")
        if notes:
            print(f"Notes:           {notes}")
        print()
        
        confirm = input("Submit this withdrawal request? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            print("Request cancelled.")
            return False
        
        # Insert request
        cursor.execute("""
            INSERT INTO withdrawal_requests 
            (investor_id, request_date, requested_amount, request_method, notes, status)
            VALUES (?, ?, ?, ?, ?, 'Pending')
        """, (
            investor_id,
            datetime.now().date().isoformat(),
            amount,
            request_method,
            notes
        ))
        
        request_id = cursor.lastrowid
        
        conn.commit()
        
        print()
        print("=" * 70)
        print("✅ WITHDRAWAL REQUEST SUBMITTED")
        print("=" * 70)
        print(f"Request ID: {request_id}")
        print(f"Status: Pending Approval")
        print()
        print("Next steps:")
        print("  1. View pending: python scripts/view_pending_withdrawals.py")
        print("  2. Process: python scripts/process_withdrawal_enhanced.py")
        print()
        
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
        success = submit_withdrawal_request()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
