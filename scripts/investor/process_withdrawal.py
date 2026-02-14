"""
Process Withdrawal with Historical Date Support

Allows backdating withdrawals to use historical NAV.

Usage:
    python scripts/process_withdrawal_historical.py
    
Features:
- Enter transaction date (defaults to today)
- Uses NAV from transaction date for share calculation
- Calculates tax on realized gains
- Records tax event
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
import os
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  Warning: python-dotenv not installed")

# Import email functionality
try:
    from src.automation.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Get tax rate from environment
TAX_RATE = float(os.getenv('TAX_RATE', '0.37'))


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def get_nav_for_date(conn, transaction_date):
    """Get NAV per share for a specific date"""
    cursor = conn.cursor()
    
    # Try exact date
    cursor.execute("""
        SELECT nav_per_share, total_portfolio_value, total_shares
        FROM nav_history
        WHERE DATE(date) = DATE(?)
        ORDER BY date DESC
        LIMIT 1
    """, (transaction_date,))
    
    result = cursor.fetchone()
    
    if result:
        return result
    
    # Try most recent before date
    cursor.execute("""
        SELECT nav_per_share, total_portfolio_value, total_shares
        FROM nav_history
        WHERE DATE(date) <= DATE(?)
        ORDER BY date DESC
        LIMIT 1
    """, (transaction_date,))
    
    result = cursor.fetchone()
    
    if result:
        print(f"⚠️  No NAV found for {transaction_date}, using most recent")
        return result
    
    return None


def get_current_nav(conn):
    """Get most recent NAV"""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT date, nav_per_share, total_portfolio_value, total_shares
        FROM nav_history
        ORDER BY date DESC
        LIMIT 1
    """)
    
    return cursor.fetchone()


