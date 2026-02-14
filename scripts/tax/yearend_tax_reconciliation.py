"""
Year-End Tax Reconciliation

Calculate actual tax liability for the year and reconcile with quarterly payments.
Collect additional tax or refund overpayments.

Usage:
    python scripts/yearend_tax_reconciliation.py --year 2026
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


def yearend_reconciliation():
    """Year-end tax reconciliation"""
    
    parser = argparse.ArgumentParser(description='Year-end tax reconciliation')
    parser.add_argument('--year', type=int, required=True, help='Tax year')
    
    args = parser.parse_args()
    
    db_path = get_database_path()
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        TAX_RATE = 0.37
        
        # Get December 31 NAV
        cursor.execute("""
            SELECT nav_per_share, date
            FROM daily_nav
            WHERE date LIKE ?
            ORDER BY date DESC
            LIMIT 1
        """, (f"{args.year}-12-%",))
        nav_data = cursor.fetchone()
        
        if not nav_data:
            print(f"❌ No December {args.year} NAV data found")
            return False
        
        nav_per_share, nav_date = nav_data
        
        print("=" * 80)
        print(f"YEAR-END TAX RECONCILIATION - {args.year}")
        print("=" * 80)
        print(f"NAV Date: {nav_date}")
        print(f"NAV: ${nav_per_share:.4f}")
        print()
        
        # Get active investors
        cursor.execute("""
            SELECT investor_id, name, email, current_shares, net_investment
            FROM investors
            WHERE status = 'Active'
            ORDER BY name
        """)
        investors = cursor.fetchall()
        
        if not investors:
            print("No active investors.")
            return True
        
        # Calculate for each investor
        reconciliations = []
        total_tax_owed = 0
        total_already_paid = 0
        total_adjustment = 0
        
        for inv_id, name, email, shares, net_inv in investors:
            gross_value = shares * nav_per_share
            unrealized_gain = max(0, gross_value - net_inv)
            
            # Calculate actual tax owed
            actual_tax = unrealized_gain * TAX_RATE
            
            # Get quarterly payments made during year
            cursor.execute("""
                SELECT SUM(ABS(amount))
                FROM transactions
                WHERE investor_id = ?
                AND transaction_type = 'Tax Payment'
                AND date LIKE ?
            """, (inv_id, f"{args.year}-%"))
            
            paid_result = cursor.fetchone()
            quarterly_paid = paid_result[0] if paid_result and paid_result[0] else 0
            
            # Calculate adjustment needed
            adjustment = actual_tax - quarterly_paid
            
            reconciliations.append({
                'id': inv_id,
                'name': name,
                'email': email,
                'shares': shares,
                'net_investment': net_inv,
                'gross_value': gross_value,
                'unrealized_gain': unrealized_gain,
                'actual_tax': actual_tax,
                'quarterly_paid': quarterly_paid,
                'adjustment': adjustment
            })
            
            total_tax_owed += actual_tax
            total_already_paid += quarterly_paid
            total_adjustment += adjustment
        
        # Show reconciliation
        print("YEAR-END RECONCILIATION:")
        print()
        
        for inv in reconciliations:
            print(f"{inv['name']}")
            print(f"  Gross Value:       ${inv['gross_value']:,.2f}")
            print(f"  Unrealized Gain:   ${inv['unrealized_gain']:,.2f}")
            print(f"  Actual Tax (37%):  ${inv['actual_tax']:,.2f}")
            print(f"  Quarterly Paid:    ${inv['quarterly_paid']:,.2f}")
            
            if inv['adjustment'] > 0:
                print(f"  ADDITIONAL DUE:    ${inv['adjustment']:,.2f} ⚠️")
            elif inv['adjustment'] < 0:
                print(f"  REFUND DUE:        ${abs(inv['adjustment']):,.2f} ✓")
            else:
                print(f"  Status:            Fully paid ✓")
            print()
        
        print("=" * 80)
        print(f"TOTAL TAX OWED:      ${total_tax_owed:,.2f}")
        print(f"QUARTERLY PAID:      ${total_already_paid:,.2f}")
        print(f"NET ADJUSTMENT:      ${total_adjustment:,.2f}")
        print("=" * 80)
        print()
        
        if total_adjustment == 0:
            print("✅ All taxes fully reconciled!")
            return True
        
        confirm = input(f"Process year-end adjustments? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            print("Cancelled.")
            return False
        
        print()
        print("Processing adjustments...")
        
        # Process each adjustment
        for inv in reconciliations:
            if inv['adjustment'] == 0:
                print(f"  • {inv['name']}: No adjustment needed")
                continue
            
            if inv['adjustment'] > 0:
                # Collect additional tax
                shares_to_sell = inv['adjustment'] / nav_per_share
                new_shares = inv['shares'] - shares_to_sell
                
                cursor.execute("""
                    UPDATE investors
                    SET current_shares = ?,
                        updated_at = ?
                    WHERE investor_id = ?
                """, (new_shares, datetime.now().isoformat(), inv['id']))
                
                cursor.execute("""
                    INSERT INTO transactions
                    (date, investor_id, transaction_type, amount, share_price, shares_transacted, notes)
                    VALUES (?, ?, 'Tax Payment', ?, ?, ?, ?)
                """, (
                    datetime.now().date().isoformat(),
                    inv['id'],
                    -inv['adjustment'],
                    nav_per_share,
                    -shares_to_sell,
                    f"Year-end {args.year} tax reconciliation - additional collection"
                ))
                
                print(f"  ✅ {inv['name']}: Collected ${inv['adjustment']:,.2f}")
            
            else:
                # Refund overpayment
                shares_to_add = abs(inv['adjustment']) / nav_per_share
                new_shares = inv['shares'] + shares_to_add
                
                cursor.execute("""
                    UPDATE investors
                    SET current_shares = ?,
                        updated_at = ?
                    WHERE investor_id = ?
                """, (new_shares, datetime.now().isoformat(), inv['id']))
                
                cursor.execute("""
                    INSERT INTO transactions
                    (date, investor_id, transaction_type, amount, share_price, shares_transacted, notes)
                    VALUES (?, ?, 'Tax Refund', ?, ?, ?, ?)
                """, (
                    datetime.now().date().isoformat(),
                    inv['id'],
                    abs(inv['adjustment']),
                    nav_per_share,
                    shares_to_add,
                    f"Year-end {args.year} tax reconciliation - refund overpayment"
                ))
                
                print(f"  ✅ {inv['name']}: Refunded ${abs(inv['adjustment']):,.2f}")
        
        # Update daily NAV
        cursor.execute("""
            SELECT total_portfolio_value, total_shares
            FROM daily_nav
            WHERE date = ?
        """, (nav_date,))
        portfolio_data = cursor.fetchone()
        
        if portfolio_data:
            current_portfolio, current_total_shares = portfolio_data
            
            new_portfolio = current_portfolio - total_adjustment
            new_total_shares = current_total_shares - (total_adjustment / nav_per_share)
            
            cursor.execute("""
                UPDATE daily_nav
                SET total_portfolio_value = ?,
                    total_shares = ?
                WHERE date = ?
            """, (new_portfolio, new_total_shares, nav_date))
        
        conn.commit()
        
        print()
        print("=" * 80)
        print("✅ YEAR-END TAX RECONCILIATION COMPLETE")
        print("=" * 80)
        print(f"Net adjustment: ${total_adjustment:,.2f}")
        print(f"Total tax for {args.year}: ${total_tax_owed:,.2f}")
        print()
        
        # Send emails
        admin_email = os.getenv('ADMIN_EMAIL', 'dlang32@gmail.com')
        
        if EMAIL_AVAILABLE:
            for inv in reconciliations:
                subject = f"Year-End Tax Reconciliation - {args.year}"
                
                if inv['adjustment'] > 0:
                    message = f"""Dear {inv['name']},

