#!/usr/bin/env python3
"""
Migration: Clean Up Trades Table
=================================

This migration performs three cleanup operations:

1. REVERSE PRE-TOVITO TASTYTRADE TRANSACTIONS
   TastyTrade transactions before 12/29/2025 pre-date Tovito Trader's
   use of the account. These are zeroed out via reversing entries
   (per CLAUDE.md -- never delete records).

2. NORMALIZE DATE FORMATS
   Some Tradier-imported trades have dates stored as 'YYYY-MM-DDT00:00:00Z'
   instead of 'YYYY-MM-DD'. This normalizes all dates to plain YYYY-MM-DD.

3. REMOVE REDUNDANT tradier_transaction_id COLUMN
   The brokerage_transaction_id column replaces tradier_transaction_id.
   Since SQLite doesn't support DROP COLUMN on older versions, this
   recreates the table without the legacy column.

Usage:
    python scripts/setup/migrate_cleanup_trades.py --check    # Preview changes
    python scripts/setup/migrate_cleanup_trades.py --execute   # Apply changes
"""

import sys
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

CUTOFF_DATE = '2025-12-29'  # Tovito Trader started using TastyTrade account


def get_database_path():
    """Get production database path."""
    return PROJECT_DIR / 'data' / 'tovito.db'


def backup_database():
    """Create a backup before making changes."""
    import shutil
    db_path = get_database_path()
    backup_dir = PROJECT_DIR / 'data' / 'backups'
    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = backup_dir / f'tovito_pre_cleanup_{timestamp}.db'
    shutil.copy2(db_path, backup_path)
    print(f"[BACKUP] Created: {backup_path}")
    return backup_path


def check_pre_tovito_trades(cursor):
    """Find TastyTrade transactions before the cutoff date."""
    cursor.execute("""
        SELECT trade_id, date, trade_type, amount, symbol, description,
               brokerage_transaction_id
        FROM trades
        WHERE source = 'tastytrade'
          AND date < ?
        ORDER BY date
    """, (CUTOFF_DATE,))
    return cursor.fetchall()


def check_date_format_issues(cursor):
    """Find trades with timestamp suffixes in the date field."""
    cursor.execute("""
        SELECT trade_id, date, source
        FROM trades
        WHERE date LIKE '%T%'
        ORDER BY date
    """)
    return cursor.fetchall()


def check_tradier_transaction_id_column(cursor):
    """Check if the legacy column exists and its state."""
    cursor.execute("PRAGMA table_info(trades)")
    columns = {row[1]: row for row in cursor.fetchall()}
    has_legacy = 'tradier_transaction_id' in columns
    has_new = 'brokerage_transaction_id' in columns

    if has_legacy:
        cursor.execute("""
            SELECT COUNT(*) FROM trades
            WHERE tradier_transaction_id IS NOT NULL
        """)
        legacy_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM trades
            WHERE brokerage_transaction_id IS NOT NULL
        """)
        new_count = cursor.fetchone()[0]

        # Check if they match (migration should have copied values)
        cursor.execute("""
            SELECT COUNT(*) FROM trades
            WHERE tradier_transaction_id IS NOT NULL
              AND brokerage_transaction_id IS NOT NULL
              AND tradier_transaction_id = brokerage_transaction_id
        """)
        match_count = cursor.fetchone()[0]

        return {
            'has_legacy': True,
            'has_new': has_new,
            'legacy_count': legacy_count,
            'new_count': new_count,
            'match_count': match_count,
        }

    return {'has_legacy': False, 'has_new': has_new}


def run_check(db_path):
    """Preview all changes without modifying anything."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("=" * 60)
    print("TRADES TABLE CLEANUP -- Preview")
    print("=" * 60)
    print()

    # 1. Pre-Tovito trades
    pre_tovito = check_pre_tovito_trades(cursor)
    print(f"1. PRE-TOVITO TASTYTRADE TRANSACTIONS (before {CUTOFF_DATE})")
    print("-" * 50)
    if pre_tovito:
        print(f"   Found {len(pre_tovito)} transactions to reverse:")
        for row in pre_tovito:
            tid, date, ttype, amount, symbol, desc, brok_id = row
            print(f"   ID {tid}: {date} | {ttype or 'N/A'} | ${amount:,.4f} | {symbol or 'N/A'} | {desc or 'N/A'}")
        total_amount = sum(r[3] for r in pre_tovito)
        print(f"   Total amount to reverse: ${total_amount:,.4f}")
    else:
        print("   No pre-Tovito TastyTrade transactions found. [OK]")
    print()

    # 2. Date format issues
    date_issues = check_date_format_issues(cursor)
    print("2. DATE FORMAT NORMALIZATION (T00:00:00Z -> YYYY-MM-DD)")
    print("-" * 50)
    if date_issues:
        print(f"   Found {len(date_issues)} trades with timestamp in date field:")
        for row in date_issues[:5]:
            print(f"   ID {row[0]}: '{row[1]}' -> '{row[1][:10]}' (source: {row[2]})")
        if len(date_issues) > 5:
            print(f"   ... and {len(date_issues) - 5} more")
    else:
        print("   All dates are clean YYYY-MM-DD format. [OK]")
    print()

    # 3. Column removal
    col_info = check_tradier_transaction_id_column(cursor)
    print("3. TRADIER_TRANSACTION_ID COLUMN REMOVAL")
    print("-" * 50)
    if col_info['has_legacy']:
        print(f"   Legacy column exists: {col_info['legacy_count']} rows with data")
        print(f"   New column has: {col_info['new_count']} rows with data")
        print(f"   Matching values: {col_info['match_count']}")
        if col_info['legacy_count'] == col_info['match_count']:
            print("   All legacy values are backed up in brokerage_transaction_id. [OK]")
        else:
            unmatched = col_info['legacy_count'] - col_info['match_count']
            print(f"   [WARN]  {unmatched} legacy values NOT in brokerage_transaction_id!")
            print("       These will be copied before column removal.")
    else:
        print("   Legacy column already removed. [OK]")
    print()

    conn.close()
    print("Run with --execute to apply these changes.")