def get_active_investors(conn):
    """Get all active investors"""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT investor_id, name, current_shares, net_investment, email
        FROM investors
        WHERE status = 'Active'
        ORDER BY investor_id
    """)
    
    return cursor.fetchall()


def calculate_tax_on_withdrawal(withdrawal_amount, current_value, total_unrealized_gain):
    """Calculate tax on realized gains from withdrawal"""
    
    # Proportion of position being withdrawn
    proportion_withdrawn = Decimal(str(withdrawal_amount)) / Decimal(str(current_value))
    
    # Realized gain
    realized_gain = Decimal(str(total_unrealized_gain)) * proportion_withdrawn
    
    # Tax on realized gain
    tax_due = realized_gain * Decimal(str(TAX_RATE))
    
    # Net proceeds after tax
    net_proceeds = Decimal(str(withdrawal_amount)) - tax_due
    
    return {
        'proportion': float(proportion_withdrawn),
        'realized_gain': float(realized_gain),
        'tax_due': float(tax_due),
        'net_proceeds': float(net_proceeds)
    }


def process_withdrawal(conn, investor_id, investor_name, investor_email,
                      withdrawal_amount, transaction_date,
                      nav_per_share, current_shares, net_investment):
    """Process the withdrawal transaction"""
    
    current_value = float(current_shares) * nav_per_share
    total_unrealized_gain = current_value - net_investment
    
    # Calculate shares to sell
    shares_to_sell = Decimal(str(withdrawal_amount)) / Decimal(str(nav_per_share))
    
    # Check sufficient shares
    if shares_to_sell > Decimal(str(current_shares)):
        return False, "Insufficient shares"
    
    # Calculate tax
    tax_calc = calculate_tax_on_withdrawal(withdrawal_amount, current_value, total_unrealized_gain)
    
    new_shares = Decimal(str(current_shares)) - shares_to_sell
    
    # Reduce net_investment proportionally
    proportion_withdrawn = tax_calc['proportion']
    net_investment_reduction = Decimal(str(net_investment)) * Decimal(str(proportion_withdrawn))
    new_net_investment = Decimal(str(net_investment)) - net_investment_reduction
    
    cursor = conn.cursor()
    
    try:
        # Update investor
        cursor.execute("""
            UPDATE investors
            SET current_shares = ?,
                net_investment = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE investor_id = ?
        """, (float(new_shares), float(new_net_investment), investor_id))
        
        # Record transaction
        cursor.execute("""
            INSERT INTO transactions (
                investor_id, transaction_date, transaction_type,
                amount, share_price, shares_transacted, notes
            ) VALUES (?, ?, 'Withdrawal', ?, ?, ?, ?)
        """, (
            investor_id,
            transaction_date,
            float(withdrawal_amount),
            float(nav_per_share),
            -float(shares_to_sell),
            f"Withdrawal processed on {datetime.now().strftime('%Y-%m-%d')}, Tax: ${tax_calc['tax_due']:.2f}"
        ))
        
        # Record tax event
        cursor.execute("""
            INSERT INTO tax_events (
                investor_id, event_date, event_type,
                withdrawal_amount, realized_gain, tax_due, notes
            ) VALUES (?, ?, 'Withdrawal', ?, ?, ?, ?)
        """, (
            investor_id,
            transaction_date,
            float(withdrawal_amount),
            tax_calc['realized_gain'],
            tax_calc['tax_due'],
            f"Tax on withdrawal: {tax_calc['proportion']*100:.2f}% of position"
        ))
        
        # Update NAV history
        cursor.execute("""
            SELECT total_portfolio_value, total_shares
            FROM nav_history
            ORDER BY date DESC
            LIMIT 1
        """)
        
        latest_nav = cursor.fetchone()
        if latest_nav:
            new_portfolio_value = latest_nav[0] - withdrawal_amount
            new_total_shares = latest_nav[1] - float(shares_to_sell)
            new_nav_per_share = new_portfolio_value / new_total_shares if new_total_shares > 0 else 0
            
            cursor.execute("""
                UPDATE nav_history
                SET total_portfolio_value = ?,
                    total_shares = ?,
                    nav_per_share = ?
                WHERE date = (SELECT MAX(date) FROM nav_history)
            """, (new_portfolio_value, new_total_shares, new_nav_per_share))
        
        conn.commit()
        
        # Send email confirmation
        if EMAIL_AVAILABLE and investor_email:
            try:
                # Get cost basis portion
                cost_basis_withdrawn = float(net_investment_reduction)
                gain_portion = tax_calc['realized_gain']
                
                subject = f"Withdrawal Processed - ${tax_calc['net_proceeds']:,.2f} Net Proceeds"
                
                message = f"""Hi {investor_name},

Your withdrawal has been successfully processed!

WITHDRAWAL DETAILS:
{'='*60}
Transaction Date:       {transaction_date}
Gross Withdrawal:       ${withdrawal_amount:,.2f}
Shares Sold:            {shares_to_sell:,.4f}
Share Price (NAV):      ${nav_per_share:.4f}

TAX CALCULATION:
{'='*60}
Proportion Withdrawn:   {tax_calc['proportion']*100:.2f}%
Cost Basis Withdrawn:   ${cost_basis_withdrawn:,.2f} (not taxed)
Realized Gain:          ${tax_calc['realized_gain']:,.2f} (taxable)
Tax Due (37%):          ${tax_calc['tax_due']:,.2f}
Net Proceeds:           ${tax_calc['net_proceeds']:,.2f}

The net proceeds of ${tax_calc['net_proceeds']:,.2f} will be transferred to your account.

TAX INFORMATION:
{'='*60}
The ${tax_calc['tax_due']:,.2f} withheld will be paid to the IRS on behalf
of the fund. This represents your proportional share of the fund's
tax liability.

No further tax filing is required from you for this withdrawal.

YOUR REMAINING POSITION:
{'='*60}
Remaining Shares:       {new_shares:,.4f}
Current Share Price:    ${nav_per_share:.4f}
Current Value:          ${float(new_shares) * nav_per_share:,.2f}
Total Invested:         ${new_net_investment:,.2f}

Thank you for your investment in Tovito Trader!

Questions? Just reply to this email.

