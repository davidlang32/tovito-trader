"""
ETL Extract Layer
=================
Pulls raw transaction data from brokerage APIs and ingests it into
the brokerage_transactions_raw staging table.

The staging table preserves the original API response as JSON, ensuring
no data is lost during normalization. Deduplication prevents re-ingesting
transactions that already exist in staging.
"""

import json
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Default database path
PROJECT_DIR = Path("C:/tovito-trader")
DB_PATH = PROJECT_DIR / "data" / "tovito.db"


def extract_from_brokerage(
    source: str,
    start_date: datetime = None,
    end_date: datetime = None,
    db_path: Path = None,
) -> Dict:
    """
    Extract raw transactions from a brokerage and ingest into staging.

    Calls the brokerage client's get_raw_transactions() method and
    inserts the results into brokerage_transactions_raw.

    Args:
        source: Brokerage provider name ('tradier' or 'tastytrade')
        start_date: Start of date range (defaults to 7 days ago)
        end_date: End of date range (defaults to today)
        db_path: Override database path (for testing)

    Returns:
        dict with: 'total': int, 'ingested': int, 'skipped': int, 'errors': int
    """
    import sys
    if str(PROJECT_DIR) not in sys.path:
        sys.path.insert(0, str(PROJECT_DIR))

    from src.api.brokerage import get_brokerage_client

    if start_date is None:
        start_date = datetime.now() - timedelta(days=7)
    if end_date is None:
        end_date = datetime.now()

    logger.info(
        "Extracting from %s: %s to %s",
        source,
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d'),
    )

    client = get_brokerage_client(source)
    raw_transactions = client.get_raw_transactions(start_date, end_date)

    logger.info("Fetched %d raw transactions from %s", len(raw_transactions), source)

    result = ingest_raw_transactions(source, raw_transactions, db_path)
    return result


def ingest_raw_transactions(
    source: str,
    raw_transactions: List[Dict],
    db_path: Path = None,
) -> Dict:
    """
    Insert raw transaction dicts into the staging table.

    Uses INSERT OR IGNORE to skip duplicates (dedup on source +
    brokerage_transaction_id unique constraint).

    Args:
        source: Brokerage provider name
        raw_transactions: List of dicts from client.get_raw_transactions()
        db_path: Override database path (for testing)

    Returns:
        dict with: 'total': int, 'ingested': int, 'skipped': int, 'errors': int
    """
    if db_path is None:
        db_path = DB_PATH

    result = {'total': len(raw_transactions), 'ingested': 0, 'skipped': 0, 'errors': 0}

    if not raw_transactions:
        logger.info("No transactions to ingest for %s", source)
        return result

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        for txn in raw_transactions:
            brokerage_id = txn.get('brokerage_transaction_id', '')
            if not brokerage_id:
                logger.warning("Skipping transaction with no brokerage_transaction_id")
                result['errors'] += 1
                continue

            # Serialize raw_data to JSON
            raw_data = txn.get('raw_data', {})
            raw_json = json.dumps(raw_data, default=str)

            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO brokerage_transactions_raw (
                        source,
                        brokerage_transaction_id,
                        raw_data,
                        transaction_date,
                        transaction_type,
                        transaction_subtype,
                        symbol,
                        amount,
                        description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    source,
                    brokerage_id,
                    raw_json,
                    txn.get('transaction_date', ''),
                    txn.get('transaction_type', ''),
                    txn.get('transaction_subtype'),
                    txn.get('symbol') or None,
                    txn.get('amount', 0.0),
                    txn.get('description', ''),
                ))

                if cursor.rowcount > 0:
                    result['ingested'] += 1
                else:
                    result['skipped'] += 1

            except sqlite3.Error as e:
                logger.error(
                    "Failed to ingest transaction %s from %s: %s",
                    brokerage_id, source, e
                )
                result['errors'] += 1

        conn.commit()

    except Exception as e:
        logger.error("Ingestion failed for %s: %s", source, e)
        conn.rollback()
        raise
    finally:
        conn.close()

    logger.info(
        "Ingestion complete for %s: %d total, %d ingested, %d skipped, %d errors",
        source, result['total'], result['ingested'], result['skipped'], result['errors']
    )
    return result
