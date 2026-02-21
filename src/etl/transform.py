"""
ETL Transform Layer
===================
Reads pending rows from brokerage_transactions_raw and normalizes them
into a canonical format ready for the production trades table.

The canonical mapping ensures that regardless of source brokerage,
every trade gets the same trade_type, category, and subcategory
for equivalent transaction types.
"""

import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

PROJECT_DIR = Path("C:/tovito-trader")
DB_PATH = PROJECT_DIR / "data" / "tovito.db"


# ============================================================
# CANONICAL MAPPING
# ============================================================
# Central truth for how brokerage-specific transaction types
# map to our standard trade_type, category, and subcategory.
# This replaces the per-client normalization logic for the ETL path.

# TastyTrade type+subtype → (trade_type, category, subcategory)
TASTYTRADE_MAP = {
    # Trades
    ('trade', 'buy'): ('buy', 'Trade', 'Stock Buy'),
    ('trade', 'sell'): ('sell', 'Trade', 'Stock Sell'),
    ('trade', 'buy to open'): ('buy_to_open', 'Trade', 'Option Buy'),
    ('trade', 'sell to close'): ('sell_to_close', 'Trade', 'Option Sell'),
    ('trade', 'buy to close'): ('buy_to_close', 'Trade', 'Option Buy'),
    ('trade', 'sell to open'): ('sell_to_open', 'Trade', 'Option Sell'),
    # Money movements
    ('money movement', ''): ('ach', 'Transfer', None),  # subcategory from amount sign
    ('balance adjustment', ''): ('ach', 'Transfer', None),
    # Income
    ('dividend', ''): ('dividend', 'Income', 'Dividend'),
    ('interest', ''): ('interest', 'Income', 'Interest'),
    # Fees
    ('fee', ''): ('fee', 'Fee', 'Fee'),
    # Other
    ('receive deliver', ''): ('other', 'Other', 'Receive Deliver'),
}

# Tradier type → (trade_type, category, subcategory)
TRADIER_MAP = {
    'trade': ('buy', 'Trade', None),       # subcategory from description/amount
    'option': ('buy_to_open', 'Trade', None),  # refined by description
    'ach': ('ach', 'Transfer', None),       # subcategory from amount sign
    'wire': ('ach', 'Transfer', None),
    'journal': ('journal', 'Transfer', 'Journal'),
    'dividend': ('dividend', 'Income', 'Dividend'),
    'interest': ('interest', 'Income', 'Interest'),
    'fee': ('fee', 'Fee', 'Fee'),
    'commission': ('fee', 'Fee', 'Commission'),
}


def transform_pending(db_path: Path = None) -> Dict:
    """
    Transform all pending rows in staging into canonical format.

    Reads rows WHERE etl_status = 'pending', applies the canonical
    mapping, and returns normalized dicts ready for insertion into
    the production trades table.

    Args:
        db_path: Override database path (for testing)

    Returns:
        dict with:
            'transformed': list of (raw_id, normalized_dict) tuples
            'errors': list of (raw_id, error_message) tuples
            'skipped': list of raw_ids
    """
    if db_path is None:
        db_path = DB_PATH

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    result = {'transformed': [], 'errors': [], 'skipped': []}

    try:
        cursor.execute("""
            SELECT raw_id, source, brokerage_transaction_id, raw_data,
                   transaction_date, transaction_type, transaction_subtype,
                   symbol, amount, description
            FROM brokerage_transactions_raw
            WHERE etl_status = 'pending'
            ORDER BY transaction_date, raw_id
        """)

        rows = cursor.fetchall()
        logger.info("Found %d pending rows to transform", len(rows))

        for row in rows:
            try:
                normalized = _transform_row(dict(row))
                if normalized:
                    result['transformed'].append((row['raw_id'], normalized))
                else:
                    result['skipped'].append(row['raw_id'])
            except Exception as e:
                logger.error(
                    "Transform error for raw_id=%d: %s", row['raw_id'], e
                )
                result['errors'].append((row['raw_id'], str(e)))

    finally:
        conn.close()

    logger.info(
        "Transform complete: %d transformed, %d errors, %d skipped",
        len(result['transformed']), len(result['errors']), len(result['skipped'])
    )
    return result