Best regards,
David Lang
Tovito Trader
"""
                
                send_email(
                    to_email=investor_email,
                    subject=subject,
                    message=message
                )
                print(f"\n✅ Confirmation email sent to {investor_email}")
                
            except Exception as e:
                print(f"\n⚠️  Warning: Could not send email: {e}")
        
        return True, {
            'shares_sold': float(shares_to_sell),
            'new_shares': float(new_shares),
            'new_net_investment': float(new_net_investment),
            **tax_calc
        }
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error processing withdrawal: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


def main():
    print("=" * 70)
    print("PROCESS WITHDRAWAL (WITH HISTORICAL DATE SUPPORT)")
    print("=" * 70)
    print()
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Get current NAV
        current_nav_data = get_current_nav(conn)
        
        if not current_nav_data:
            print("❌ No NAV history found.")
            conn.close()
            return
        
        nav_date, current_nav, portfolio_value, total_shares = current_nav_data
        
        print(f"📊 CURRENT PORTFOLIO STATUS (as of {nav_date})")
        print("-" * 70)
        print(f"   Portfolio Value: ${portfolio_value:,.2f}")
        print(f"   NAV per Share:   ${current_nav:.4f}")
        print()
        
        # Get active investors
        investors = get_active_investors(conn)
        
        if not investors:
            print("❌ No active investors found.")
            conn.close()
            return
        
        print("👥 ACTIVE INVESTORS:")
        print("-" * 70)
        for idx, (inv_id, name, shares, net_inv, email) in enumerate(investors, 1):
            current_value = shares * current_nav
            unrealized_gain = current_value - net_inv
            tax_liability = unrealized_gain * TAX_RATE if unrealized_gain > 0 else 0
            after_tax_value = current_value - tax_liability
            
            print(f"   {idx}. {name} ({inv_id})")
            print(f"      Shares: {shares:,.4f}")
            print(f"      Gross Value: ${current_value:,.2f}")
            print(f"      After-Tax Value: ${after_tax_value:,.2f}")
            print(f"      Tax Liability: ${tax_liability:,.2f}")
        print()
        
        # Select investor
        while True:
            try:
                selection = input(f"Select investor (1-{len(investors)}) or 'cancel': ").strip()
                
                if selection.lower() == 'cancel':
                    print("Cancelled.")
                    conn.close()
                    return
                
                investor_num = int(selection)
                if 1 <= investor_num <= len(investors):
                    break
                else:
                    print(f"❌ Please enter 1-{len(investors)}")
            except ValueError:
                print("❌ Invalid input")
        
        investor_id, investor_name, current_shares, net_investment, investor_email = investors[investor_num - 1]
        
        print()
        print("=" * 70)
        print(f"WITHDRAWAL FOR: {investor_name} ({investor_id})")
        print("=" * 70)
        print()
        
        # Get transaction date
        print("📅 TRANSACTION DATE:")
        print(f"   Press Enter for today ({date.today()})")
        print(f"   Or enter date: YYYY-MM-DD (e.g., 2026-01-21)")
        print()
        
        while True:
            date_input = input("Transaction date: ").strip()
            
            if date_input == '':
                transaction_date = date.today()
                break
            
            try:
                transaction_date = datetime.strptime(date_input, '%Y-%m-%d').date()
                
                if transaction_date > date.today():
                    print("❌ Transaction date cannot be in the future")
                    continue
                
                break
            except ValueError:
                print("❌ Invalid date format. Use YYYY-MM-DD")
        
        print()
        print(f"✅ Using transaction date: {transaction_date}")
        print()
        
        # Get NAV for transaction date
        nav_data = get_nav_for_date(conn, transaction_date)
        
        if not nav_data:
            print(f"❌ No NAV found for {transaction_date}")
            conn.close()
            return
        
        nav_on_date, _, _ = nav_data
        
        print(f"📈 NAV ON {transaction_date}: ${nav_on_date:.4f}")
        print()
        
        # Calculate position on that date
        value_on_date = current_shares * nav_on_date
        unrealized_gain = value_on_date - net_investment
        tax_liability = unrealized_gain * TAX_RATE if unrealized_gain > 0 else 0
        after_tax_value = value_on_date - tax_liability
        
        print("CURRENT POSITION:")
        print("-" * 70)
        print(f"Shares:              {current_shares:,.4f}")
        print(f"Gross Value:         ${value_on_date:,.2f}")
        print(f"Net Investment:      ${net_investment:,.2f}")
        print(f"Unrealized Gain:     ${unrealized_gain:,.2f}")
        print(f"Tax Liability (37%): ${tax_liability:,.2f}")
        print(f"After-Tax Value:     ${after_tax_value:,.2f}")
        print()
        
        # Get withdrawal amount
        while True:
            try:
                amount_input = input("Withdrawal amount ($): ").strip()
                withdrawal_amount = float(amount_input)
                
                if withdrawal_amount <= 0:
                    print("❌ Amount must be positive")
                    continue
                
                if withdrawal_amount > value_on_date:
                    print(f"❌ Insufficient funds. Max: ${value_on_date:,.2f}")
                    continue
                
                break
            except ValueError:
                print("❌ Invalid amount")
        
        print()
        
        # Calculate preview
        shares_to_sell = withdrawal_amount / nav_on_date
        tax_calc = calculate_tax_on_withdrawal(withdrawal_amount, value_on_date, unrealized_gain)
        
        new_shares = current_shares - shares_to_sell
        proportion = tax_calc['proportion']
        new_net_investment = net_investment * (1 - proportion)
        
        # Show preview
        print("=" * 70)
        print("WITHDRAWAL PREVIEW")
        print("=" * 70)
        print()
        print(f"Transaction Date:        {transaction_date}")
        print(f"Withdrawal Amount:       ${withdrawal_amount:,.2f}")
        print(f"Share Price (NAV):       ${nav_on_date:.4f}")
        print(f"Shares to Sell:          {shares_to_sell:,.4f}")
        print()
        print("TAX CALCULATION:")
        print("-" * 70)
        print(f"Proportion Withdrawn:    {proportion*100:.2f}%")
        print(f"Cost Basis Portion:      ${(net_investment * proportion):,.2f} (not taxed)")
        print(f"Gain Portion:            ${tax_calc['realized_gain']:,.2f} (taxed at 37%)")
        print(f"Tax Due:                 ${tax_calc['tax_due']:,.2f}")
        print(f"NET PROCEEDS:            ${tax_calc['net_proceeds']:,.2f}")
        print()
        print("POSITION AFTER WITHDRAWAL:")
        print("-" * 70)
        print(f"Remaining Shares:        {new_shares:,.4f}")
        print(f"Remaining Value:         ${(new_shares * nav_on_date):,.2f}")
        print(f"Remaining Investment:    ${new_net_investment:,.2f}")
        print()
        print("=" * 70)
        
        # Confirm
        confirm = input("\nConfirm withdrawal? (yes/no): ").strip().lower()
        
        if confirm not in ['yes', 'y']:
            print("Cancelled.")
            conn.close()
            return
        
        # Process withdrawal
        print()
        print("Processing withdrawal...")
        
        success, result = process_withdrawal(
            conn, investor_id, investor_name, investor_email,
            withdrawal_amount, transaction_date,
            nav_on_date, current_shares, net_investment
        )
        
        if success:
            print()
            print("=" * 70)
            print("✅ WITHDRAWAL PROCESSED SUCCESSFULLY!")
            print("=" * 70)
            print()
            print(f"Investor:        {investor_name}")
            print(f"Date:            {transaction_date}")
            print(f"Gross Amount:    ${withdrawal_amount:,.2f}")
            print(f"Tax Withheld:    ${result['tax_due']:,.2f}")
            print(f"Net Proceeds:    ${result['net_proceeds']:,.2f}")
            print()
            print(f"Shares Sold:     {result['shares_sold']:,.4f}")
            print(f"Remaining:       {result['new_shares']:,.4f} shares")
            print()
        else:
            print(f"\n❌ Withdrawal failed: {result}")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
