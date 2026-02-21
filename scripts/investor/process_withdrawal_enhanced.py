"""
Process Withdrawal (Enhanced) - With Manual Approval & Tax Calculation

DEPRECATED: This script is maintained for backwards compatibility.
For new withdrawals, use the fund flow workflow instead:
    python scripts/investor/submit_fund_flow.py      # Submit request
    python scripts/investor/match_fund_flow.py        # Match to brokerage ACH
    python scripts/investor/process_fund_flow.py      # Execute share accounting

The fund flow workflow provides full lifecycle tracking, brokerage ACH matching,
and audit trail via the fund_flow_requests table.

Complete withdrawal processing with:
- Manual approval workflow
- Tax calculation (37% on realized gains)
- Email confirmations
- Database logging

Usage:
    python scripts/investor/process_withdrawal_enhanced.py
    python scripts/investor/process_withdrawal_enhanced.py --request-id 5
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Email service
try:
    from src.automation.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError as e:
    EMAIL_AVAILABLE = False
    print(f"⚠️  Email service not available: {e}")


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def get_pending_requests(cursor):
    """Get pending withdrawal requests"""
    
    # Get current NAV first
    cursor.execute("""
        SELECT nav_per_share
        FROM daily_nav
        ORDER BY date DESC
        LIMIT 1
    """)
    nav_row = cursor.fetchone()
    nav_per_share = nav_row[0] if nav_row else 1.0
    
    cursor.execute("""
        SELECT 
            wr.id,
            wr.investor_id,
            i.name,
            i.email,
            wr.request_date,
            wr.requested_amount,
            wr.request_method,
            wr.notes,
            i.current_shares,
            (i.current_shares * ?) as current_value,
            i.net_investment
        FROM withdrawal_requests wr
        JOIN investors i ON wr.investor_id = i.investor_id
        WHERE wr.status IN ('Pending', 'Approved')
        ORDER BY wr.request_date
    """, (nav_per_share,))
    return cursor.fetchall()


def calculate_withdrawal_details(requested_amount, current_value, current_shares, net_investment, nav_per_share, tax_rate=0.37):
    """Calculate withdrawal amounts (NO TAX WITHHOLDING)"""
    
    # Calculate unrealized gain
    unrealized_gain = max(0, current_value - net_investment)
    
    # Calculate proportion being withdrawn
    if current_value > 0:
        proportion = requested_amount / current_value
    else:
        return None
    
    # Calculate shares to sell
    shares_to_sell = current_shares * proportion
    
    # Calculate realized gain (proportional to withdrawal)
    realized_gain = unrealized_gain * proportion
    
    # NO TAX WITHHELD - handled via quarterly payments
    tax_withheld = 0
    net_proceeds = requested_amount  # Full amount
    
    # Calculate new position
    new_shares = current_shares - shares_to_sell
    new_value = new_shares * nav_per_share
    new_net_investment = net_investment * (1 - proportion)
    
    return {
        'requested_amount': requested_amount,
        'proportion': proportion,
        'shares_to_sell': shares_to_sell,
        'realized_gain': realized_gain,
        'tax_withheld': 0,  # NO TAX
        'net_proceeds': requested_amount,  # FULL AMOUNT
        'new_shares': new_shares,
        'new_value': new_value,
        'new_net_investment': new_net_investment
    }


def send_withdrawal_confirmation(investor_name, investor_email, details, admin_email):
    """Send withdrawal confirmation email"""
    
    if not EMAIL_AVAILABLE:
        return False
    
    subject = "Withdrawal Processed - Tovito Trader"
    
    message = f"""Dear {investor_name},

Your withdrawal has been processed successfully.

WITHDRAWAL SUMMARY
==================
Withdrawal Amount:     ${details['requested_amount']:,.2f}
Realized Gain:         ${details['realized_gain']:,.2f}
Net Proceeds:          ${details['requested_amount']:,.2f} (full amount)

TAX TREATMENT
=============
No tax was withheld from this withdrawal. Your tax liability is handled 
through our quarterly estimated tax payment system.

UPDATED POSITION
================
Shares Remaining:      {details['new_shares']:,.4f}
Current Value (Gross): ${details['new_value']:,.2f}

IMPORTANT TAX INFORMATION
=========================
Tax on your gains will be paid through quarterly estimated tax payments.
We will reconcile your actual tax at year-end.
tax return.

Realized gain of ${details['realized_gain']:,.2f} was recognized on this withdrawal.

If you have any questions, please don't hesitate to contact us.

Best regards,
Tovito Trader Management

---
This is an automated confirmation from Tovito Trader.
Processed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    return send_email(
        to_email=investor_email,
        subject=subject,
        message=message
    )