def _transform_row(row: Dict) -> Optional[Dict]:
    """
    Transform a single staging row into canonical trades format.

    Args:
        row: Dict from brokerage_transactions_raw table

    Returns:
        Normalized dict ready for trades table insertion, or None to skip
    """
    source = row['source']
    raw_data = json.loads(row['raw_data']) if isinstance(row['raw_data'], str) else row['raw_data']
    amount = row['amount'] or 0.0
    txn_type = (row['transaction_type'] or '').lower().strip()
    txn_subtype = (row['transaction_subtype'] or '').lower().strip()
    description = (row['description'] or '').lower()

    if source == 'tastytrade':
        trade_type, category, subcategory = _map_tastytrade(
            txn_type, txn_subtype, amount, raw_data
        )
    elif source == 'tradier':
        trade_type, category, subcategory = _map_tradier(
            txn_type, description, amount, raw_data
        )
    else:
        trade_type, category, subcategory = 'other', 'Other', 'Unknown'

    # Resolve ACH subcategory from amount sign
    if subcategory is None and trade_type == 'ach':
        subcategory = 'Deposit' if amount > 0 else 'Withdrawal'

    # Resolve trade subcategory from amount/description for Tradier
    if subcategory is None and category == 'Trade':
        if 'buy' in description:
            subcategory = 'Stock Buy'
        elif 'sell' in description:
            subcategory = 'Stock Sell'
        elif amount < 0:
            subcategory = 'Stock Buy'
        elif amount > 0:
            subcategory = 'Stock Sell'
        else:
            subcategory = 'Trade'

    # Refine Tradier trade_type from description
    if source == 'tradier' and trade_type in ('buy', 'buy_to_open') and category == 'Trade':
        if 'sell' in description:
            trade_type = 'sell' if txn_type == 'trade' else 'sell_to_close'
        elif 'buy' in description:
            trade_type = 'buy' if txn_type == 'trade' else 'buy_to_open'

    # Extract financial fields from raw data
    commission = _extract_float(raw_data, 'commission', 0.0)
    fees = 0.0
    if source == 'tastytrade':
        fees += _extract_float(raw_data, 'clearing_fees', 0.0)
        fees += _extract_float(raw_data, 'regulatory_fees', 0.0)

    quantity = _extract_float(raw_data, 'quantity', None)
    price = _extract_float(raw_data, 'price', None)
    if price is None:
        price = _extract_float(raw_data, 'strike_price', None)
        # Only use strike_price if it's actually a trade price, not an option strike
        if price and trade_type not in ('buy_to_open', 'sell_to_close',
                                         'buy_to_close', 'sell_to_open'):
            price = None

    # Option fields
    option_type = None
    strike = None
    expiration_date = None
    if trade_type in ('buy_to_open', 'sell_to_close', 'buy_to_close', 'sell_to_open'):
        option_type = _extract_str(raw_data, 'option_type')
        strike = _extract_float(raw_data, 'strike_price', None) or _extract_float(raw_data, 'strike', None)
        expiration_date = _extract_str(raw_data, 'expiration_date')
        if expiration_date:
            expiration_date = str(expiration_date)[:10]

    return {
        'date': row['transaction_date'],
        'type': trade_type,  # Raw type for production 'type' column (NOT NULL)
        'trade_type': trade_type,
        'symbol': row['symbol'] or '',
        'quantity': quantity,
        'price': price,
        'amount': round(amount, 2),
        'option_type': option_type,
        'strike': strike,
        'expiration_date': expiration_date,
        'commission': round(commission, 2),
        'fees': round(fees, 2),
        'category': category,
        'subcategory': subcategory or 'Unknown',
        'description': row['description'] or '',
        'notes': '',
        'source': source,
        'brokerage_transaction_id': row['brokerage_transaction_id'],
    }


def _map_tastytrade(
    txn_type: str, txn_subtype: str, amount: float, raw_data: dict
) -> Tuple[str, str, Optional[str]]:
    """Map TastyTrade transaction type to canonical values."""
    # Try exact match first
    key = (txn_type, txn_subtype)
    if key in TASTYTRADE_MAP:
        return TASTYTRADE_MAP[key]

    # Try type-only match (subtype as wildcard)
    key_type_only = (txn_type, '')
    if key_type_only in TASTYTRADE_MAP:
        return TASTYTRADE_MAP[key_type_only]

    # Fuzzy match for trades
    if txn_type == 'trade':
        if 'buy' in txn_subtype:
            if 'open' in txn_subtype:
                return ('buy_to_open', 'Trade', 'Option Buy')
            elif 'close' in txn_subtype:
                return ('buy_to_close', 'Trade', 'Option Buy')
            return ('buy', 'Trade', 'Stock Buy')
        elif 'sell' in txn_subtype:
            if 'close' in txn_subtype:
                return ('sell_to_close', 'Trade', 'Option Sell')
            elif 'open' in txn_subtype:
                return ('sell_to_open', 'Trade', 'Option Sell')
            return ('sell', 'Trade', 'Stock Sell')

    # Fallback
    logger.warning(
        "Unknown TastyTrade type: %s/%s — mapping to 'other'",
        txn_type, txn_subtype
    )
    return ('other', 'Other', txn_type.title() if txn_type else 'Unknown')


def _map_tradier(
    txn_type: str, description: str, amount: float, raw_data: dict
) -> Tuple[str, str, Optional[str]]:
    """Map Tradier transaction type to canonical values."""
    if txn_type in TRADIER_MAP:
        trade_type, category, subcategory = TRADIER_MAP[txn_type]

        # Refine option subcategory
        if txn_type == 'option':
            opt_type = raw_data.get('option_type', '')
            if opt_type:
                subcategory = f"Option {opt_type.title()}"
            else:
                subcategory = 'Option Trade'

        return (trade_type, category, subcategory)

    # Fuzzy matches
    if 'dividend' in txn_type:
        return ('dividend', 'Income', 'Dividend')
    if 'interest' in txn_type:
        return ('interest', 'Income', 'Interest')
    if 'fee' in txn_type or 'commission' in txn_type:
        return ('fee', 'Fee', txn_type.title())

    logger.warning("Unknown Tradier type: %s — mapping to 'other'", txn_type)
    return ('other', 'Other', txn_type.title() if txn_type else 'Unknown')


def _extract_float(data: dict, key: str, default=None):
    """Safely extract a float from a dict, handling various types."""
    val = data.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _extract_str(data: dict, key: str, default=None):
    """Safely extract a string from a dict."""
    val = data.get(key)
    if val is None:
        return default
    return str(val)
