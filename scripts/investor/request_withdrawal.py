"""
Request Withdrawal - Log withdrawal request for approval

Logs withdrawal requests from any source (email, form, verbal).
Requests must be manually approved before processing.

Usage:
    python scripts/request_withdrawal.py
    python scripts/request_withdrawal.py --investor 20260101-01A --amount 5000
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
import argparse
from pathlib import Path
from datetime import datetime


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def create_requests_table(cursor):
    """Create withdrawal_requests table if it doesn't exist"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS withdrawal_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investor_id TEXT NOT NULL,
            amount REAL NOT NULL,
            request_date TEXT NOT NULL,
            request_source TEXT,
            notes TEXT,
            status TEXT DEFAULT 'Pending',
            approved_date TEXT,
            processed_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (investor_id) REFERENCES investors(investor_id)
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_withdrawal_requests_status 
        ON withdrawal_requests(status)
    """)


def request_withdrawal_interactive(cursor):
    """Interactive withdrawal request"""
    
    # Get active investors
    cursor.execute("""
        SELECT investor_id, name, current_shares, net_investment
        FROM investors
        WHERE status = 'Active'
        ORDER BY name
    """)
    investors = cursor.fetchall()
    
    if not investors:
        print("No active investors found.")
        return False
    
    print("=" * 70)
    print("REQUEST WITHDRAWAL")
    print("=" * 70)
    print()
    
    # Get current NAV first for display
    cursor.execute("""
        SELECT nav_per_share
        FROM daily_nav
        ORDER BY date DESC
        LIMIT 1
    """)
    nav_row = cursor.fetchone()
    if not nav_row:
        print("No NAV data available.")
        return False
    nav = nav_row[0]
    
    print("Select investor:")
    for i, (inv_id, name, shares, net_inv) in enumerate(investors, 1):
        current_value = shares * nav
        unrealized_gain = current_value - net_inv
        
        gain_display = ""
        if unrealized_gain > 0:
            gain_display = f" | Gain: ${unrealized_gain:,.2f} ✓"
        elif unrealized_gain < 0:
            gain_display = f" | Loss: ${abs(unrealized_gain):,.2f} ⚠️"
        else:
            gain_display = " | Break-even"
            
        print(f"  {i}. {name} ({inv_id})")
        print(f"     Shares: {shares:,.4f} | Value: ${current_value:,.2f}{gain_display}")
    
    print()
    choice = input("Select investor (1-{}): ".format(len(investors))).strip()
    
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(investors):
            print("Invalid selection.")
            return False
        
        investor_id, name, shares, net_investment = investors[idx]
    except (ValueError, IndexError):
        print("Invalid selection.")
        return False
    
    # Get current NAV
    cursor.execute("""
        SELECT nav_per_share
        FROM daily_nav
        ORDER BY date DESC
        LIMIT 1
    """)
    nav_row = cursor.fetchone()
    
    if not nav_row:
        print("No NAV data available.")
        return False
    
    nav = nav_row[0]
    current_value = shares * nav
    unrealized_gain = max(0, current_value - net_investment)
    tax_liability = unrealized_gain * 0.37
    available_to_withdraw = current_value - tax_liability
    
    print()
    print(f"Selected: {name}")
    print(f"Current shares: {shares:,.4f}")
    print(f"Current NAV: ${nav:.4f}")
    print(f"Current value: ${current_value:,.2f}")
    print(f"Net investment: ${net_investment:,.2f}")
    print(f"Unrealized gain: ${unrealized_gain:,.2f}")
    print(f"Tax liability (37%): ${tax_liability:,.2f}")
    print(f"Available to withdraw: ${available_to_withdraw:,.2f}")
    print()
    
    # Get withdrawal amount
    amount_str = input("Withdrawal amount: $").strip()
    
    try:
        amount = float(amount_str.replace(',', ''))
        if amount <= 0:
            print("Amount must be positive.")
            return False
        if amount > available_to_withdraw:
            print()
            print(f"⚠️  Withdrawal amount (${amount:,.2f}) exceeds available balance!")
            print(f"   Maximum available: ${available_to_withdraw:,.2f}")
            print(f"   (Current value ${current_value:,.2f} - Tax liability ${tax_liability:,.2f})")
            print()
            proceed = input("Continue anyway? (yes/no): ").strip().lower()
            if proceed not in ['yes', 'y']:
                return False
    except ValueError:
        print("Invalid amount.")
        return False
    
    # Get source
    print()
    print("Request source:")
    print("  1. Email")
    print("  2. Form submission")
    print("  3. Verbal request")
    print("  4. Other")
    source_choice = input("Select (1-4): ").strip()
    
    source_map = {
        '1': 'Email',
        '2': 'Form',
        '3': 'Verbal',
        '4': 'Other'
    }
    source = source_map.get(source_choice, 'Other')
    
    # Get notes
    notes = input("Notes (optional): ").strip() or None
    
    # Calculate estimated tax impact
    proportion = amount / current_value
    realized_gain = unrealized_gain * proportion
    principal_portion = amount - realized_gain
    
    print()
    print("=" * 70)
    print("WITHDRAWAL REQUEST SUMMARY")
    print("=" * 70)
    print()
    print(f"Investor: {name} ({investor_id})")
    print(f"Requested amount: ${amount:,.2f}")
    print(f"Source: {source}")
    if notes:
        print(f"Notes: {notes}")
    print()
    print("BREAKDOWN:")
    print(f"  Withdrawal amount:    ${amount:,.2f}")
    print(f"  Principal portion:    ${principal_portion:,.2f}")
    print(f"  Gain portion:         ${realized_gain:,.2f}")
    print()
    print("TAX TREATMENT:")
    print(f"  NO tax withheld at withdrawal")
    print(f"  Tax handled via quarterly payments")
    print(f"  Investor receives: ${amount:,.2f} (full amount)")
    print()
    print("Status: PENDING APPROVAL")
    print()
    
    confirm = input("Log this withdrawal request? (yes/no): ").strip().lower()
    
    if confirm not in ['yes', 'y']:
        print("Request cancelled.")
        return False
    
    # Log request
    cursor.execute("""
        INSERT INTO withdrawal_requests 
        (investor_id, requested_amount, request_date, request_method, notes, status)
        VALUES (?, ?, ?, ?, ?, 'Pending')
    """, (
        investor_id,
        amount,
        datetime.now().date().isoformat(),
        source,
        notes
    ))
    
    request_id = cursor.lastrowid
    
    print()
    print(f"✅ Withdrawal request logged (ID: {request_id})")
    print()
    print("Next steps:")
    print("  1. Review: python scripts/list_withdrawal_requests.py")
    print("  2. Approve: python scripts/approve_withdrawal.py")
    print()
    
    return True


def request_withdrawal_command(cursor, investor_id, amount, source='Email', notes=None):
    """Command-line withdrawal request"""
    
    # Verify investor exists
    cursor.execute("""
        SELECT name, current_shares, net_investment
        FROM investors
        WHERE investor_id = ? AND status = 'Active'
    """, (investor_id,))
    
    investor = cursor.fetchone()
    if not investor:
        print(f"Investor {investor_id} not found or inactive.")
        return False
    
    name, shares, net_investment = investor
    
    # Get current NAV
    cursor.execute("""
        SELECT nav_per_share
        FROM daily_nav
        ORDER BY date DESC
        LIMIT 1
    """)
    nav_row = cursor.fetchone()
    
    if not nav_row:
        print("No NAV data available.")
        return False
    
    nav = nav_row[0]
    current_value = shares * nav
    
    if amount > current_value:
        print(f"Amount ${amount:,.2f} exceeds current value ${current_value:,.2f}.")
        return False
    
    # Log request
    cursor.execute("""
        INSERT INTO withdrawal_requests 
        (investor_id, requested_amount, request_date, request_method, notes, status)
        VALUES (?, ?, ?, ?, ?, 'Pending')
    """, (
        investor_id,
        amount,
        datetime.now().date().isoformat(),
        source,
        notes
    ))
    
    request_id = cursor.lastrowid
    
    print(f"✅ Withdrawal request logged for {name}")
    print(f"   Request ID: {request_id}")
    print(f"   Amount: ${amount:,.2f}")
    print(f"   Status: PENDING APPROVAL")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Request withdrawal')
    parser.add_argument('--investor', help='Investor ID')
    parser.add_argument('--amount', type=float, help='Withdrawal amount')
    parser.add_argument('--source', default='Email', help='Request source')
    parser.add_argument('--notes', help='Notes')
    
    args = parser.parse_args()
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create table if needed
        create_requests_table(cursor)
        conn.commit()
        
        # Process request
        if args.investor and args.amount:
            success = request_withdrawal_command(
                cursor, 
                args.investor, 
                args.amount, 
                args.source, 
                args.notes
            )
        else:
            success = request_withdrawal_interactive(cursor)
        
        if success:
            conn.commit()
        
        conn.close()
        return success
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