def send_admin_notification(request_id, investor_name, details, admin_email):
    """Send admin notification"""
    
    if not EMAIL_AVAILABLE:
        return False
    
    subject = f"Withdrawal Processed - {investor_name} - ${details['requested_amount']:,.2f}"
    
    message = f"""Withdrawal Request #{request_id} has been processed.

Investor: {investor_name}

DETAILS:
Withdrawal Amount:  ${details['requested_amount']:,.2f}
Realized Gain:      ${details['realized_gain']:,.2f}
Tax Withheld:       ${details['tax_withheld']:,.2f}
Net Proceeds:       ${details['net_proceeds']:,.2f}

Shares Sold:        {details['shares_to_sell']:,.4f}

Investor confirmation email has been sent.

---
Tovito Trader Automated System
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    return send_email(
        to_email=admin_email,
        subject=subject,
        message=message
    )


def process_withdrawal():
    """Process withdrawal with approval workflow"""
    
    parser = argparse.ArgumentParser(description='Process withdrawal requests')
    parser.add_argument('--request-id', type=int, help='Specific request ID to process')
    
    args = parser.parse_args()
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get current NAV
        cursor.execute("""
            SELECT nav_per_share, total_portfolio_value, total_shares, date
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        nav_data = cursor.fetchone()
        
        if not nav_data:
            print("❌ No NAV data found. Run daily update first.")
            return False
        
        nav_per_share, portfolio_value, total_shares, nav_date = nav_data
        
        print("=" * 70)
        print("WITHDRAWAL PROCESSING - MANUAL APPROVAL")
        print("=" * 70)
        print()
        print(f"Current NAV: ${nav_per_share:.4f} (as of {nav_date})")
        print(f"Portfolio Value: ${portfolio_value:,.2f}")
        print()
        
        # Get pending requests
        requests = get_pending_requests(cursor)
        
        if not requests:
            print("No pending withdrawal requests.")
            print()
            print("💡 To submit a request:")
            print("   python scripts/submit_withdrawal_request.py")
            return True
        
        # If specific request ID provided, filter to that one
        if args.request_id:
            requests = [r for r in requests if r[0] == args.request_id]
            if not requests:
                print(f"❌ Request #{args.request_id} not found or not pending")
                return False
        
        # Show pending requests
        print(f"Pending Requests: {len(requests)}")
        print()
        
        for idx, request in enumerate(requests, 1):
            req_id, inv_id, name, email, req_date, amount, method, notes, shares, value, net_inv = request
            
            print(f"Request #{req_id}")
            print(f"  Investor: {name} ({inv_id})")
            print(f"  Amount: ${amount:,.2f}")
            print(f"  Date: {req_date}")
            print(f"  Method: {method}")
            if notes:
                print(f"  Notes: {notes}")
            print(f"  Current Value: ${value:,.2f}")
            print(f"  Current Shares: {shares:,.4f}")
            print()
        
        # Select request to process
        if len(requests) == 1:
            selected_idx = 0
            print(f"Processing Request #{requests[0][0]}...")
        else:
            print("Select request to process:")
            for idx, request in enumerate(requests, 1):
                print(f"  {idx}. Request #{request[0]} - {request[2]} - ${request[5]:,.2f}")
            print()
            
            while True:
                try:
                    selection = input("Select request (number) or 'q' to quit: ").strip()
                    if selection.lower() == 'q':
                        print("Cancelled.")
                        return False
                    idx = int(selection) - 1
                    if 0 <= idx < len(requests):
                        selected_idx = idx
                        break
                    print("Invalid selection.")
                except ValueError:
                    print("Please enter a number.")
        
        # Get selected request
        req_id, inv_id, name, email, req_date, amount, method, notes, shares, value, net_inv = requests[selected_idx]
        
        print()
        print("=" * 70)
        print(f"PROCESSING REQUEST #{req_id}")
        print("=" * 70)
        print(f"Investor: {name}")
        print(f"Requested Amount: ${amount:,.2f}")
        print()
        
        # Calculate withdrawal details
        tax_rate = float(os.getenv('TAX_RATE', '0.37'))
        details = calculate_withdrawal_details(
            amount, value, shares, net_inv, nav_per_share, tax_rate
        )
        
        if not details:
            print("❌ Cannot calculate withdrawal (zero current value)")
            return False
        
        # Show calculation
        print("WITHDRAWAL CALCULATION:")
        print(f"  Current Value:      ${value:,.2f}")
        print(f"  Net Investment:     ${net_inv:,.2f}")
        unrealized_gain = value - net_inv
        print(f"  Unrealized Gain:    ${unrealized_gain:,.2f}")
        print()
        print(f"  Withdrawal Amount:  ${details['requested_amount']:,.2f}")
        print(f"  Proportion:         {details['proportion']:.2%}")
        print(f"  Shares to Sell:     {details['shares_to_sell']:,.4f}")
        print()
        principal_portion = details['requested_amount'] - details['realized_gain']
        print("  BREAKDOWN:")
        print(f"    Principal portion:  ${principal_portion:,.2f}")
        print(f"    Gain portion:       ${details['realized_gain']:,.2f}")
        print()
        print("  TAX TREATMENT:")
        print(f"    NO tax withheld at withdrawal")
        print(f"    Tax handled via quarterly payments")
        print(f"    Investor receives:  ${details['requested_amount']:,.2f} (full amount)")
        print()
        print("NEW POSITION:")
        print(f"  Shares:             {details['new_shares']:,.4f}")
        print(f"  Value:              ${details['new_value']:,.2f}")
        print()
        
        # Approval decision
        print("=" * 70)
        decision = input("Approve and process this withdrawal? (yes/no): ").strip().lower()
        
        if decision not in ['yes', 'y']:
            # Ask for rejection reason
            reason = input("Rejection reason (optional): ").strip() or "Declined by admin"
            
            cursor.execute("""
                UPDATE withdrawal_requests
                SET status = 'Rejected',
                    rejection_reason = ?,
                    updated_at = ?
                WHERE id = ?
            """, (reason, datetime.now().isoformat(), req_id))
            
            conn.commit()
            
            print()
            print(f"✅ Request #{req_id} rejected: {reason}")
            print()
            
            conn.close()
            return True
        
        print()
        print("Processing withdrawal...")
        
        # Update investor record
        cursor.execute("""
            UPDATE investors
            SET current_shares = ?,
                net_investment = ?,
                updated_at = ?
            WHERE investor_id = ?
        """, (
            details['new_shares'],
            details['new_net_investment'],
            datetime.now().isoformat(),
            inv_id
        ))
        
        # Record transaction
        cursor.execute("""
            INSERT INTO transactions
            (date, investor_id, transaction_type, amount, share_price, shares_transacted, notes)
            VALUES (?, ?, 'Withdrawal', ?, ?, ?, ?)
        """, (
            datetime.now().date().isoformat(),
            inv_id,
            -details['requested_amount'],
            nav_per_share,
            -details['shares_to_sell'],
            f"Withdrawal with ${details['tax_withheld']:.2f} tax withheld"
        ))
        
        # Update withdrawal request
        cursor.execute("""
            UPDATE withdrawal_requests
            SET status = 'Processed',
                processed_date = ?,
                actual_amount = ?,
                shares_sold = ?,
                realized_gain = ?,
                tax_withheld = ?,
                net_proceeds = ?,
                approved_by = 'Admin',
                approved_date = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            datetime.now().date().isoformat(),
            details['requested_amount'],
            details['shares_to_sell'],
            details['realized_gain'],
            details['tax_withheld'],
            details['net_proceeds'],
            datetime.now().date().isoformat(),
            datetime.now().isoformat(),
            req_id
        ))
        
        # Update daily NAV (reduce portfolio value and shares)
        new_portfolio_value = portfolio_value - details['requested_amount']
        new_total_shares = total_shares - details['shares_to_sell']
        
        cursor.execute("""
            UPDATE daily_nav
            SET total_portfolio_value = ?,
                total_shares = ?
            WHERE date = ?
        """, (new_portfolio_value, new_total_shares, nav_date))
        
        conn.commit()
        
        print("   ✅ Database updated")
        
        # Send emails
        admin_email = os.getenv('ADMIN_EMAIL', 'dlang32@gmail.com')
        
        if EMAIL_AVAILABLE:
            print("   📧 Sending investor confirmation...")
            if send_withdrawal_confirmation(name, email, details, admin_email):
                print("   ✅ Investor email sent")
            else:
                print("   ⚠️  Investor email failed")
            
            print("   📧 Sending admin notification...")
            if send_admin_notification(req_id, name, details, admin_email):
                print("   ✅ Admin email sent")
            else:
                print("   ⚠️  Admin email failed")
        
        print()
        print("=" * 70)
        print("✅ WITHDRAWAL PROCESSED SUCCESSFULLY")
        print("=" * 70)
        print(f"Request #{req_id} completed")
        print(f"Net proceeds: ${details['net_proceeds']:,.2f}")
        print(f"Tax withheld: ${details['tax_withheld']:,.2f}")
        print()
        
        conn.close()
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
        success = process_withdrawal()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
