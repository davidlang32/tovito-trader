"""
Database Migration: Add Holdings Snapshots & Source Tracking
=============================================================
Schema version: 2.0.0 → 2.1.0

Changes:
  1. Add 'source' column to trades table (defaults existing rows to 'tradier')
  2. Add 'brokerage_transaction_id' column to trades table (backfills from tradier_transaction_id)
  3. Create 'holdings_snapshots' table for daily position tracking
  4. Create 'position_snapshots' table for per-position detail
  5. Add indexes for new columns

Usage:
    python scripts/setup/migrate_add_holdings_and_source.py
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))


def get_database_path():
    """Get database path."""
    return PROJECT_DIR / 'data' / 'tovito.db'


def check_column_exists(cursor, table, column):
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def check_table_exists(cursor, table):
    """Check if a table exists."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    return cursor.fetchone() is not None


def migrate(db_path):
    """Run the migration."""
    print("=" * 60)
    print("Migration: Add Holdings Snapshots & Source Tracking")
    print(f"Database: {db_path}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        return False

    conn = sqlite3.connect(str(db_path), timeout=10)
    cursor = conn.cursor()

    changes_made = 0

    try:
        # ---- 1. Add 'source' column to trades ----
        print("Step 1: Adding 'source' column to trades table...")

        if check_column_exists(cursor, 'trades', 'source'):
            print("  [SKIP] Column 'source' already exists")
        else:
            cursor.execute(
                "ALTER TABLE trades ADD COLUMN source TEXT DEFAULT 'tradier'"
            )
            # Backfill: all existing trades came from Tradier
            cursor.execute(
                "UPDATE trades SET source = 'tradier' WHERE source IS NULL"
            )
            count = cursor.rowcount
            print(f"  [OK] Added 'source' column, backfilled {count} rows as 'tradier'")
            changes_made += 1

        # ---- 2. Add 'brokerage_transaction_id' column to trades ----
        print("Step 2: Adding 'brokerage_transaction_id' column to trades table...")

        if check_column_exists(cursor, 'trades', 'brokerage_transaction_id'):
            print("  [SKIP] Column 'brokerage_transaction_id' already exists")
        else:
            cursor.execute(
                "ALTER TABLE trades ADD COLUMN brokerage_transaction_id TEXT"
            )
            # Backfill from tradier_transaction_id
            cursor.execute("""
                UPDATE trades
                SET brokerage_transaction_id = tradier_transaction_id
                WHERE tradier_transaction_id IS NOT NULL
                  AND brokerage_transaction_id IS NULL
            """)
            count = cursor.rowcount
            print(f"  [OK] Added 'brokerage_transaction_id', backfilled {count} rows")
            changes_made += 1

        # ---- 3. Add indexes on new columns ----
        print("Step 3: Adding indexes...")

        indexes = [
            ("idx_trades_source", "CREATE INDEX IF NOT EXISTS idx_trades_source ON trades(source)"),
            ("idx_trades_date_source", "CREATE INDEX IF NOT EXISTS idx_trades_date_source ON trades(date, source)"),
        ]

        for idx_name, idx_sql in indexes:
            try:
                cursor.execute(idx_sql)
                print(f"  [OK] Index '{idx_name}' created")
                changes_made += 1
            except sqlite3.OperationalError as e:
                if "already exists" in str(e):
                    print(f"  [SKIP] Index '{idx_name}' already exists")
                else:
                    raise

        # ---- 4. Create holdings_snapshots table ----
        print("Step 4: Creating 'holdings_snapshots' table...")

        if check_table_exists(cursor, 'holdings_snapshots'):
            print("  [SKIP] Table 'holdings_snapshots' already exists")
        else:
            cursor.execute("""
                CREATE TABLE holdings_snapshots (
                    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    source TEXT NOT NULL,
                    snapshot_time TIMESTAMP NOT NULL,
                    total_positions INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, source)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_holdings_snapshots_date
                ON holdings_snapshots(date)
            """)
            print("  [OK] Table 'holdings_snapshots' created")
            changes_made += 1

        # ---- 5. Create position_snapshots table ----
        print("Step 5: Creating 'position_snapshots' table...")

        if check_table_exists(cursor, 'position_snapshots'):
            print("  [SKIP] Table 'position_snapshots' already exists")
        else:
            cursor.execute("""
                CREATE TABLE position_snapshots (
                    position_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    underlying_symbol TEXT,
                    quantity REAL NOT NULL,
                    instrument_type TEXT,
                    average_open_price REAL,
                    close_price REAL,
                    market_value REAL,
                    cost_basis REAL,
                    unrealized_pl REAL,
                    option_type TEXT,
                    strike REAL,
                    expiration_date DATE,
                    multiplier INTEGER,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (snapshot_id) REFERENCES holdings_snapshots(snapshot_id)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_position_snapshots_snapshot
                ON position_snapshots(snapshot_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_position_snapshots_symbol
                ON position_snapshots(symbol)
            """)
            print("  [OK] Table 'position_snapshots' created")
            changes_made += 1

        # ---- 6. Update schema version ----
        print("Step 6: Updating schema version...")

        try:
            cursor.execute("""
                UPDATE system_config
                SET value = '2.1.0', updated_at = CURRENT_TIMESTAMP
                WHERE key = 'schema_version'
            """)
            if cursor.rowcount > 0:
                print("  [OK] Schema version updated to 2.1.0")
            else:
                print("  [SKIP] No schema_version row found in system_config")
        except sqlite3.OperationalError:
            print("  [SKIP] system_config table not found")

        # ---- Commit ----
        conn.commit()

        print()
        print("=" * 60)
        if changes_made > 0:
            print(f"MIGRATION COMPLETE: {changes_made} change(s) applied")
        else:
            print("MIGRATION COMPLETE: No changes needed (already up to date)")
        print("=" * 60)

        return True

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: Migration failed: {e}")
        print("All changes have been rolled back.")
        return False

    finally:
        conn.close()


def main():
    """Entry point with confirmation prompt."""
    db_path = get_database_path()

    print()
    print(f"This will migrate: {db_path}")
    print()
    print("Changes:")
    print("  1. Add 'source' column to trades table")
    print("  2. Add 'brokerage_transaction_id' column to trades table")
    print("  3. Create 'holdings_snapshots' table")
    print("  4. Create 'position_snapshots' table")
    print()

    # Remind about backup
    print("IMPORTANT: Back up the database before running this migration!")
    print("  python scripts/utilities/backup_database.py")
    print()

    response = input("Proceed with migration? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Migration cancelled.")
        return

    print()
    success = migrate(db_path)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
