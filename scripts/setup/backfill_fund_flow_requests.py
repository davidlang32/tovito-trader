"""
Backfill Fund Flow Requests from Historical Transactions
=========================================================

Creates fund_flow_requests records for all historical transactions that
were processed through legacy scripts (before the fund flow workflow existed).

This ensures every transaction has a corresponding lifecycle record for
complete audit trail visibility.

Usage:
    python scripts/setup/backfill_fund_flow_requests.py --dry-run    # Preview only
    python scripts/setup/backfill_fund_flow_requests.py              # Execute backfill
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import argparse
import sqlite3
import sys
import subprocess
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

DB_PATH = PROJECT_DIR / 'data' / 'tovito.db'
BACKUP_SCRIPT = PROJECT_DIR / 'scripts' / 'utilities' / 'backup_database.py'


def get_orphan_transactions(conn):
    """
    Find transactions that have no corresponding fund_flow_requests record.

    A transaction is an 'orphan' if:
    - Its transaction_id does not appear in fund_flow_requests.transaction_id
    - No fund_flow_requests has a reference_id matching 'ffr-...' that links to it
    - Its transaction_type is Initial, Contribution, or Withdrawal
      (Tax_Payment, Fee, Adjustment are not fund flow items)
    """
    # Use COALESCE to handle both nav_per_share (new) and share_price (legacy) columns
    cursor = conn.execute("""
        SELECT t.transaction_id, t.date, t.investor_id, t.transaction_type,
               t.amount, t.shares_transacted,
               COALESCE(t.nav_per_share, t.share_price) as nav_per_share,
               t.description, t.reference_id, t.notes, t.created_at
        FROM transactions t
        WHERE t.transaction_type IN ('Initial', 'Contribution', 'Withdrawal')
          AND (t.is_deleted IS NULL OR t.is_deleted = 0)
          AND t.transaction_id NOT IN (
              SELECT COALESCE(ffr.transaction_id, -1)
              FROM fund_flow_requests ffr
              WHERE ffr.transaction_id IS NOT NULL
          )
          AND NOT EXISTS (
              SELECT 1 FROM fund_flow_requests ffr2
              WHERE ffr2.notes LIKE '%transaction #' || t.transaction_id || '%'
          )
          AND (t.reference_id IS NULL OR t.reference_id NOT LIKE 'ffr-%')
        ORDER BY t.date, t.transaction_id
    """)
    return cursor.fetchall()


def get_tax_events_for_withdrawal(conn, investor_id, transaction_date):
    """
    Look up tax events matching this withdrawal for backfill data.
    Returns the first matching tax event, or None.
    """
    cursor = conn.execute("""
        SELECT realized_gain, tax_due, net_proceeds, tax_rate
        FROM tax_events
        WHERE investor_id = ?
          AND date = ?
        ORDER BY event_id DESC
        LIMIT 1
    """, (investor_id, transaction_date))
    return cursor.fetchone()


def map_transaction_to_flow_type(transaction_type):
    """Map transaction_type to fund flow flow_type."""
    if transaction_type in ('Initial', 'Contribution'):
        return 'contribution'
    elif transaction_type == 'Withdrawal':
        return 'withdrawal'
    return None


def backfill(dry_run=False, skip_ids=None):
    """Execute the backfill process.

    Args:
        dry_run: If True, preview only without writing.
        skip_ids: List of transaction IDs to exclude from backfill.
    """
    skip_ids = skip_ids or []
    print()
    print("=" * 70)
    print("BACKFILL FUND FLOW REQUESTS FROM HISTORICAL TRANSACTIONS")
    print("=" * 70)
    print()

    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # Find orphan transactions
        orphans = get_orphan_transactions(conn)

        if not orphans:
            print("No orphan transactions found. All transactions have fund flow records.")
            return True

        print(f"Found {len(orphans)} transaction(s) without fund flow records:")
        print("-" * 70)

        backfill_records = []
        warnings_list = []

        for txn in orphans:
            txn_id = txn['transaction_id']

            if txn_id in skip_ids:
                print(f"  #{txn_id:>3}  SKIPPED (excluded via --skip)")
                continue
            txn_date = txn['date']
            investor_id = txn['investor_id']
            txn_type = txn['transaction_type']
            amount = txn['amount']
            shares = txn['shares_transacted']
            nav = txn['nav_per_share']

            flow_type = map_transaction_to_flow_type(txn_type)
            if not flow_type:
                warnings_list.append(
                    f"  SKIP #{txn_id}: Unsupported transaction_type '{txn_type}'"
                )
                continue

            # Build the backfill record
            record = {
                'investor_id': investor_id,
                'flow_type': flow_type,
                'requested_amount': abs(amount),
                'request_date': txn_date,
                'request_method': 'admin',
                'status': 'processed',
                'processed_date': txn['created_at'] or txn_date,
                'actual_amount': abs(amount),
                'shares_transacted': abs(shares) if shares else 0,
                'nav_per_share': nav,
                'transaction_id': txn_id,
                'realized_gain': None,
                'tax_withheld': 0.0,
                'net_proceeds': abs(amount),
                'notes': f"Historical backfill from transaction #{txn_id}",
            }

            # For withdrawals, try to find matching tax events
            if flow_type == 'withdrawal':
                tax_event = get_tax_events_for_withdrawal(conn, investor_id, txn_date)
                if tax_event:
                    record['realized_gain'] = tax_event['realized_gain']
                    record['tax_withheld'] = tax_event['tax_due'] or 0.0
                    net = tax_event['net_proceeds']
                    if net:
                        record['net_proceeds'] = net
                else:
                    warnings_list.append(
                        f"  WARNING #{txn_id}: Withdrawal on {txn_date} for {investor_id} "
                        f"— no matching tax_events found. Realized gain set to NULL."
                    )

            backfill_records.append(record)

            # Print preview
            type_label = txn_type.upper()
            print(f"  #{txn_id:>3}  {txn_date}  {investor_id}  {type_label:<14}"
                  f"  ${abs(amount):>10,.2f}  -> flow_type='{flow_type}'")

        print("-" * 70)
        print(f"Total to backfill: {len(backfill_records)}")

        if warnings_list:
            print()
            print("WARNINGS:")
            for w in warnings_list:
                print(w)

        if dry_run:
            print()
            print("DRY RUN — no changes made. Re-run without --dry-run to execute.")
            return True

        if not backfill_records:
            print("Nothing to backfill.")
            return True

        # Backup database before writing
        print()
        print("Backing up database before backfill...")
        if BACKUP_SCRIPT.exists():
            result = subprocess.run(
                [sys.executable, str(BACKUP_SCRIPT)],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print("  Backup completed.")
            else:
                print(f"  Backup warning: {result.stderr.strip()}")
                confirm = input("  Continue without backup? (yes/no): ").strip().lower()
                if confirm not in ('yes', 'y'):
                    print("Aborted.")
                    return False
        else:
            print(f"  Warning: Backup script not found at {BACKUP_SCRIPT}")
            confirm = input("  Continue without backup? (yes/no): ").strip().lower()
            if confirm not in ('yes', 'y'):
                print("Aborted.")
                return False

        # Execute backfill
        print()
        print("Inserting fund flow request records...")

        now = datetime.now().isoformat()
        inserted = 0

        for rec in backfill_records:
            conn.execute("""
                INSERT INTO fund_flow_requests (
                    investor_id, flow_type, requested_amount, request_date,
                    request_method, status, processed_date, actual_amount,
                    shares_transacted, nav_per_share, transaction_id,
                    realized_gain, tax_withheld, net_proceeds,
                    notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rec['investor_id'],
                rec['flow_type'],
                rec['requested_amount'],
                rec['request_date'],
                rec['request_method'],
                rec['status'],
                rec['processed_date'],
                rec['actual_amount'],
                rec['shares_transacted'],
                rec['nav_per_share'],
                rec['transaction_id'],
                rec['realized_gain'],
                rec['tax_withheld'],
                rec['net_proceeds'],
                rec['notes'],
                now, now,
            ))
            inserted += 1

        # Log the backfill operation
        conn.execute("""
            INSERT INTO system_logs (timestamp, log_type, category, message, details)
            VALUES (?, 'INFO', 'Data Migration', ?, ?)
        """, (
            now,
            f"Backfilled {inserted} fund_flow_requests from historical transactions",
            f"Transaction IDs: {[r['transaction_id'] for r in backfill_records]}",
        ))

        conn.commit()

        print(f"  Inserted {inserted} fund flow request record(s).")
        print()
        print("=" * 70)
        print("BACKFILL COMPLETE")
        print("=" * 70)

        if warnings_list:
            print()
            print("ACTION REQUIRED — Review these items:")
            for w in warnings_list:
                print(w)
            print()
            print("You may need to manually update these records with missing data.")

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
    parser = argparse.ArgumentParser(
        description="Backfill fund_flow_requests from historical transactions"
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help="Preview what would be backfilled without making changes"
    )
    parser.add_argument(
        '--skip', type=int, nargs='+', metavar='ID',
        help="Transaction IDs to exclude from backfill (e.g. --skip 1 2)"
    )
    args = parser.parse_args()

    try:
        success = backfill(dry_run=args.dry_run, skip_ids=args.skip or [])
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(1)
