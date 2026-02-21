"""
Unified Trade Sync — Pull from ALL Configured Brokerages

Fetches recent trade history from each configured brokerage provider
and inserts new transactions with source tagging.

Usage:
    python scripts/trading/sync_all_trades.py                     # Last 7 days
    python scripts/trading/sync_all_trades.py --days 30           # Last 30 days
    python scripts/trading/sync_all_trades.py --provider tradier  # Single provider
    python scripts/trading/sync_all_trades.py --check             # Preview only
"""

import sys
import os
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv
load_dotenv(PROJECT_DIR / ".env")


def get_database_path():
    """Get database path."""
    return PROJECT_DIR / 'data' / 'tovito.db'


def get_existing_ids(cursor, source):
    """Get existing brokerage_transaction_ids for a source."""
    cursor.execute(
        "SELECT brokerage_transaction_id FROM trades WHERE source = ? AND brokerage_transaction_id IS NOT NULL",
        (source,)
    )
    return set(row[0] for row in cursor.fetchall())


def insert_trade(cursor, txn, source):
    """Insert a single trade record."""
    brokerage_id = txn.get('brokerage_transaction_id', '')

    cursor.execute("""
        INSERT INTO trades (
            brokerage_transaction_id, source, date, type, trade_type,
            amount, commission, symbol, quantity, price,
            option_type, strike, expiration_date,
            description, notes, category, subcategory
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)
    """, (
        brokerage_id or None,
        source,
        txn['date'],
        txn['transaction_type'],
        txn['transaction_type'],
        txn['amount'],
        txn['commission'] + txn.get('fees', 0),
        txn['symbol'],
        txn['quantity'],
        txn['price'],
        txn.get('option_type'),
        txn.get('strike'),
        txn.get('expiration_date'),
        txn['description'],
        txn['category'],
        txn['subcategory'],
    ))


def sync_provider(client, source, cursor, existing_ids, start_date, end_date, check_only):
    """Sync trades from a single provider."""
    print(f"\n  Fetching from {source}...")

    try:
        transactions = client.get_transactions(start_date, end_date)
        print(f"  [OK] {len(transactions)} transactions from API")
    except Exception as e:
        print(f"  [FAIL] API error: {e}")
        return 0, 0, 1

    imported = 0
    skipped = 0

    for txn in transactions:
        brokerage_id = txn.get('brokerage_transaction_id', '')

        if brokerage_id and brokerage_id in existing_ids:
            skipped += 1
            continue

        if check_only:
            imported += 1
            continue

        try:
            insert_trade(cursor, txn, source)
            imported += 1
        except sqlite3.IntegrityError:
            skipped += 1

    return imported, skipped, 0


def main():
    parser = argparse.ArgumentParser(description='Sync trades from all brokerages')
    parser.add_argument('--days', type=int, default=7, help='Days of history (default: 7)')
    parser.add_argument('--provider', type=str, help='Sync only this provider')
    parser.add_argument('--check', action='store_true', help='Preview only')
    args = parser.parse_args()

    print("=" * 60)
    print("Unified Trade Sync")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    start_date = datetime.now() - timedelta(days=args.days)
    end_date = datetime.now()
    print(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    from src.api.brokerage import get_configured_providers, get_brokerage_client

    providers = get_configured_providers()
    if args.provider:
        providers = [args.provider]

    print(f"Providers: {', '.join(providers)}")

    db_path = get_database_path()
    conn = sqlite3.connect(str(db_path), timeout=10)
    cursor = conn.cursor()

    total_imported = 0
    total_skipped = 0
    total_errors = 0

    try:
        for source in providers:
            try:
                client = get_brokerage_client(source)
            except Exception as e:
                print(f"\n  [FAIL] Could not initialize {source}: {e}")
                total_errors += 1
                continue

            existing_ids = get_existing_ids(cursor, source)
            print(f"\n  Existing {source} trades in DB: {len(existing_ids)}")

            imported, skipped, errors = sync_provider(
                client, source, cursor, existing_ids,
                start_date, end_date, args.check
            )

            total_imported += imported
            total_skipped += skipped
            total_errors += errors

            print(f"  New: {imported}, Skipped: {skipped}")

        if not args.check:
            conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"\n[FAIL] Sync failed: {e}")
        sys.exit(1)

    finally:
        conn.close()

    # Summary
    print()
    print("=" * 60)
    mode = "PREVIEW" if args.check else "SYNC COMPLETE"
    print(f"{mode}")
    print(f"  New trades:     {total_imported}")
    print(f"  Skipped (dups): {total_skipped}")
    if total_errors:
        print(f"  Errors:         {total_errors}")
    print("=" * 60)


if __name__ == '__main__':
    main()
