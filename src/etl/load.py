"""
ETL Load Layer
==============
Takes normalized transaction dicts from the transform step and
inserts them into the production trades table. Updates the staging
table's etl_status to reflect the outcome.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

PROJECT_DIR = Path("C:/tovito-trader")
DB_PATH = PROJECT_DIR / "data" / "tovito.db"


def _ensure_trades_schema(cursor):
    """
    Ensure the trades table has columns required by the ETL pipeline.

    The production database may have been created with an older schema
    missing 'fees' and 'is_deleted'. This adds them if absent, with
    safe defaults that don't affect existing data.
    """
    cursor.execute("PRAGMA table_info(trades)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    if 'fees' not in existing_cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN fees REAL DEFAULT 0")
        logger.info("Added missing 'fees' column to trades table")

    if 'is_deleted' not in existing_cols:
        cursor.execute(
            "ALTER TABLE trades ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0"
        )
        logger.info("Added missing 'is_deleted' column to trades table")


def load_to_trades(
    transformed: List[Tuple[int, Dict]],
    errors: List[Tuple[int, str]] = None,
    skipped: List[int] = None,
    db_path: Path = None,
) -> Dict:
    """
    Insert normalized rows into the production trades table and update
    staging table ETL status.

    Args:
        transformed: List of (raw_id, normalized_dict) tuples from transform step
        errors: List of (raw_id, error_message) tuples from transform step
        skipped: List of raw_ids that were skipped during transform
        db_path: Override database path (for testing)

    Returns:
        dict with: 'loaded': int, 'duplicates': int, 'load_errors': int
    """
    if db_path is None:
        db_path = DB_PATH

    if errors is None:
        errors = []
    if skipped is None:
        skipped = []

    result = {'loaded': 0, 'duplicates': 0, 'load_errors': 0}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure production trades table has all required columns
    _ensure_trades_schema(cursor)

    try:
        # First, mark transform errors in staging table
        for raw_id, error_msg in errors:
            cursor.execute("""
                UPDATE brokerage_transactions_raw
                SET etl_status = 'error',
                    etl_error = ?,
                    etl_transformed_at = ?
                WHERE raw_id = ?
            """, (error_msg, datetime.now().isoformat(), raw_id))

        # Mark skipped rows
        for raw_id in skipped:
            cursor.execute("""
                UPDATE brokerage_transactions_raw
                SET etl_status = 'skipped',
                    etl_transformed_at = ?
                WHERE raw_id = ?
            """, (datetime.now().isoformat(), raw_id))

        # Insert transformed rows into production trades table
        for raw_id, row in transformed:
            try:
                # Check if this brokerage_transaction_id already exists in trades
                cursor.execute("""
                    SELECT trade_id FROM trades
                    WHERE source = ? AND brokerage_transaction_id = ?
                    AND is_deleted = 0
                """, (row['source'], row['brokerage_transaction_id']))

                existing = cursor.fetchone()

                # Fallback dedup for Tradier: synthetic IDs vary by index between
                # runs, so also check by date + amount to catch logical duplicates
                # from the original import script.
                if not existing and row.get('brokerage_transaction_id', '').startswith('GENERATED_'):
                    cursor.execute("""
                        SELECT trade_id FROM trades
                        WHERE source = ? AND date = ? AND amount = ?
                        AND is_deleted = 0
                    """, (row['source'], row['date'], row['amount']))
                    existing = cursor.fetchone()

                if existing:
                    # Already in production — mark as transformed, link to existing
                    cursor.execute("""
                        UPDATE brokerage_transactions_raw
                        SET etl_status = 'transformed',
                            etl_trade_id = ?,
                            etl_transformed_at = ?
                        WHERE raw_id = ?
                    """, (existing[0], datetime.now().isoformat(), raw_id))
                    result['duplicates'] += 1
                    continue

                # Insert into trades
                cursor.execute("""
                    INSERT INTO trades (
                        date, type, trade_type, symbol, quantity, price, amount,
                        option_type, strike, expiration_date,
                        commission, fees,
                        category, subcategory,
                        description, notes,
                        source, brokerage_transaction_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['date'],
                    row['type'],
                    row['trade_type'],
                    row['symbol'] or None,
                    row['quantity'],
                    row['price'],
                    row['amount'],
                    row['option_type'],
                    row['strike'],
                    row['expiration_date'],
                    row['commission'],
                    row['fees'],
                    row['category'],
                    row['subcategory'],
                    row['description'],
                    row['notes'],
                    row['source'],
                    row['brokerage_transaction_id'],
                ))

                trade_id = cursor.lastrowid

                # Update staging row with success
                cursor.execute("""
                    UPDATE brokerage_transactions_raw
                    SET etl_status = 'transformed',
                        etl_trade_id = ?,
                        etl_transformed_at = ?
                    WHERE raw_id = ?
                """, (trade_id, datetime.now().isoformat(), raw_id))

                result['loaded'] += 1

            except sqlite3.Error as e:
                logger.error(
                    "Failed to load raw_id=%d into trades: %s", raw_id, e
                )
                # Mark as error in staging
                cursor.execute("""
                    UPDATE brokerage_transactions_raw
                    SET etl_status = 'error',
                        etl_error = ?,
                        etl_transformed_at = ?
                    WHERE raw_id = ?
                """, (f"Load error: {e}", datetime.now().isoformat(), raw_id))
                result['load_errors'] += 1

        conn.commit()

    except Exception as e:
        logger.error("Load failed: %s", e)
        conn.rollback()
        raise
    finally:
        conn.close()

    logger.info(
        "Load complete: %d loaded, %d duplicates, %d errors",
        result['loaded'], result['duplicates'], result['load_errors']
    )
    return result