Year-end tax reconciliation for {args.year} has been completed.

RECONCILIATION SUMMARY
======================
Actual Tax Owed ({args.year}):  ${inv['actual_tax']:,.2f}
Quarterly Payments:     ${inv['quarterly_paid']:,.2f}
Additional Collected:   ${inv['adjustment']:,.2f}

This additional amount was withdrawn from your account to cover 
your full {args.year} tax liability.

Final tax paid to IRS: ${inv['actual_tax']:,.2f}

Questions? Contact us anytime.

Best regards,
Tovito Trader Management
"""
                elif inv['adjustment'] < 0:
                    message = f"""Dear {inv['name']},

Year-end tax reconciliation for {args.year} has been completed.

RECONCILIATION SUMMARY
======================
Actual Tax Owed ({args.year}):  ${inv['actual_tax']:,.2f}
Quarterly Payments:     ${inv['quarterly_paid']:,.2f}
Refund (Overpayment):   ${abs(inv['adjustment']):,.2f}

You overpaid during quarterly payments. This amount has been 
credited back to your account.

Final tax paid to IRS: ${inv['actual_tax']:,.2f}

Questions? Contact us anytime.

Best regards,
Tovito Trader Management
"""
                else:
                    message = f"""Dear {inv['name']},

Year-end tax reconciliation for {args.year} has been completed.

RECONCILIATION SUMMARY
======================
Actual Tax Owed ({args.year}):  ${inv['actual_tax']:,.2f}
Quarterly Payments:     ${inv['quarterly_paid']:,.2f}
Status:                 Fully reconciled ✓

Your quarterly payments exactly matched your actual tax liability.
No adjustment needed.

Questions? Contact us anytime.

Best regards,
Tovito Trader Management
"""
                
                send_email(inv['email'], subject, message)
            
            # Admin summary
            admin_subject = f"Year-End Tax Reconciliation Complete - {args.year}"
            admin_message = f"""Year-end tax reconciliation for {args.year} completed.

Total Tax Owed: ${total_tax_owed:,.2f}
Quarterly Paid: ${total_already_paid:,.2f}
Net Adjustment: ${total_adjustment:,.2f}

Investor notifications sent.
"""
            send_email(admin_email, admin_subject, admin_message)
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = yearend_reconciliation()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(1)
