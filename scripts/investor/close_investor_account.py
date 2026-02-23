"""
Close Investor Account

Complete account closure with full liquidation via fund flow workflow.
Creates proper fund_flow_requests records for audit trail.

Tax is NOT withheld at closure — realized gains are recorded and settled
quarterly via scripts/tax/quarterly_tax_payment.py.

Usage:
    python scripts/investor/close_investor_account.py --investor 20260101-01A
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from dotenv import load_dotenv

load_dotenv()

PROJECT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

DB_PATH = PROJECT_DIR / 'data' / 'tovito.db'
TAX_RATE = Decimal('0.37')

# Try to import email service
EMAIL_AVAILABLE = False
try:
    from src.automation.email_service import EmailService
    EMAIL_AVAILABLE = True
except ImportError:
    try:
        from src.automation.email_service import send_email
        EMAIL_AVAILABLE = True
    except ImportError:
        pass


def close_account():
    """Close investor account with full liquidation via fund flow workflow."""

    parser = argparse.ArgumentParser(description='Close investor account')
    parser.add_argument('--investor', required=True, help='Investor ID')
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # Get current NAV
        nav_row = conn.execute("""
            SELECT nav_per_share, date, total_portfolio_value, total_shares
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """).fetchone()

        if not nav_row:
            print("Error: No NAV data available")
            return False

        nav_per_share = Decimal(str(round(nav_row['nav_per_share'], 4)))
        nav_date = nav_row['date']
        portfolio_value = Decimal(str(nav_row['total_portfolio_value']))
        total_shares_fund = Decimal(str(nav_row['total_shares']))

        # Get investor
        investor = conn.execute("""
            SELECT investor_id, name, email, current_shares, net_investment, status
            FROM investors
            WHERE investor_id = ?
        """, (args.investor,)).fetchone()

        if not investor:
            print(f"Error: Investor {args.investor} not found")
            return False

        inv_id = investor['investor_id']
        name = investor['name']
        email = investor['email']
        shares = Decimal(str(investor['current_shares']))
        net_inv = Decimal(str(investor['net_investment']))
        status = investor['status']

        if status == 'Inactive':
            print(f"Investor {inv_id} is already inactive")
            return True

        # Calculate final position
        gross_value = (shares * nav_per_share).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        unrealized_gain = max(Decimal('0'), gross_value - net_inv)
        tax_liability = (unrealized_gain * TAX_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        after_tax_value = gross_value - tax_liability

        print("=" * 80)
        print(f"CLOSE INVESTOR ACCOUNT")
        print("=" * 80)
        print(f"Investor ID: {inv_id}")
        print(f"NAV Date: {nav_date}")
        print(f"NAV: ${float(nav_per_share):.4f}")
        print()
        print("CURRENT POSITION:")
        print(f"  Shares:                {float(shares):,.4f}")
        print(f"  Gross Value:           ${float(gross_value):,.2f}")
        print(f"  Net Investment:        ${float(net_inv):,.2f}")
        print(f"  Unrealized Gain:       ${float(unrealized_gain):,.2f}")
        print()
        print("FINAL SETTLEMENT:")
        print(f"  Realized Gain:         ${float(unrealized_gain):,.2f} (tax settled quarterly)")
        print(f"  Amount Disbursed:      ${float(gross_value):,.2f} (full gross value)")
        print(f"  Est. Tax Liability:    ${float(tax_liability):,.2f} (settled in next quarterly payment)")
        print()
        print("CLOSURE PLAN:")
        print(f"  1. Sell all {float(shares):,.4f} shares")
        print(f"  2. Disburse ${float(gross_value):,.2f} to investor (full amount)")
        print(f"  3. Record realized gain for quarterly tax settlement")
        print(f"  4. Mark account inactive")
        print()

        confirm = input("Close this account? (yes/no): ").strip().lower()
        if confirm not in ('yes', 'y'):
            print("Cancelled.")
            return False

        print()
        print("Processing account closure...")

        now = datetime.now().isoformat()
        today = datetime.now().date().isoformat()

        # Step 1: Create fund_flow_requests record for the closure withdrawal
        conn.execute("""
            INSERT INTO fund_flow_requests (
                investor_id, flow_type, requested_amount, request_date,
                request_method, status, notes, created_at, updated_at
            ) VALUES (?, 'withdrawal', ?, ?, 'admin', 'processed', ?, ?, ?)
        """, (
            inv_id,
            float(gross_value),
            today,
            "Account closure - full liquidation",
            now, now,
        ))
        request_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Step 2: Insert withdrawal transaction with fund flow linkage
        conn.execute("""
            INSERT INTO transactions (
                date, investor_id, transaction_type, amount,
                shares_transacted, nav_per_share, description,
                reference_id, notes, created_at, updated_at
            ) VALUES (?, ?, 'Withdrawal', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            today,
            inv_id,
            float(-gross_value),
            float(-shares),
            float(nav_per_share),
            f"Account closure - withdrawal of ${float(gross_value):,.2f} at NAV ${float(nav_per_share):,.4f}",
            f"ffr-{request_id}",
            f"Account closure - fund flow request #{request_id}",
            now, now,
        ))
        transaction_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Step 3: Record realized gain as tax event (no withholding)
        if unrealized_gain > 0:
            conn.execute("""
                INSERT INTO tax_events (
                    date, investor_id, event_type, withdrawal_amount,
                    realized_gain, tax_rate, tax_due, net_proceeds,
                    reference_id, created_at, updated_at
                ) VALUES (?, ?, 'Realized_Gain', ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                today,
                inv_id,
                float(gross_value),
                float(unrealized_gain),
                float(TAX_RATE),
                0.0,  # No tax withheld — settled quarterly
                float(gross_value),
                f"ffr-{request_id}",
                now, now,
            ))

        # Step 4: Update fund_flow_requests with processing details
        conn.execute("""
            UPDATE fund_flow_requests
            SET processed_date = ?,
                actual_amount = ?,
                shares_transacted = ?,
                nav_per_share = ?,
                transaction_id = ?,
                realized_gain = ?,
                tax_withheld = 0,
                net_proceeds = ?,
                updated_at = ?
            WHERE request_id = ?
        """, (
            now,
            float(gross_value),
            float(shares),
            float(nav_per_share),
            transaction_id,
            float(unrealized_gain),
            float(gross_value),
            now,
            request_id,
        ))

        # Step 5: Update investor to inactive with zero shares
        conn.execute("""
            UPDATE investors
            SET status = 'Inactive',
                current_shares = 0,
                net_investment = 0,
                updated_at = ?
            WHERE investor_id = ?
        """, (now, inv_id))

        # Step 6: Update daily NAV totals
        new_portfolio_value = float(portfolio_value - gross_value)
        new_total_shares = float(total_shares_fund - shares)

        conn.execute("""
            UPDATE daily_nav
            SET total_portfolio_value = ?,
                total_shares = ?
            WHERE date = ?
        """, (round(new_portfolio_value, 2), round(new_total_shares, 4), nav_date))

        # Step 7: Log to system_logs
        conn.execute("""
            INSERT INTO system_logs (timestamp, level, category, message, details)
            VALUES (?, 'INFO', 'Account Closure', ?, ?)
        """, (
            now,
            f"Account closed for {inv_id}: ${float(gross_value):,.2f} disbursed",
            f"request_id={request_id}, transaction_id={transaction_id}, "
            f"shares={float(shares):.4f}, nav={float(nav_per_share):.4f}, "
            f"realized_gain={float(unrealized_gain):,.2f}",
        ))

        conn.commit()

        print("   Database updated")

        # Send emails
        if EMAIL_AVAILABLE:
            try:
                email_service = EmailService()

                # Investor confirmation
                subject = "Account Closure Confirmation - Tovito Trader"
                body = f"""Account Closure Confirmation
============================

Your account has been closed.

FINAL ACCOUNT SUMMARY
=====================
Gross Value:           ${float(gross_value):,.2f}
Net Investment:        ${float(net_inv):,.2f}
Total Gain:            ${float(unrealized_gain):,.2f}

DISBURSEMENT
============
Amount Disbursed:      ${float(gross_value):,.2f}

Note: Tax on realized gains (${float(unrealized_gain):,.2f}) will be
settled in the next quarterly tax payment.

INVESTMENT SUMMARY
==================
Total Invested:        ${float(net_inv):,.2f}
Total Returned:        ${float(gross_value):,.2f}
Gross Return:          {float((gross_value / net_inv - 1) * 100) if net_inv > 0 else 0:.2f}%

Thank you for investing with Tovito Trader.
"""
                email_service.send_general_email(
                    recipient=None,
                    subject=subject,
                    body=body,
                )
                print("   Confirmation email sent")
            except Exception as e:
                print(f"   Note: Email not sent ({e})")

        print()
        print("=" * 80)
        print("ACCOUNT CLOSURE COMPLETE")
        print("=" * 80)
        print(f"  Investor:    {inv_id}")
        print(f"  Disbursed:   ${float(gross_value):,.2f}")
        print(f"  Realized Gain: ${float(unrealized_gain):,.2f} (tax settled quarterly)")
        print(f"  Status:      Inactive")
        print()
        print("Audit Links:")
        print(f"  fund_flow_requests.request_id = {request_id}")
        print(f"  fund_flow_requests.transaction_id = {transaction_id}")
        print(f"  transactions.reference_id = 'ffr-{request_id}'")
        print()

        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        success = close_account()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(1)
