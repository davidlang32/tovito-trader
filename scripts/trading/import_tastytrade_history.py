"""
Import TastyTrade Transaction History to Trades Table

Fetches trade history from TastyTrade API and imports into the
unified trades table with source='tastytrade'.

Usage:
    python scripts/trading/import_tastytrade_history.py --check      # Preview
    python scripts/trading/import_tastytrade_history.py --import      # Import
    python scripts/trading/import_tastytrade_history.py --import --days 90
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


def get_existing_trade_ids(cursor, source='tastytrade'):
    """Get existing brokerage_transaction_ids for a source."""
    cursor.execute(
        "SELECT brokerage_transaction_id FROM trades WHERE source = ? AND brokerage_transaction_id IS NOT NULL",
        (source,)
    )
    return set(row[0] for row in cursor.fetchall())


def import_transactions(cursor, transactions, existing_ids):
    """Import new transactions to database."""
    imported = 0
    skipped = 0

    for txn in transactions:
        brokerage_id = txn.get('brokerage_transaction_id', '')

        # Skip if already exists
        if brokerage_id and brokerage_id in existing_ids:
            skipped += 1
            continue

        try:
            cursor.execute("""
                INSERT INTO trades (
                    brokerage_transaction_id, source, date, type, trade_type,
                    amount, commission, symbol, quantity, price,
                    option_type, strike, expiration_date,
                    description, notes, category, subcategory
                ) VALUES (?, 'tastytrade', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)
            """, (
                brokerage_id or None,
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
            imported += 1

        except sqlite3.IntegrityError:
            skipped += 1

    return imported, skipped


def main():
    parser = argparse.ArgumentParser(description='Import TastyTrade trade history')
    parser.add_argument('--check', action='store_true', help='Preview without importing')
    parser.add_argument('--import', dest='do_import', action='store_true', help='Import to database')
    parser.add_argument('--days', type=int, default=365, help='Days of history (default: 365)')
    args = parser.parse_args()

    if not args.check and not args.do_import:
        parser.print_help()
        print("\nSpecify --check (preview) or --import (execute)")
        return

    print("=" * 60)
    print("TastyTrade Trade History Import")
    print("=" * 60)
    print()

    # Fetch from API
    try:
        from src.api.tastytrade_client import TastyTradeClient
        client = TastyTradeClient()
        print("[OK] TastyTrade client initialized")
    except Exception as e:
        print(f"[FAIL] Could not initialize TastyTrade client: {e}")
        sys.exit(1)

    start_date = datetime.now() - timedelta(days=args.days)
    end_date = datetime.now()

    print(f"Fetching {args.days} days of history...")
    print(f"  Start: {start_date.strftime('%Y-%m-%d')}")
    print(f"  End:   {end_date.strftime('%Y-%m-%d')}")
    print()

    try:
        transactions = client.get_transactions(start_date, end_date)
        print(f"[OK] Found {len(transactions)} transactions from TastyTrade")
    except Exception as e:
        print(f"[FAIL] API error: {e}")
        sys.exit(1)

    if not transactions:
        print("No transactions to import.")
        return

    # Show summary
    categories = {}
    for txn in transactions:
        cat = txn.get('category', 'Unknown')
        categories[cat] = categories.get(cat, 0) + 1

    print()
    print("Transaction breakdown:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
    print()

    if args.check:
        print("Preview mode — no changes made.")
        print("Run with --import to import these transactions.")
        return

    # Import
    db_path = get_database_path()
    conn = sqlite3.connect(str(db_path), timeout=10)
    cursor = conn.cursor()

    try:
        existing_ids = get_existing_trade_ids(cursor, 'tastytrade')
        print(f"Existing TastyTrade trades in DB: {len(existing_ids)}")

        imported, skipped = import_transactions(cursor, transactions, existing_ids)
        conn.commit()

        print()
        print("=" * 60)
        print(f"IMPORT COMPLETE")
        print(f"  New trades imported: {imported}")
        print(f"  Duplicates skipped:  {skipped}")
        print("=" * 60)

    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Import failed: {e}")
        sys.exit(1)

    finally:
        conn.close()


if __name__ == '__main__':
    main()
