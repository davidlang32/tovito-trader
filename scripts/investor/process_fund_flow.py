"""
Process Fund Flow Request
=========================
Takes a matched fund flow request and executes share accounting:
  - Contribution: calculates new shares, updates investor, records transaction
  - Withdrawal: calculates shares to sell, tax, updates investor, records events

Only processes requests with status 'matched' (brokerage ACH confirmed).

Usage:
    python scripts/investor/process_fund_flow.py
    python scripts/investor/process_fund_flow.py --request-id 5
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import argparse
import sqlite3
import sys
from pathlib import Path
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

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
    pass


def get_processable_requests(conn, request_id=None):
    """Fetch matched fund flow requests ready for processing."""
    query = """
        SELECT ffr.*, i.name as investor_name, i.current_shares,
               i.net_investment, i.status as investor_status
        FROM fund_flow_requests ffr
        JOIN investors i ON ffr.investor_id = i.investor_id
        WHERE ffr.status = 'matched'
    """
    params = []
    if request_id:
        query += " AND ffr.request_id = ?"
        params.append(request_id)
    query += " ORDER BY ffr.request_date"
    return conn.execute(query, params).fetchall()


def get_nav_for_date(conn, target_date):
    """
    Get NAV per share for a specific date (4 decimal places).
    Falls back to most recent NAV before that date.
    """
    # Try exact date first
    cursor = conn.execute(
        "SELECT nav_per_share FROM daily_nav WHERE date = ? LIMIT 1",
        (target_date,)
    )
    row = cursor.fetchone()
    if row:
        return Decimal(str(round(row[0], 4)))

    # Fall back to most recent before that date
    cursor = conn.execute(
        "SELECT nav_per_share FROM daily_nav WHERE date <= ? ORDER BY date DESC LIMIT 1",
        (target_date,)
    )
    row = cursor.fetchone()
    if row:
        return Decimal(str(round(row[0], 4)))

    # Last resort: most recent NAV
    cursor = conn.execute(
        "SELECT nav_per_share FROM daily_nav ORDER BY date DESC LIMIT 1"
    )
    row = cursor.fetchone()
    if row:
        return Decimal(str(round(row[0], 4)))

    return None


def process_contribution(conn, req, nav_per_share):
    """
    Execute share accounting for a contribution.

    Returns dict with processing details.
    """
    investor_id = req['investor_id']
    amount = Decimal(str(req['actual_amount'] or req['requested_amount']))
    request_date = req['matched_date'][:10] if req['matched_date'] else req['request_date']

    # Calculate shares
    new_shares = (amount / nav_per_share).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    current_shares = Decimal(str(req['current_shares']))
    new_total_shares = current_shares + new_shares
    net_investment = Decimal(str(req['net_investment']))
    new_net_investment = net_investment + amount

    now = datetime.now().isoformat()

    # Insert transaction
    conn.execute("""
        INSERT INTO transactions (
            date, investor_id, transaction_type, amount,
            shares_transacted, nav_per_share, description,
            reference_id, notes, created_at, updated_at
        ) VALUES (?, ?, 'Contribution', ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        request_date,
        investor_id,
        float(amount),
        float(new_shares),
        float(nav_per_share),
        f"Contribution of ${float(amount):,.2f} at NAV ${float(nav_per_share):,.4f}",
        f"ffr-{req['request_id']}",
        f"Fund flow request #{req['request_id']}",
        now, now,
    ))
    transaction_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Update investor
    conn.execute("""
        UPDATE investors
        SET current_shares = ?,
            net_investment = ?,
            updated_at = ?
        WHERE investor_id = ?
    """, (float(new_total_shares), float(new_net_investment), now, investor_id))

    return {
        'transaction_id': transaction_id,
        'amount': float(amount),
        'nav_per_share': float(nav_per_share),
        'shares_transacted': float(new_shares),
        'new_total_shares': float(new_total_shares),
        'new_net_investment': float(new_net_investment),
        'realized_gain': 0.0,
        'tax_withheld': 0.0,
        'net_proceeds': float(amount),
    }


