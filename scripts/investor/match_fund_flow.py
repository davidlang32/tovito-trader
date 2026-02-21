"""
Match Fund Flow Request to Brokerage ACH
=========================================
Shows pending/approved fund flow requests alongside recent ACH activity
from the trades table. Fund manager selects a request and an ACH trade
to match them — confirming that the money has actually moved.

Usage:
    python scripts/investor/match_fund_flow.py
    python scripts/investor/match_fund_flow.py --request-id 5
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import argparse
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

DB_PATH = PROJECT_DIR / 'data' / 'tovito.db'


def get_matchable_requests(conn, request_id=None):
    """
    Fetch fund flow requests that are ready for ACH matching.

    Statuses 'approved' and 'awaiting_funds' are eligible for matching.
    """
    query = """
        SELECT ffr.request_id, ffr.investor_id, ffr.flow_type,
               ffr.requested_amount, ffr.request_date, ffr.status,
               ffr.request_method, ffr.notes,
               i.name as investor_name
        FROM fund_flow_requests ffr
        JOIN investors i ON ffr.investor_id = i.investor_id
        WHERE ffr.status IN ('pending', 'approved', 'awaiting_funds')
    """
    params = []

    if request_id:
        query += " AND ffr.request_id = ?"
        params.append(request_id)

    query += " ORDER BY ffr.request_date"
    return conn.execute(query, params).fetchall()


def get_recent_ach_trades(conn, days=30):
    """
    Fetch recent ACH/transfer trades that could match a fund flow request.

    Looks at trades with trade_type='ach' or category='Transfer'.
    """
    cursor = conn.execute("""
        SELECT trade_id, date, trade_type, symbol, amount, source,
               description, brokerage_transaction_id, category, subcategory
        FROM trades
        WHERE (trade_type = 'ach' OR category = 'Transfer')
        AND is_deleted = 0
        AND date >= date('now', ?)
        ORDER BY date DESC
    """, (f'-{days} days',))
    return cursor.fetchall()


def get_already_matched_trade_ids(conn):
    """Get trade IDs that are already matched to a fund flow request."""
    cursor = conn.execute("""
        SELECT matched_trade_id FROM fund_flow_requests
        WHERE matched_trade_id IS NOT NULL
    """)
    return {row[0] for row in cursor.fetchall()}


def match_flow():
    """Interactive flow to match a request to a brokerage ACH."""
    parser = argparse.ArgumentParser(description="Match fund flow request to ACH")
    parser.add_argument('--request-id', type=int, help="Specific request ID to match")
    args = parser.parse_args()

    print()
    print("=" * 70)
    print("MATCH FUND FLOW REQUEST TO BROKERAGE ACH")
    print("=" * 70)
    print()

    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # Step 1: Show matchable requests
        requests = get_matchable_requests(conn, args.request_id)

        if not requests:
            if args.request_id:
                print(f"No matchable request found with ID #{args.request_id}")
            else:
                print("No fund flow requests awaiting matching.")
            print("(Eligible statuses: pending, approved, awaiting_funds)")
            return False

        print(f"MATCHABLE REQUESTS ({len(requests)}):")
        print("-" * 70)
        print(f"{'#':>4}  {'Type':>12}  {'Amount':>12}  {'Date':>12}  {'Status':>15}  {'Investor'}")
        print("-" * 70)

        for req in requests:
            print(
                f"  {req['request_id']:>2}  "
                f"{req['flow_type']:>12}  "
                f"${req['requested_amount']:>10,.2f}  "
                f"{req['request_date']:>12}  "
                f"{req['status']:>15}  "
                f"{req['investor_name']}"
            )
        print()

        # Step 2: Select a request
        if args.request_id:
            selected_req = requests[0]
        elif len(requests) == 1:
            selected_req = requests[0]
            print(f"Auto-selected request #{selected_req['request_id']}")
        else:
            req_choice = input("Select request # to match: ").strip()
            try:
                req_id = int(req_choice)
                selected_req = next((r for r in requests if r['request_id'] == req_id), None)
                if not selected_req:
                    print(f"Request #{req_id} not found in matchable list.")
                    return False
            except ValueError:
                print("Invalid input.")
                return False

        print()
        print(f"Selected: Request #{selected_req['request_id']} - "
              f"{selected_req['flow_type'].upper()} "
              f"${selected_req['requested_amount']:,.2f} "
              f"for {selected_req['investor_name']}")
        print()

        # Step 3: Show recent ACH trades
        ach_trades = get_recent_ach_trades(conn)
        matched_ids = get_already_matched_trade_ids(conn)

        # Filter out already-matched trades
        available_trades = [t for t in ach_trades if t['trade_id'] not in matched_ids]

        if not available_trades:
            print("No unmatched ACH trades found in the last 30 days.")
            print("Has the ACH appeared at the brokerage yet?")
            print()

            # Offer to set status to awaiting_funds
            if selected_req['status'] in ('pending', 'approved'):
                set_awaiting = input(
                    "Set request to 'awaiting_funds' status? (yes/no): "
                ).strip().lower()
                if set_awaiting in ('yes', 'y'):
                    now = datetime.now().isoformat()
                    conn.execute("""
                        UPDATE fund_flow_requests
                        SET status = 'awaiting_funds', updated_at = ?
                        WHERE request_id = ?
                    """, (now, selected_req['request_id']))
                    conn.commit()
                    print(f"Request #{selected_req['request_id']} status → awaiting_funds")
            return False

        print(f"RECENT ACH TRADES (unmatched, last 30 days):")
        print("-" * 70)
        print(f"{'ID':>6}  {'Date':>12}  {'Amount':>12}  {'Source':>12}  {'Description'}")
        print("-" * 70)

        for trade in available_trades:
            desc = (trade['description'] or '')[:30]
            print(
                f"  {trade['trade_id']:>4}  "
                f"{trade['date']:>12}  "
                f"${trade['amount']:>10,.2f}  "
                f"{trade['source']:>12}  "
                f"{desc}"
            )
        print()

        # Step 4: Select a trade to match
        trade_choice = input("Select trade ID to match: ").strip()
        try:
            trade_id = int(trade_choice)
            selected_trade = next(
                (t for t in available_trades if t['trade_id'] == trade_id), None
            )
            if not selected_trade:
                print(f"Trade #{trade_id} not found in available list.")
                return False
        except ValueError:
            print("Invalid input.")
            return False

        # Step 5: Validate match makes sense
        req_amount = selected_req['requested_amount']
        trade_amount = abs(selected_trade['amount'])
        diff = abs(req_amount - trade_amount)
        diff_pct = (diff / req_amount * 100) if req_amount > 0 else 0

        print()
        print("-" * 70)
        print("MATCH PREVIEW")
        print("-" * 70)
        print(f"  Request:  #{selected_req['request_id']} — "
              f"{selected_req['flow_type']} ${req_amount:,.2f}")
        print(f"  Trade:    #{selected_trade['trade_id']} — "
              f"${selected_trade['amount']:,.2f} on {selected_trade['date']}")
        if diff > 0.01:
            print(f"  Difference: ${diff:,.2f} ({diff_pct:.1f}%)")
            if diff_pct > 5:
                print("  WARNING: Large difference between requested and actual amount!")
        else:
            print(f"  Amounts match exactly")
        print("-" * 70)
        print()

        confirm = input("Confirm this match? (yes/no): ").strip().lower()
        if confirm not in ('yes', 'y'):
            print("Match cancelled.")
            return False

        # Step 6: Update fund_flow_requests with match
        now = datetime.now().isoformat()

        # Also try to find the raw_id if this trade came through ETL
        cursor = conn.execute("""
            SELECT raw_id FROM brokerage_transactions_raw
            WHERE etl_trade_id = ?
        """, (trade_id,))
        raw_row = cursor.fetchone()
        raw_id = raw_row['raw_id'] if raw_row else None

        conn.execute("""
            UPDATE fund_flow_requests
            SET status = 'matched',
                matched_trade_id = ?,
                matched_raw_id = ?,
                matched_date = ?,
                matched_by = 'admin',
                actual_amount = ?,
                updated_at = ?
            WHERE request_id = ?
        """, (
            trade_id,
            raw_id,
            now,
            abs(selected_trade['amount']),
            now,
            selected_req['request_id'],
        ))

        # Log to system_logs
        conn.execute("""
            INSERT INTO system_logs (timestamp, level, category, message, details)
            VALUES (?, 'INFO', 'Fund Flow', ?, ?)
        """, (
            now,
            f"Fund flow request #{selected_req['request_id']} matched to trade #{trade_id}",
            f"flow_type={selected_req['flow_type']}, amount=${req_amount:,.2f}, "
            f"trade_amount=${abs(selected_trade['amount']):,.2f}",
        ))

        conn.commit()

        print()
        print(f"Request #{selected_req['request_id']} matched to Trade #{trade_id}!")
        print(f"Status: MATCHED")
        print()
        print("Next step:")
        print(f"  Process shares: python scripts/investor/process_fund_flow.py "
              f"--request-id {selected_req['request_id']}")
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
        success = match_flow()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
