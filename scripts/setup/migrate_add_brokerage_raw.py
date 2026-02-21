"""
Database Migration - Brokerage Transactions Raw (ETL Staging)

Adds staging table for raw brokerage API data. Part of the ETL pipeline
that ensures consistent data normalization across all brokerage providers.

Run once to add the table to your database.
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
from pathlib import Path
from datetime import datetime


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def migrate():
    """Add brokerage_transactions_raw staging table"""

    db_path = get_database_path()

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return False

    print("=" * 70)
    print("DATABASE MIGRATION - BROKERAGE TRANSACTIONS RAW (ETL STAGING)")
    print("=" * 70)
    print()
    print("This will add the brokerage_transactions_raw table for:")
    print("  - Storing raw brokerage API responses (JSON)")
    print("  - ETL staging before normalization into trades table")
    print("  - Full audit trail of original brokerage data")
    print("  - Deduplication via (source, brokerage_transaction_id)")
    print()

    confirm = input("Proceed with migration? (yes/no): ").strip().lower()

    if confirm not in ['yes', 'y']:
        print("Migration cancelled.")
        return False

    print()
    print("Running migration...")
    print()

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name = 'brokerage_transactions_raw'
        """)
        existing = cursor.fetchone()

        if existing:
            print("Warning: brokerage_transactions_raw table already exists")
            overwrite = input("Continue anyway? (yes/no): ").strip().lower()
            if overwrite not in ['yes', 'y']:
                print("Migration cancelled.")
                conn.close()
                return False
            print()

        # Create brokerage_transactions_raw table
        print("Creating brokerage_transactions_raw table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS brokerage_transactions_raw (
                raw_id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Source tracking
                source TEXT NOT NULL,
                brokerage_transaction_id TEXT NOT NULL,

                -- Raw data (JSON blob preserving everything the API returned)
                raw_data TEXT NOT NULL,

                -- Extracted key fields (for querying without parsing JSON)
                transaction_date DATE NOT NULL,
                transaction_type TEXT NOT NULL,
                transaction_subtype TEXT,
                symbol TEXT,
                amount REAL,
                description TEXT,

                -- ETL tracking
                etl_status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (etl_status IN ('pending', 'transformed', 'skipped', 'error')),
                etl_transformed_at TIMESTAMP,
                etl_trade_id INTEGER,
                etl_error TEXT,

                -- Metadata
                ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

                -- Deduplication
                UNIQUE(source, brokerage_transaction_id)
            )
        """)
        print("   brokerage_transactions_raw table created")

        # Create indexes
        print("Creating indexes...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_raw_txn_source_brokerage_id
            ON brokerage_transactions_raw(source, brokerage_transaction_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_raw_txn_etl_status
            ON brokerage_transactions_raw(etl_status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_raw_txn_date
            ON brokerage_transactions_raw(transaction_date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_raw_txn_source_date
            ON brokerage_transactions_raw(source, transaction_date)
        """)
        print("   Indexes created")

        conn.commit()

        # Verify table
        print()
        print("Verifying migration...")
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name = 'brokerage_transactions_raw'
        """)
        table = cursor.fetchone()

        if table:
            cursor.execute("SELECT COUNT(*) FROM brokerage_transactions_raw")
            count = cursor.fetchone()[0]
            print(f"   brokerage_transactions_raw: {count} rows")

        conn.close()

        print()
        print("=" * 70)
        print("MIGRATION COMPLETE!")
        print("=" * 70)
        print()
        print("New table added:")
        print("  brokerage_transactions_raw - ETL staging for raw brokerage data")
        print()
        print("ETL Status Values:")
        print("  pending     - Ingested, awaiting transform")
        print("  transformed - Successfully normalized into trades table")
        print("  skipped     - Intentionally skipped (e.g., duplicate)")
        print("  error       - Transform failed (see etl_error column)")
        print()
        print("Next steps:")
        print("  1. Run ETL: python scripts/trading/run_etl.py --days 30")
        print("  2. Verify:  SELECT COUNT(*) FROM brokerage_transactions_raw")
        print()

        return True

    except sqlite3.Error as e:
        print(f"\nDatabase error: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = migrate()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