def execute_migration(db_path):
    """Apply all cleanup changes."""
    # Step 0: Backup
    backup_path = backup_database()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print()
    print("=" * 60)
    print("TRADES TABLE CLEANUP -- Executing")
    print("=" * 60)
    print()

    try:
        # =============================================
        # STEP 1: Reverse pre-Tovito TastyTrade trades
        # =============================================
        print("Step 1: Reversing pre-Tovito TastyTrade transactions...")
        pre_tovito = check_pre_tovito_trades(cursor)

        if pre_tovito:
            reversed_count = 0
            for row in pre_tovito:
                tid, date, ttype, amount, symbol, desc, brok_id = row

                # Insert reversing entry with negated amount
                cursor.execute("""
                    INSERT INTO trades (
                        date, type, trade_type, amount, commission, symbol,
                        description, notes, category, subcategory, source,
                        brokerage_transaction_id
                    ) VALUES (
                        ?, ?, ?, ?, 0, ?,
                        ?, ?, 'Adjustment', 'Reversal', 'tastytrade', ?
                    )
                """, (
                    date[:10],  # Normalize date too
                    ttype or 'other',
                    ttype or 'other',
                    -amount,  # Negate the original amount
                    symbol,
                    f"REVERSAL of trade #{tid}: {desc or 'N/A'}",
                    f"Pre-Tovito Trader transaction (before {CUTOFF_DATE}). "
                    f"This account activity predates Tovito Trader's use of the "
                    f"TastyTrade account. Zeroed out to maintain accurate fund records.",
                    f"reversal_of_{brok_id}" if brok_id else None,
                ))
                reversed_count += 1
                print(f"   Reversed trade #{tid}: ${amount:,.4f} -> ${-amount:,.4f}")

            print(f"   [OK] {reversed_count} reversing entries created")
        else:
            print("   No pre-Tovito transactions to reverse. [OK]")
        print()

        # =============================================
        # STEP 2: Normalize date formats
        # =============================================
        print("Step 2: Normalizing date formats...")
        date_issues = check_date_format_issues(cursor)

        if date_issues:
            for row in date_issues:
                tid, old_date, source = row
                new_date = old_date[:10]  # Strip T00:00:00Z
                cursor.execute(
                    "UPDATE trades SET date = ?, updated_at = CURRENT_TIMESTAMP WHERE trade_id = ?",
                    (new_date, tid)
                )

            # Also normalize expiration_date if it has timestamps
            cursor.execute("""
                UPDATE trades
                SET expiration_date = SUBSTR(expiration_date, 1, 10),
                    updated_at = CURRENT_TIMESTAMP
                WHERE expiration_date LIKE '%T%'
            """)

            print(f"   [OK] {len(date_issues)} trade dates normalized to YYYY-MM-DD")
        else:
            print("   All dates already clean. [OK]")
        print()

        # =============================================
        # STEP 3: Remove tradier_transaction_id column
        # =============================================
        print("Step 3: Removing legacy tradier_transaction_id column...")
        col_info = check_tradier_transaction_id_column(cursor)

        if col_info['has_legacy']:
            # First, ensure all legacy IDs are in brokerage_transaction_id
            cursor.execute("""
                UPDATE trades
                SET brokerage_transaction_id = tradier_transaction_id
                WHERE tradier_transaction_id IS NOT NULL
                  AND (brokerage_transaction_id IS NULL
                       OR brokerage_transaction_id = '')
            """)
            copied = cursor.rowcount
            if copied > 0:
                print(f"   Copied {copied} IDs from legacy to brokerage_transaction_id")

            # The original table has UNIQUE(tradier_transaction_id) constraint,
            # which prevents ALTER TABLE DROP COLUMN even on SQLite 3.35+.
            # Must recreate the table without the column and constraint.
            print(f"   SQLite version: {sqlite3.sqlite_version}")
            print("   Recreating table without legacy column and UNIQUE constraint...")

            # Get current column list (minus tradier_transaction_id)
            cursor.execute("PRAGMA table_info(trades)")
            all_cols = cursor.fetchall()
            keep_cols = [c[1] for c in all_cols if c[1] != 'tradier_transaction_id']
            cols_str = ', '.join(keep_cols)

            # Copy data to temp table
            cursor.execute(f"CREATE TABLE trades_new AS SELECT {cols_str} FROM trades")

            # Drop old table (removes the UNIQUE constraint too)
            cursor.execute("DROP TABLE trades")

            # Recreate with clean schema (no tradier_transaction_id, no legacy UNIQUE)
            cursor.execute("""
                CREATE TABLE trades (
                    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    type TEXT NOT NULL,
                    status TEXT,
                    amount REAL NOT NULL,
                    commission REAL DEFAULT 0,
                    symbol TEXT,
                    quantity REAL,
                    price REAL,
                    option_type TEXT,
                    strike REAL,
                    expiration_date DATE,
                    trade_type TEXT,
                    description TEXT,
                    notes TEXT,
                    category TEXT,
                    subcategory TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source TEXT DEFAULT 'tradier',
                    brokerage_transaction_id TEXT
                )
            """)

            # Copy data back
            cursor.execute(f"""
                INSERT INTO trades ({cols_str})
                SELECT {cols_str} FROM trades_new
            """)
            cursor.execute("DROP TABLE trades_new")

            # Recreate indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_type ON trades(trade_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_source ON trades(source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_date_source ON trades(date, source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_brokerage_id ON trades(brokerage_transaction_id)")

            print("   [OK] Table recreated without tradier_transaction_id column")

            # Also remove the legacy index if it exists
            cursor.execute("DROP INDEX IF EXISTS idx_trades_tradier_id")
            print("   [OK] Legacy index removed")
        else:
            print("   Legacy column already removed. [OK]")
        print()

        # Commit all changes
        conn.commit()
        print("=" * 60)
        print("[OK] ALL CLEANUP COMPLETE")
        print("=" * 60)

        # Verify
        cursor.execute("SELECT COUNT(*) FROM trades")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT source, COUNT(*) FROM trades GROUP BY source")
        by_source = cursor.fetchall()
        cursor.execute("PRAGMA table_info(trades)")
        cols = [row[1] for row in cursor.fetchall()]

        print(f"\nPost-cleanup stats:")
        print(f"  Total trades: {total}")
        for source, count in by_source:
            print(f"    {source}: {count}")
        print(f"  Columns: {len(cols)}")
        print(f"  tradier_transaction_id present: {'tradier_transaction_id' in cols}")
        print(f"\nBackup saved at: {backup_path}")

    except Exception as e:
        conn.rollback()
        print(f"\n[FAIL] MIGRATION FAILED: {e}")
        print(f"No changes were made. Backup is at: {backup_path}")
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Clean up trades table')
    parser.add_argument('--check', action='store_true', help='Preview changes')
    parser.add_argument('--execute', action='store_true', help='Apply changes')
    args = parser.parse_args()

    if not args.check and not args.execute:
        parser.print_help()
        print("\nSpecify --check (preview) or --execute (apply changes)")
        return

    db_path = get_database_path()

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    if args.check:
        run_check(db_path)
    elif args.execute:
        execute_migration(db_path)


if __name__ == '__main__':
    main()
