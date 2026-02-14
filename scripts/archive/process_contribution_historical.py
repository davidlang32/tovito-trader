"""
Process Contribution with Historical Date Support
CORRECTED VERSION - Uses actual database schema

Usage:
    python scripts/process_contribution_historical.py
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from src.automation.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent / 'data' / 'tovito.db'


def get_nav_for_date(conn, transaction_date):
    """Get NAV per share for a specific date"""
    cursor = conn.cursor()
    
    # Try exact date first - TABLE NAME: daily_nav
    cursor.execute("""
        SELECT nav_per_share, total_portfolio_value, total_shares
        FROM daily_nav
        WHERE DATE(date) = DATE(?)
        ORDER BY date DESC
        LIMIT 1
    """, (transaction_date,))
    
    result = cursor.fetchone()
    
    if result:
        return result
    
    # If no exact match, try most recent before this date
    cursor.execute("""
        SELECT nav_per_share, total_portfolio_value, total_shares
        FROM daily_nav
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
        FROM daily_nav
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


def calculate_shares_to_buy(contribution_amount, nav_per_share):
    """Calculate shares to purchase"""
    return Decimal(str(contribution_amount)) / Decimal(str(nav_per_share))


def process_contribution(conn, investor_id, investor_name, investor_email,
                        contribution_amount, transaction_date,
                        nav_per_share, current_shares, net_investment):
    """Process the contribution transaction"""
    
    # Calculate shares
    shares_to_buy = calculate_shares_to_buy(contribution_amount, nav_per_share)
    new_shares = Decimal(str(current_shares)) + shares_to_buy
    new_net_investment = Decimal(str(net_investment)) + Decimal(str(contribution_amount))
    
    cursor = conn.cursor()
    
    try:
        # Get current NAV for today's value calculation
        current_nav_data = get_current_nav(conn)
        if current_nav_data:
            today_date, today_nav, today_portfolio, today_total_shares = current_nav_data
        else:
            today_nav = nav_per_share
        
        # Calculate current value and gain
        current_value = float(new_shares) * float(today_nav)
        gain_since_contribution = current_value - float(new_net_investment)
        gain_percent = (gain_since_contribution / float(new_net_investment)) * 100 if new_net_investment > 0 else 0
        
        # Update investor
        cursor.execute("""
            UPDATE investors
            SET current_shares = ?,
                net_investment = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE investor_id = ?
        """, (float(new_shares), float(new_net_investment), investor_id))
        
        # Record transaction - COLUMN NAME: date (not transaction_date)
        cursor.execute("""
            INSERT INTO transactions (
                investor_id, date, transaction_type,
                amount, share_price, shares_transacted, notes
            ) VALUES (?, ?, 'Contribution', ?, ?, ?, ?)
        """, (
            investor_id,
            transaction_date,
            float(contribution_amount),
            float(nav_per_share),
            float(shares_to_buy),
            f"Contribution processed on {datetime.now().strftime('%Y-%m-%d')}"
        ))
        
        # Update daily_nav with new totals
        cursor.execute("""
            SELECT total_portfolio_value, total_shares
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        
        latest_nav = cursor.fetchone()
        if latest_nav:
            new_portfolio_value = latest_nav[0] + contribution_amount
            new_total_shares = latest_nav[1] + float(shares_to_buy)
            new_nav_per_share = new_portfolio_value / new_total_shares if new_total_shares > 0 else 0
            
            # Update latest NAV record
            cursor.execute("""
                UPDATE daily_nav
                SET total_portfolio_value = ?,
                    total_shares = ?,
                    nav_per_share = ?
                WHERE date = (SELECT MAX(date) FROM daily_nav)
            """, (new_portfolio_value, new_total_shares, new_nav_per_share))
        
        conn.commit()
        
        # Send email confirmation
        if EMAIL_AVAILABLE and investor_email:
            try:
                subject = f"Contribution Processed - ${contribution_amount:,.2f} Added"
                
                message = f"""Hi {investor_name},

Your contribution has been successfully processed!

CONTRIBUTION DETAILS:
{'='*60}
Transaction Date:       {transaction_date}
Amount Contributed:     ${contribution_amount:,.2f}
Share Price (NAV):      ${nav_per_share:.4f}
Shares Purchased:       {shares_to_buy:,.4f}

YOUR NEW POSITION (as of {today_date if current_nav_data else 'today'}):
{'='*60}
Total Shares:           {new_shares:,.4f}
Current Share Price:    ${today_nav:.4f}
Current Value:          ${current_value:,.2f}
Total Invested:         ${new_net_investment:,.2f}
Unrealized Gain/Loss:   ${gain_since_contribution:+,.2f} ({gain_percent:+.2f}%)

PERFORMANCE SINCE CONTRIBUTION:
{'='*60}
NAV when contributed:   ${nav_per_share:.4f}
NAV today:              ${today_nav:.4f}
Change:                 ${(today_nav - nav_per_share):+.4f} ({((today_nav/nav_per_share - 1) * 100):+.2f}%)

Thank you for your continued investment in Tovito Trader!

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
            'shares_bought': float(shares_to_buy),
            'new_shares': float(new_shares),
            'new_net_investment': float(new_net_investment),
            'current_value': current_value,
            'gain': gain_since_contribution,
            'gain_percent': gain_percent,
            'today_nav': today_nav
        }
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error processing contribution: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def main():
    print("=" * 70)
    print("PROCESS CONTRIBUTION (WITH HISTORICAL DATE SUPPORT)")
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
            print("❌ No NAV history found. Run daily NAV update first.")
            conn.close()
            return
        
        nav_date, current_nav, portfolio_value, total_shares = current_nav_data
        
        print(f"📊 CURRENT PORTFOLIO STATUS (as of {nav_date})")
        print("-" * 70)
        print(f"   Portfolio Value: ${portfolio_value:,.2f}")
        print(f"   Total Shares:    {total_shares:,.4f}")
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
            print(f"   {idx}. {name} ({inv_id})")
            print(f"      Shares: {shares:,.4f} | Value: ${current_value:,.2f}")
        print()
        
        # Select investor
        while True:
            try:
                selection = input("Select investor (1-{}) or 'cancel': ".format(len(investors))).strip()
                
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
        print(f"CONTRIBUTION FOR: {investor_name} ({investor_id})")
        print("=" * 70)
        print()
        
        # Get transaction date
        print("📅 TRANSACTION DATE:")
        print(f"   Press Enter for today ({date.today()})")
        print(f"   Or enter date in format: YYYY-MM-DD (e.g., 2026-01-21)")
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
            print(f"❌ No NAV found for {transaction_date} or earlier")
            print("   Please run daily NAV update for that date first")
            conn.close()
            return
        
        nav_on_date, portfolio_on_date, shares_on_date = nav_data
        
        print(f"📈 NAV ON {transaction_date}: ${nav_on_date:.4f}")
        if str(transaction_date) != str(nav_date):
            print(f"📈 NAV TODAY ({nav_date}): ${current_nav:.4f}")
            change = ((current_nav / nav_on_date) - 1) * 100
            print(f"   Change since transaction: {change:+.2f}%")
        print()
        
        # Get contribution amount
        while True:
            try:
                amount_input = input("Contribution amount ($): ").strip()
                contribution_amount = float(amount_input)
                
                if contribution_amount <= 0:
                    print("❌ Amount must be positive")
                    continue
                
                break
            except ValueError:
                print("❌ Invalid amount")
        
        print()
        
        # Calculate shares
        shares_to_buy = calculate_shares_to_buy(contribution_amount, nav_on_date)
        new_shares = Decimal(str(current_shares)) + shares_to_buy
        new_net_investment = Decimal(str(net_investment)) + Decimal(str(contribution_amount))
        
        # Calculate current value
        current_value = float(new_shares) * current_nav
        value_at_contribution = float(new_shares) * nav_on_date
        gain_since = current_value - value_at_contribution
        
        # Show preview
        print("=" * 70)
        print("CONTRIBUTION PREVIEW")
        print("=" * 70)
        print()
        print(f"Transaction Date:        {transaction_date}")
        print(f"Contribution Amount:     ${contribution_amount:,.2f}")
        print(f"Share Price (NAV):       ${nav_on_date:.4f}")
        print(f"Shares to Purchase:      {shares_to_buy:,.4f}")
        print()
        print("POSITION AFTER CONTRIBUTION:")
        print("-" * 70)
        print(f"Current Shares:          {current_shares:,.4f}")
        print(f"New Shares:              {new_shares:,.4f} (+{shares_to_buy:,.4f})")
        print()
        print(f"Current Net Investment:  ${net_investment:,.2f}")
        print(f"New Net Investment:      ${new_net_investment:,.2f} (+${contribution_amount:,.2f})")
        print()
        
        if str(transaction_date) != str(nav_date):
            print(f"VALUE AT CONTRIBUTION:   ${value_at_contribution:,.2f}")
            print(f"CURRENT VALUE (today):   ${current_value:,.2f}")
            print(f"Gain Since Contribution: ${gain_since:+,.2f} ({(gain_since/value_at_contribution*100):+.2f}%)")
        else:
            print(f"Current Value:           ${current_value:,.2f}")
        
        print()
        print("=" * 70)
        
        # Confirm
        confirm = input("\nConfirm contribution? (yes/no): ").strip().lower()
        
        if confirm not in ['yes', 'y']:
            print("Cancelled.")
            conn.close()
            return
        
        # Process contribution
        print()
        print("Processing contribution...")
        
        success, result = process_contribution(
            conn, investor_id, investor_name, investor_email,
            contribution_amount, transaction_date,
            nav_on_date, current_shares, net_investment
        )
        
        if success:
            print()
            print("=" * 70)
            print("✅ CONTRIBUTION PROCESSED SUCCESSFULLY!")
            print("=" * 70)
            print()
            print(f"Investor:        {investor_name}")
            print(f"Amount:          ${contribution_amount:,.2f}")
            print(f"Date:            {transaction_date}")
            print(f"Shares Bought:   {result['shares_bought']:,.4f}")
            print(f"New Total:       {result['new_shares']:,.4f} shares")
            print(f"Current Value:   ${result['current_value']:,.2f}")
            print(f"Total Invested:  ${result['new_net_investment']:,.2f}")
            print(f"Unrealized Gain: ${result['gain']:+,.2f} ({result['gain_percent']:+.2f}%)")
            print()
        else:
            print()
            print("❌ Contribution failed. No changes made.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"\n❌ Database error: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
