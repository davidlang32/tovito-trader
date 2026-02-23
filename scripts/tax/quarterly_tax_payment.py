"""
Quarterly Estimated Tax Payment

Calculates and processes quarterly estimated tax payments for all investors.
Run 4 times per year (Q1, Q2, Q3, Q4).

Usage:
    python scripts/quarterly_tax_payment.py --quarter 1 --year 2026
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


def calculate_quarterly_tax():
    """Calculate and process quarterly tax payments"""
    
    parser = argparse.ArgumentParser(description='Process quarterly tax payments')
    parser.add_argument('--quarter', type=int, required=True, help='Quarter (1-4)')
    parser.add_argument('--year', type=int, required=True, help='Year')
    
    args = parser.parse_args()
    
    if args.quarter not in [1, 2, 3, 4]:
        print("❌ Quarter must be 1-4")
        return False
    
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
            SELECT nav_per_share, date
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        nav_data = cursor.fetchone()
        if not nav_data:
            print("❌ No NAV data")
            return False
        
        nav_per_share, nav_date = nav_data
        
        quarter_name = f"Q{args.quarter} {args.year}"
        
        print("=" * 80)
        print(f"QUARTERLY ESTIMATED TAX PAYMENT - {quarter_name}")
        print("=" * 80)
        print(f"NAV Date: {nav_date}")
        print(f"NAV: ${nav_per_share:.4f}")
        print()
        
        # Get active investors
        cursor.execute("""
            SELECT investor_id, name, email, current_shares, net_investment
            FROM investors
            WHERE status = 'Active' AND current_shares > 0
            ORDER BY name
        """)
        investors = cursor.fetchall()
        
        if not investors:
            print("No active investors found.")
            return True
        
        # Calculate tax for each investor
        investor_taxes = []
        total_tax = 0
        
        for inv_id, name, email, shares, net_inv in investors:
            gross_value = shares * nav_per_share
            unrealized_gain = max(0, gross_value - net_inv)
            
            # Quarterly tax = 25% of annual tax liability
            annual_tax = unrealized_gain * TAX_RATE
            quarterly_tax = annual_tax * 0.25
            
            investor_taxes.append({
                'id': inv_id,
                'name': name,
                'email': email,
                'shares': shares,
                'net_investment': net_inv,
                'gross_value': gross_value,
                'unrealized_gain': unrealized_gain,
                'annual_tax': annual_tax,
                'quarterly_tax': quarterly_tax
            })
            
            total_tax += quarterly_tax
        
        # Show summary
        print("INVESTOR TAX CALCULATIONS:")
        print()
        for inv in investor_taxes:
            print(f"{inv['name']}")
            print(f"  Gross Value:       ${inv['gross_value']:,.2f}")
            print(f"  Unrealized Gain:   ${inv['unrealized_gain']:,.2f}")
            print(f"  Annual Tax (37%):  ${inv['annual_tax']:,.2f}")
            print(f"  Quarterly Payment: ${inv['quarterly_tax']:,.2f}")
            print()
        
        print("=" * 80)
        print(f"TOTAL QUARTERLY TAX: ${total_tax:,.2f}")
        print("=" * 80)
        print()
        
        confirm = input(f"Process {quarter_name} tax payments? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            print("Cancelled.")
            return False
        
        print()
        print("Processing tax payments...")
        
        # Process each investor
        for inv in investor_taxes:
            if inv['quarterly_tax'] <= 0:
                print(f"  • {inv['name']}: $0 (no gain)")
                continue
            
            # Calculate shares to sell (4 decimal places)
            shares_to_sell = round(inv['quarterly_tax'] / nav_per_share, 4)
            new_shares = round(inv['shares'] - shares_to_sell, 4)
            
            # Update investor
            cursor.execute("""
                UPDATE investors
                SET current_shares = ?,
                    updated_at = ?
                WHERE investor_id = ?
            """, (new_shares, datetime.now().isoformat(), inv['id']))
            
            # Record transaction
            cursor.execute("""
                INSERT INTO transactions
                (date, investor_id, transaction_type, amount, share_price, shares_transacted, notes)
                VALUES (?, ?, 'Tax Payment', ?, ?, ?, ?)
            """, (
                datetime.now().date().isoformat(),
                inv['id'],
                -inv['quarterly_tax'],
                nav_per_share,
                -shares_to_sell,
                f"{quarter_name} estimated tax payment"
            ))
            
            print(f"  ✅ {inv['name']}: ${inv['quarterly_tax']:,.2f} ({shares_to_sell:.4f} shares)")
        
        # Update daily NAV
        cursor.execute("""
            SELECT total_portfolio_value, total_shares
            FROM daily_nav
            WHERE date = ?
        """, (nav_date,))
        portfolio_data = cursor.fetchone()
        
        if portfolio_data:
            current_portfolio, current_total_shares = portfolio_data
            
            new_portfolio = round(current_portfolio - total_tax, 2)
            new_total_shares = round(current_total_shares - (total_tax / nav_per_share), 4)
            
            cursor.execute("""
                UPDATE daily_nav
                SET total_portfolio_value = ?,
                    total_shares = ?
                WHERE date = ?
            """, (new_portfolio, new_total_shares, nav_date))
        
        conn.commit()
        
        print()
        print("=" * 80)
        print("✅ QUARTERLY TAX PAYMENTS PROCESSED")
        print("=" * 80)
        print(f"Total tax collected: ${total_tax:,.2f}")
        print(f"Quarter: {quarter_name}")
        print()
        print("Next steps:")
        print("  • Pay ${:,.2f} to IRS for quarterly estimated taxes".format(total_tax))
        print(f"  • Record payment date and confirmation")
        print()
        
        # Send emails
        admin_email = os.getenv('ADMIN_EMAIL', 'dlang32@gmail.com')
        
        if EMAIL_AVAILABLE:
            # Send to each investor
            for inv in investor_taxes:
                if inv['quarterly_tax'] <= 0:
                    continue
                
                subject = f"Quarterly Tax Payment - {quarter_name}"
                message = f"""Dear {inv['name']},

Your {quarter_name} estimated tax payment has been processed.

TAX PAYMENT SUMMARY
===================
Gross Value:         ${inv['gross_value']:,.2f}
Unrealized Gain:     ${inv['unrealized_gain']:,.2f}
Annual Tax (37%):    ${inv['annual_tax']:,.2f}

Quarterly Payment:   ${inv['quarterly_tax']:,.2f}
Shares Sold:         {inv['quarterly_tax'] / nav_per_share:,.4f}

This payment covers your estimated tax liability for {quarter_name}.
We will reconcile your actual tax at year-end.

UPDATED POSITION
================
Remaining Shares:    {inv['shares'] - (inv['quarterly_tax'] / nav_per_share):,.4f}
Current Value:       ${(inv['shares'] - (inv['quarterly_tax'] / nav_per_share)) * nav_per_share:,.2f}

Questions? Contact us anytime.

Best regards,
Tovito Trader Management
"""
                
                send_email(inv['email'], subject, message)
            
            # Admin summary
            admin_subject = f"Quarterly Tax Processed - {quarter_name} - ${total_tax:,.2f}"
            admin_message = f"""{quarter_name} Estimated Tax Payments Processed

Total Tax Collected: ${total_tax:,.2f}

Investor Breakdown:
"""
            for inv in investor_taxes:
                admin_message += f"\n  • {inv['name']}: ${inv['quarterly_tax']:,.2f}"
            
            admin_message += f"""

PAY TO IRS:
Amount: ${total_tax:,.2f}
Due: Q{args.quarter} estimated tax deadline

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
        success = calculate_quarterly_tax()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(1)