def run_full_pipeline(
    source: str = None,
    start_date=None,
    end_date=None,
    db_path: Path = None,
) -> Dict:
    """
    Run the complete ETL pipeline: Extract → Transform → Load.

    Convenience function that orchestrates all three steps.

    Args:
        source: Brokerage provider name (None = all configured providers)
        start_date: Start of date range (defaults to 7 days)
        end_date: End of date range (defaults to today)
        db_path: Override database path (for testing)

    Returns:
        dict with combined stats from all three steps
    """
    import sys
    if str(PROJECT_DIR) not in sys.path:
        sys.path.insert(0, str(PROJECT_DIR))

    from src.etl.extract import extract_from_brokerage
    from src.etl.transform import transform_pending

    if db_path is None:
        db_path = DB_PATH

    # Determine providers
    if source:
        providers = [source]
    else:
        from src.api.brokerage import get_configured_providers
        providers = get_configured_providers()

    stats = {
        'providers': providers,
        'extract': {},
        'transform': {'transformed': 0, 'errors': 0, 'skipped': 0},
        'load': {'loaded': 0, 'duplicates': 0, 'load_errors': 0},
    }

    # Step 1: Extract from each provider
    for provider in providers:
        try:
            extract_result = extract_from_brokerage(
                provider, start_date, end_date, db_path
            )
            stats['extract'][provider] = extract_result
        except Exception as e:
            logger.error("Extract failed for %s: %s", provider, e)
            stats['extract'][provider] = {'error': str(e)}

    # Step 2: Transform all pending rows
    transform_result = transform_pending(db_path)
    stats['transform']['transformed'] = len(transform_result['transformed'])
    stats['transform']['errors'] = len(transform_result['errors'])
    stats['transform']['skipped'] = len(transform_result['skipped'])

    # Step 3: Load into production
    if transform_result['transformed'] or transform_result['errors'] or transform_result['skipped']:
        load_result = load_to_trades(
            transform_result['transformed'],
            transform_result['errors'],
            transform_result['skipped'],
            db_path,
        )
        stats['load'] = load_result

    return stats
