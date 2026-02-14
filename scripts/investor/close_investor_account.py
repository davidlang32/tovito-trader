"""
Close Investor Account

Complete account closure with final tax settlement and full liquidation.

Usage:
    python scripts/close_investor_account.py --investor 20260101-01A
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.automation.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def close_account():
    """Close investor account with final tax settlement"""
    
    parser = argparse.ArgumentParser(description='Close investor account')
    parser.add_argument('--investor', required=True, help='Investor ID')
    
    args = parser.parse_args()
    
    db_path = get_database_path()
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        TAX_RATE = 0.37
        
        # Get current NAV
        cursor.execute("""
            SELECT nav_per_share, date, total_portfolio_value, total_shares
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        nav_data = cursor.fetchone()
        
        if not nav_data:
            print("❌ No NAV data")
            return False
        
        nav_per_share, nav_date, portfolio_value, total_shares = nav_data
        
        # Get investor
        cursor.execute("""
            SELECT investor_id, name, email, current_shares, net_investment, status
            FROM investors
            WHERE investor_id = ?
        """, (args.investor,))
        
        investor = cursor.fetchone()
        if not investor:
            print(f"❌ Investor {args.investor} not found")
            return False
        
        inv_id, name, email, shares, net_inv, status = investor
        
        if status == 'Inactive':
            print(f"⚠️  Investor {name} is already inactive")
            return True
        
        # Calculate final position
        gross_value = shares * nav_per_share
        unrealized_gain = max(0, gross_value - net_inv)
        tax_liability = unrealized_gain * TAX_RATE
        after_tax_value = gross_value - tax_liability
        
        print("=" * 80)
        print(f"CLOSE INVESTOR ACCOUNT - {name}")
        print("=" * 80)
        print(f"Investor ID: {inv_id}")
        print(f"NAV Date: {nav_date}")
        print(f"NAV: ${nav_per_share:.4f}")
        print()
        print("CURRENT POSITION:")
        print(f"  Shares:                {shares:,.4f}")
        print(f"  Gross Value:           ${gross_value:,.2f}")
        print(f"  Net Investment:        ${net_inv:,.2f}")
        print(f"  Unrealized Gain:       ${unrealized_gain:,.2f}")
        print()
        print("FINAL TAX SETTLEMENT:")
        print(f"  Tax Liability (37%):   ${tax_liability:,.2f}")
        print(f"  After-Tax Value:       ${after_tax_value:,.2f}")
        print()
        print("CLOSURE PLAN:")
        print(f"  1. Sell all {shares:,.4f} shares")
        print(f"  2. Withhold ${tax_liability:,.2f} for final tax")
        print(f"  3. Disburse ${after_tax_value:,.2f} to investor")
        print(f"  4. Mark account inactive")
        print()
        
        confirm = input(f"Close account for {name}? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            print("Cancelled.")
            return False
        
        print()
        print("Processing account closure...")
        
        # 1. Final withdrawal (full after-tax value)
        cursor.execute("""
            INSERT INTO transactions
            (date, investor_id, transaction_type, amount, share_price, shares_transacted, notes)
            VALUES (?, ?, 'Withdrawal', ?, ?, ?, ?)
        """, (
            datetime.now().date().isoformat(),
            inv_id,
            -after_tax_value,
            nav_per_share,
            -shares,
            "Account closure - final withdrawal (after-tax)"
        ))
        
        # 2. Final tax payment
        if tax_liability > 0:
            cursor.execute("""
                INSERT INTO transactions
                (date, investor_id, transaction_type, amount, share_price, shares_transacted, notes)
                VALUES (?, ?, 'Tax Payment', ?, ?, ?, ?)
            """, (
                datetime.now().date().isoformat(),
                inv_id,
                -tax_liability,
                nav_per_share,
                0,  # No shares - tax already accounted for
                "Account closure - final tax settlement"
            ))
        
        # 3. Update investor to inactive
        cursor.execute("""
            UPDATE investors
            SET status = 'Inactive',
                current_shares = 0,
                updated_at = ?
            WHERE investor_id = ?
        """, (datetime.now().isoformat(), inv_id))
        
        # 4. Update daily NAV
        new_portfolio_value = portfolio_value - gross_value
        new_total_shares = total_shares - shares
        
        cursor.execute("""
            UPDATE daily_nav
            SET total_portfolio_value = ?,
                total_shares = ?
            WHERE date = ?
        """, (new_portfolio_value, new_total_shares, nav_date))
        
        conn.commit()
        
        print("   ✅ Database updated")
        
        # Send email
        admin_email = os.getenv('ADMIN_EMAIL', 'dlang32@gmail.com')
        
        if EMAIL_AVAILABLE:
            # Investor confirmation
            subject = "Account Closure Confirmation - Tovito Trader"
            message = f"""Dear {name},

Your account closure has been processed.

FINAL ACCOUNT SUMMARY
=====================
Gross Value:           ${gross_value:,.2f}
Net Investment:        ${net_inv:,.2f}
Total Gain:            ${unrealized_gain:,.2f}

FINAL TAX SETTLEMENT
====================
Tax Liability (37%):   ${tax_liability:,.2f}

FINAL DISBURSEMENT
==================
After-Tax Value:       ${after_tax_value:,.2f}

This amount has been processed for payment to you.

The tax liability has been paid to the IRS on your behalf.
Your account is now closed.

INVESTMENT SUMMARY
==================
Total Invested:        ${net_inv:,.2f}
Total Returned:        ${after_tax_value:,.2f}
Net Gain:              ${unrealized_gain - tax_liability:,.2f}
Return:                {((after_tax_value / net_inv - 1) * 100):.2f}%

Thank you for investing with Tovito Trader!

Best regards,
Tovito Trader Management
"""
            
            send_email(email, subject, message)
            print("   ✅ Investor email sent")
            
            # Admin notification
            admin_subject = f"Account Closed - {name} - ${after_tax_value:,.2f} Disbursed"
            admin_message = f"""Account closure completed for {name}.

Investor ID: {inv_id}

Final Position:
  Gross Value: ${gross_value:,.2f}
  Tax Withheld: ${tax_liability:,.2f}
  Disbursed: ${after_tax_value:,.2f}

Return: {((after_tax_value / net_inv - 1) * 100):.2f}%

Account marked inactive.
Investor confirmation sent.
"""
            
            send_email(admin_email, admin_subject, admin_message)
            print("   ✅ Admin email sent")
        
        print()
        print("=" * 80)
        print("✅ ACCOUNT CLOSURE COMPLETE")
        print("=" * 80)
        print(f"Investor: {name}")
        print(f"Disbursed: ${after_tax_value:,.2f}")
        print(f"Tax Paid: ${tax_liability:,.2f}")
        print(f"Status: Inactive")
        print()
        print(f"Total return: {((after_tax_value / net_inv - 1) * 100):.2f}%")
        print()
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = close_account()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(1)