def process_withdrawal(conn, req, nav_per_share):
    """
    Execute share accounting for a withdrawal.

    Uses proportional gain allocation. Tax is NOT withheld at withdrawal —
    it is settled quarterly via scripts/tax/quarterly_tax_payment.py.
    Realized gains are still calculated and recorded for tax reporting.

    Returns dict with processing details.
    """
    investor_id = req['investor_id']
    amount = Decimal(str(req['actual_amount'] or req['requested_amount']))
    request_date = req['matched_date'][:10] if req['matched_date'] else req['request_date']

    current_shares = Decimal(str(req['current_shares']))
    net_investment = Decimal(str(req['net_investment']))
    current_value = current_shares * nav_per_share

    # Validate
    if amount > current_value:
        raise ValueError(
            f"Withdrawal ${float(amount):,.2f} exceeds current value ${float(current_value):,.2f}"
        )

    # Calculate shares to sell
    shares_to_sell = (amount / nav_per_share).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

    # Proportional gain calculation (for tax reporting — not withheld)
    proportion = amount / current_value if current_value > 0 else Decimal('0')
    total_unrealized_gain = max(Decimal('0'), current_value - net_investment)
    realized_gain = (total_unrealized_gain * proportion).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )

    # No tax withholding — full amount disbursed, tax settled quarterly
    net_proceeds = amount

    new_shares = current_shares - shares_to_sell
    cost_basis_sold = (net_investment * proportion).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    new_net_investment = net_investment - cost_basis_sold

    now = datetime.now().isoformat()

    # Insert withdrawal transaction
    conn.execute("""
        INSERT INTO transactions (
            date, investor_id, transaction_type, amount,
            shares_transacted, nav_per_share, description,
            reference_id, notes, created_at, updated_at
        ) VALUES (?, ?, 'Withdrawal', ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        request_date,
        investor_id,
        float(-amount),  # Withdrawals are negative
        float(-shares_to_sell),
        float(nav_per_share),
        f"Withdrawal of ${float(amount):,.2f} at NAV ${float(nav_per_share):,.4f}",
        f"ffr-{req['request_id']}",
        f"Fund flow request #{req['request_id']}",
        now, now,
    ))
    transaction_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Record realized gain as tax event (for quarterly tax settlement)
    if realized_gain > 0:
        conn.execute("""
            INSERT INTO tax_events (
                date, investor_id, event_type, withdrawal_amount,
                realized_gain, tax_rate, tax_due, net_proceeds,
                reference_id, created_at, updated_at
            ) VALUES (?, ?, 'Realized_Gain', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request_date,
            investor_id,
            float(amount),
            float(realized_gain),
            float(TAX_RATE),
            0.0,  # No tax withheld — settled quarterly
            float(net_proceeds),
            f"ffr-{req['request_id']}",
            now, now,
        ))

    # Update investor
    conn.execute("""
        UPDATE investors
        SET current_shares = ?,
            net_investment = ?,
            updated_at = ?
        WHERE investor_id = ?
    """, (float(new_shares), float(new_net_investment), now, investor_id))

    return {
        'transaction_id': transaction_id,
        'amount': float(amount),
        'nav_per_share': float(nav_per_share),
        'shares_transacted': float(shares_to_sell),
        'new_total_shares': float(new_shares),
        'new_net_investment': float(new_net_investment),
        'realized_gain': float(realized_gain),
        'tax_withheld': 0.0,
        'net_proceeds': float(net_proceeds),
    }


