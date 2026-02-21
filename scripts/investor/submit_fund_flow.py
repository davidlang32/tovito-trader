"""
Submit Fund Flow Request
========================
Interactive CLI for submitting contribution or withdrawal requests.
Creates a tracked request record in fund_flow_requests table.

Does NOT process shares — just creates the request for the
fund manager to approve, match, and process.

Usage:
    python scripts/investor/submit_fund_flow.py
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal

PROJECT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

DB_PATH = PROJECT_DIR / 'data' / 'tovito.db'


def get_active_investors(conn):
    """Fetch active investors for selection."""
    cursor = conn.execute("""
        SELECT investor_id, name, current_shares, net_investment
        FROM investors
        WHERE status = 'Active'
        ORDER BY name
    """)
    return cursor.fetchall()


def get_latest_nav(conn):
    """Get the most recent NAV per share."""
    cursor = conn.execute("""
        SELECT nav_per_share, date FROM daily_nav
        ORDER BY date DESC LIMIT 1
    """)
    row = cursor.fetchone()
    if row:
        return float(row[0]), row[1]
    return None, None


def submit_request():
    """Interactive flow to submit a fund flow request."""
    print()
    print("=" * 60)
    print("SUBMIT FUND FLOW REQUEST")
    print("=" * 60)
    print()

    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # Step 1: Select flow type
        print("Request Type:")
        print("  1. Contribution (investor adding funds)")
        print("  2. Withdrawal (investor removing funds)")
        print()

        flow_choice = input("Select type (1 or 2): ").strip()
        if flow_choice == '1':
            flow_type = 'contribution'
        elif flow_choice == '2':
            flow_type = 'withdrawal'
        else:
            print("Invalid selection. Exiting.")
            return False

        print()

        # Step 2: Select investor
        investors = get_active_investors(conn)
        if not investors:
            print("No active investors found.")
            return False

        print("Active Investors:")
        for i, inv in enumerate(investors, 1):
            shares = float(inv['current_shares'])
            nav, _ = get_latest_nav(conn)
            value = shares * nav if nav else 0
            print(f"  {i}. {inv['name']} ({inv['investor_id']}) - {shares:,.2f} shares")
        print()

        inv_choice = input("Select investor number: ").strip()
        try:
            inv_index = int(inv_choice) - 1
            if inv_index < 0 or inv_index >= len(investors):
                print("Invalid selection.")
                return False
        except ValueError:
            print("Invalid input.")
            return False

        investor = investors[inv_index]
        investor_id = investor['investor_id']
        investor_name = investor['name']
        print(f"  Selected: {investor_name}")
        print()

        # Step 3: Enter amount
        amount_str = input(f"Enter {flow_type} amount: $").strip()
        try:
            amount = Decimal(amount_str.replace(',', ''))
            if amount <= 0:
                print("Amount must be positive.")
                return False
        except Exception:
            print("Invalid amount.")
            return False

        # For withdrawals, validate against current value
        if flow_type == 'withdrawal':
            nav, nav_date = get_latest_nav(conn)
            if nav:
                current_value = float(investor['current_shares']) * nav
                if float(amount) > current_value:
                    print(f"\nWarning: Requested ${amount:,.2f} exceeds estimated")
                    print(f"         current value of ${current_value:,.2f}")
                    proceed = input("Continue anyway? (yes/no): ").strip().lower()
                    if proceed not in ('yes', 'y'):
                        print("Request cancelled.")
                        return False

        print()

        # Step 4: Enter request date
        date_str = input(f"Request date (YYYY-MM-DD, or Enter for today): ").strip()
        if not date_str:
            request_date = date.today().isoformat()
        else:
            try:
                parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
                request_date = parsed.isoformat()
            except ValueError:
                print("Invalid date format. Use YYYY-MM-DD.")
                return False
        print(f"  Date: {request_date}")
        print()

        # Step 5: Request method
        print("Request Method:")
        print("  1. Portal (investor portal)")
        print("  2. Email")
        print("  3. Verbal")
        print("  4. Admin (fund manager initiated)")
        print("  5. Other")
        print()

        method_choice = input("Select method (1-5, default 4): ").strip() or '4'
        method_map = {'1': 'portal', '2': 'email', '3': 'verbal', '4': 'admin', '5': 'other'}
        request_method = method_map.get(method_choice, 'admin')
        print(f"  Method: {request_method}")
        print()

        # Step 6: Optional notes
        notes = input("Notes (optional, press Enter to skip): ").strip() or None
        print()

        # Step 7: Preview and confirm
        print("-" * 60)
        print("REQUEST SUMMARY")
        print("-" * 60)
        print(f"  Type:      {flow_type.upper()}")
        print(f"  Investor:  {investor_name} ({investor_id})")
        print(f"  Amount:    ${amount:,.2f}")
        print(f"  Date:      {request_date}")
        print(f"  Method:    {request_method}")
        if notes:
            print(f"  Notes:     {notes}")

        # Show current position context
        nav, nav_date = get_latest_nav(conn)
        if nav:
            shares = float(investor['current_shares'])
            current_value = shares * nav
            print()
            print(f"  Current Position (as of {nav_date}):")
            print(f"    NAV/Share:  ${nav:,.4f}")
            print(f"    Shares:     {shares:,.4f}")
            print(f"    Est. Value: ${current_value:,.2f}")

            if flow_type == 'contribution':
                new_shares = float(amount) / nav
                print(f"    Est. New Shares: {new_shares:,.4f}")
            elif flow_type == 'withdrawal':
                shares_to_sell = float(amount) / nav
                net_inv = float(investor['net_investment'])
                proportion = float(amount) / current_value if current_value > 0 else 0
                unrealized_gain = max(0, current_value - net_inv)
                est_realized = unrealized_gain * proportion
                est_tax = est_realized * 0.37
                print(f"    Est. Shares to Sell: {shares_to_sell:,.4f}")
                print(f"    Est. Realized Gain:  ${est_realized:,.2f}")
                print(f"    Est. Tax (37%):      ${est_tax:,.2f}")
                print(f"    Est. Net Proceeds:   ${float(amount) - est_tax:,.2f}")

        print("-" * 60)
        print()

        confirm = input("Submit this request? (yes/no): ").strip().lower()
        if confirm not in ('yes', 'y'):
            print("Request cancelled.")
            return False

        # Step 8: Insert into database
        now = datetime.now().isoformat()
        conn.execute("""
            INSERT INTO fund_flow_requests (
                investor_id, flow_type, requested_amount, request_date,
                request_method, status, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
        """, (
            investor_id, flow_type, float(amount), request_date,
            request_method, notes, now, now,
        ))

        # Get the new request ID
        cursor = conn.execute("SELECT last_insert_rowid()")
        request_id = cursor.fetchone()[0]

        # Log to system_logs
        conn.execute("""
            INSERT INTO system_logs (timestamp, level, category, message, details)
            VALUES (?, 'INFO', 'Fund Flow', ?, ?)
        """, (
            now,
            f"Fund flow request submitted: {flow_type} ${float(amount):,.2f} for investor {investor_id}",
            f"request_id={request_id}, method={request_method}",
        ))

        conn.commit()

        print()
        print(f"Request #{request_id} submitted successfully!")
        print(f"Status: PENDING (awaiting approval)")
        print()
        print("Next steps:")
        print(f"  1. Approve:  Update status in fund manager dashboard")
        print(f"  2. Match:    python scripts/investor/match_fund_flow.py")
        print(f"  3. Process:  python scripts/investor/process_fund_flow.py")
        print()

        return True

    except sqlite3.Error as e:
        print(f"\nDatabase error: {e}")
        conn.rollback()
        return False
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        success = submit_request()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
