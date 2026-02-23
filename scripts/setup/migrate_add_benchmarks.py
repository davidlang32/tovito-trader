"""
Database Migration - Benchmark Prices Cache

Adds a cache table for benchmark market data (SPY, QQQ, BTC-USD).
Used by the NAV vs Benchmarks comparison chart across the investor
portal, Discord pinned message, and monthly PDF reports.

Run once to add the table to your database.
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
from pathlib import Path


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def migrate():
    """Add benchmark_prices cache table"""

    db_path = get_database_path()

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return False

    print("=" * 70)
    print("DATABASE MIGRATION - BENCHMARK PRICES CACHE")
    print("=" * 70)
    print()
    print("This will add the benchmark_prices table for:")
    print("  - Caching daily close prices for SPY, QQQ, BTC-USD")
    print("  - Powering the NAV vs Benchmarks comparison chart")
    print("  - Avoiding repeated Yahoo Finance API calls")
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
            WHERE type='table' AND name = 'benchmark_prices'
        """)
        existing = cursor.fetchone()

        if existing:
            print("Warning: benchmark_prices table already exists")
            overwrite = input("Continue anyway? (yes/no): ").strip().lower()
            if overwrite not in ['yes', 'y']:
                print("Migration cancelled.")
                conn.close()
                return False
            print()

        # Create benchmark_prices table
        print("Creating benchmark_prices table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS benchmark_prices (
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                close_price REAL NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (date, ticker)
            )
        """)
        print("   benchmark_prices table created")

        # Create index
        print("Creating indexes...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_benchmark_ticker_date
            ON benchmark_prices(ticker, date)
        """)
        print("   Indexes created")

        conn.commit()

        # Verify table
        print()
        print("Verifying migration...")
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name = 'benchmark_prices'
        """)
        table = cursor.fetchone()

        if table:
            cursor.execute("SELECT COUNT(*) FROM benchmark_prices")
            count = cursor.fetchone()[0]
            print(f"   benchmark_prices: {count} rows")

        conn.close()

        print()
        print("=" * 70)
        print("MIGRATION COMPLETE!")
        print("=" * 70)
        print()
        print("New table added:")
        print("  benchmark_prices - Cache for benchmark daily close prices")
        print()
        print("Next steps:")
        print("  1. Install yfinance: pip install yfinance")
        print("  2. Populate cache: python -c \"")
        print("     from src.market_data.benchmarks import refresh_benchmark_cache")
        print("     from pathlib import Path")
        print("     refresh_benchmark_cache(Path('data/tovito.db'))\"")
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