def send_confirmation_email(req, result, flow_type):
    """Send confirmation email to the investor (best-effort)."""
    if not EMAIL_AVAILABLE:
        return False

    try:
        email_service = EmailService()
        investor_name = req['investor_name']

        if flow_type == 'contribution':
            subject = f"Tovito Fund - Contribution Processed (${result['amount']:,.2f})"
            body = f"""
Contribution Confirmation
========================

Investor: {investor_name}
Amount: ${result['amount']:,.2f}
NAV/Share: ${result['nav_per_share']:,.4f}
Shares Purchased: {result['shares_transacted']:,.4f}
New Total Shares: {result['new_total_shares']:,.4f}

Thank you for your contribution.
"""
        else:
            subject = f"Tovito Fund - Withdrawal Processed (${result['amount']:,.2f})"
            body = f"""
Withdrawal Confirmation
========================

Investor: {investor_name}
Withdrawal Amount: ${result['amount']:,.2f}
NAV/Share: ${result['nav_per_share']:,.4f}
Shares Sold: {result['shares_transacted']:,.4f}

Realized Gain: ${result['realized_gain']:,.2f}
Amount Disbursed: ${result['net_proceeds']:,.2f}

Note: Tax on realized gains is settled quarterly.
No tax has been withheld from this withdrawal.

Remaining Shares: {result['new_total_shares']:,.4f}
"""

        email_service.send_general_email(
            recipient=None,  # Will use admin email
            subject=subject,
            body=body,
        )
        return True
    except Exception as e:
        print(f"  Note: Email not sent ({e})")
        return False


def process_flow():
    """Interactive flow to process a matched fund flow request."""
    parser = argparse.ArgumentParser(description="Process matched fund flow request")
    parser.add_argument('--request-id', type=int, help="Specific request ID to process")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("PROCESS FUND FLOW REQUEST")
    print("=" * 60)
    print()

    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # Step 1: Get processable requests
        requests = get_processable_requests(conn, args.request_id)

        if not requests:
            if args.request_id:
                print(f"No processable request found with ID #{args.request_id}")
                print("(Only requests with status 'matched' can be processed)")
            else:
                print("No matched fund flow requests awaiting processing.")
            return False

        print(f"MATCHED REQUESTS READY FOR PROCESSING ({len(requests)}):")
        print("-" * 60)
        for req in requests:
            amt = req['actual_amount'] or req['requested_amount']
            print(f"  #{req['request_id']:>3}  {req['flow_type']:>12}  "
                  f"${amt:>10,.2f}  {req['investor_name']}  "
                  f"(matched trade #{req['matched_trade_id']})")
        print()

        # Step 2: Select a request
        if args.request_id:
            selected_req = requests[0]
        elif len(requests) == 1:
            selected_req = requests[0]
            print(f"Auto-selected request #{selected_req['request_id']}")
        else:
            req_choice = input("Select request # to process: ").strip()
            try:
                req_id = int(req_choice)
                selected_req = next(
                    (r for r in requests if r['request_id'] == req_id), None
                )
                if not selected_req:
                    print(f"Request #{req_id} not found.")
                    return False
            except ValueError:
                print("Invalid input.")
                return False

        flow_type = selected_req['flow_type']
        amount = Decimal(str(
            selected_req['actual_amount'] or selected_req['requested_amount']
        ))

        # Step 3: Get NAV for the transaction date
        # Use matched_date (when ACH was confirmed) for share calculation
        process_date = (
            selected_req['matched_date'][:10]
            if selected_req['matched_date']
            else selected_req['request_date']
        )
        nav_per_share = get_nav_for_date(conn, process_date)

        if not nav_per_share:
            print("Error: Cannot determine NAV for processing.")
            print("Ensure daily_nav table has recent entries.")
            return False

        # Step 4: Preview
        current_shares = Decimal(str(selected_req['current_shares']))
        net_investment = Decimal(str(selected_req['net_investment']))
        current_value = current_shares * nav_per_share

        print()
        print("-" * 60)
        print("PROCESSING PREVIEW")
        print("-" * 60)
        print(f"  Request:     #{selected_req['request_id']} ({flow_type.upper()})")
        print(f"  Investor:    {selected_req['investor_name']} ({selected_req['investor_id']})")
        print(f"  Amount:      ${float(amount):,.2f}")
        print(f"  Process Date: {process_date}")
        print(f"  NAV/Share:   ${float(nav_per_share):,.4f}")
        print()

        if flow_type == 'contribution':
            new_shares = (amount / nav_per_share).quantize(
                Decimal('0.0001'), rounding=ROUND_HALF_UP
            )
            print(f"  Shares to Issue: {float(new_shares):,.4f}")
            print(f"  New Total:       {float(current_shares + new_shares):,.4f} shares")
        else:
            shares_to_sell = (amount / nav_per_share).quantize(
                Decimal('0.0001'), rounding=ROUND_HALF_UP
            )
            proportion = amount / current_value if current_value > 0 else Decimal('0')
            unrealized = max(Decimal('0'), current_value - net_investment)
            realized = (unrealized * proportion).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            print(f"  Shares to Sell:  {float(shares_to_sell):,.4f}")
            print(f"  Realized Gain:   ${float(realized):,.2f} (tax settled quarterly)")
            print(f"  Amount Disbursed: ${float(amount):,.2f} (full amount, no withholding)")
            print(f"  Remaining:       {float(current_shares - shares_to_sell):,.4f} shares")

        print("-" * 60)
        print()

        confirm = input("Process this request? (yes/no): ").strip().lower()
        if confirm not in ('yes', 'y'):
            print("Processing cancelled.")
            return False

        # Step 5: Execute
        if flow_type == 'contribution':
            result = process_contribution(conn, dict(selected_req), nav_per_share)
        else:
            result = process_withdrawal(conn, dict(selected_req), nav_per_share)

        # Step 6: Update fund_flow_requests
        now = datetime.now().isoformat()
        conn.execute("""
            UPDATE fund_flow_requests
            SET status = 'processed',
                processed_date = ?,
                actual_amount = ?,
                shares_transacted = ?,
                nav_per_share = ?,
                transaction_id = ?,
                realized_gain = ?,
                tax_withheld = ?,
                net_proceeds = ?,
                updated_at = ?
            WHERE request_id = ?
        """, (
            now,
            result['amount'],
            result['shares_transacted'],
            result['nav_per_share'],
            result['transaction_id'],
            result['realized_gain'],
            result['tax_withheld'],
            result['net_proceeds'],
            now,
            selected_req['request_id'],
        ))

        # Log to system_logs
        conn.execute("""
            INSERT INTO system_logs (timestamp, level, category, message, details)
            VALUES (?, 'INFO', 'Fund Flow', ?, ?)
        """, (
            now,
            f"Fund flow request #{selected_req['request_id']} processed: "
            f"{flow_type} ${result['amount']:,.2f} for {selected_req['investor_id']}",
            f"transaction_id={result['transaction_id']}, "
            f"shares={result['shares_transacted']:.4f}, "
            f"nav={result['nav_per_share']:.4f}",
        ))

        conn.commit()

        # Step 7: Output
        print()
        print("=" * 60)
        print("PROCESSED SUCCESSFULLY")
        print("=" * 60)
        print(f"  Request:       #{selected_req['request_id']}")
        print(f"  Transaction:   #{result['transaction_id']}")
        print(f"  Type:          {flow_type.upper()}")
        print(f"  Amount:        ${result['amount']:,.2f}")
        print(f"  NAV/Share:     ${result['nav_per_share']:,.4f}")
        print(f"  Shares:        {result['shares_transacted']:,.4f}")
        if flow_type == 'withdrawal':
            print(f"  Realized Gain: ${result['realized_gain']:,.2f} (tax settled quarterly)")
            print(f"  Disbursed:     ${result['net_proceeds']:,.2f} (full amount)")
        print(f"  New Shares:    {result['new_total_shares']:,.4f}")
        print()

        # Send confirmation email
        send_confirmation_email(dict(selected_req), result, flow_type)

        # Verify links
        print("Audit Links:")
        print(f"  fund_flow_requests.request_id = {selected_req['request_id']}")
        print(f"  fund_flow_requests.transaction_id = {result['transaction_id']}")
        print(f"  fund_flow_requests.matched_trade_id = {selected_req['matched_trade_id']}")
        print(f"  transactions.reference_id = 'ffr-{selected_req['request_id']}'")
        print()

        return True

    except sqlite3.Error as e:
        print(f"\nDatabase error: {e}")
        conn.rollback()
        return False
    except ValueError as e:
        print(f"\nValidation error: {e}")
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
        success = process_flow()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
