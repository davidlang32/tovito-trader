"""
Benchmark Market Data - Fetch & Cache
======================================
Fetches daily close prices for benchmark indices (SPY, QQQ, BTC-USD)
from Yahoo Finance via yfinance. Caches results in the benchmark_prices
SQLite table for reuse across charts, reports, and Discord messages.

Usage:
    from src.market_data.benchmarks import refresh_benchmark_cache, get_benchmark_data

    # Refresh cache (call from daily pipeline)
    stats = refresh_benchmark_cache(db_path)

    # Get data for chart generation
    data = get_benchmark_data(db_path, days=90)
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

BENCHMARK_TICKERS = ['SPY', 'QQQ', 'BTC-USD']

# Display names for chart legends
TICKER_LABELS = {
    'SPY': 'S&P 500 (SPY)',
    'QQQ': 'Nasdaq 100 (QQQ)',
    'BTC-USD': 'Bitcoin (BTC)',
}


def _ensure_table(db_path: Path) -> None:
    """Create the benchmark_prices table if it doesn't exist."""
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS benchmark_prices (
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            close_price REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (date, ticker)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_benchmark_ticker_date
        ON benchmark_prices(ticker, date)
    """)
    conn.commit()
    conn.close()


def _get_latest_cached_date(db_path: Path, ticker: str) -> Optional[str]:
    """Get the most recent cached date for a ticker."""
    conn = sqlite3.connect(str(db_path), timeout=10)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT MAX(date) FROM benchmark_prices WHERE ticker = ?",
        (ticker,)
    )
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] else None


def refresh_benchmark_cache(
    db_path: Path,
    tickers: Optional[List[str]] = None,
    lookback_days: int = 400,
) -> Dict[str, int]:
    """
    Fetch and cache benchmark daily close prices.

    Only fetches dates not already in the cache (incremental).

    Args:
        db_path: Path to SQLite database.
        tickers: List of Yahoo Finance tickers (default: BENCHMARK_TICKERS).
        lookback_days: How far back to fetch on first run.

    Returns:
        Dict mapping ticker -> number of new rows inserted.
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed. Run: pip install yfinance")
        return {}

    if tickers is None:
        tickers = BENCHMARK_TICKERS

    _ensure_table(db_path)

    stats = {}
    today = datetime.now().strftime('%Y-%m-%d')

    for ticker in tickers:
        try:
            latest = _get_latest_cached_date(db_path, ticker)

            if latest:
                # Incremental: fetch from the day after the last cached date
                start_date = (
                    datetime.strptime(latest, '%Y-%m-%d') + timedelta(days=1)
                ).strftime('%Y-%m-%d')
            else:
                # First run: fetch full lookback
                start_date = (
                    datetime.now() - timedelta(days=lookback_days)
                ).strftime('%Y-%m-%d')

            if start_date > today:
                logger.info(f"{ticker}: cache is up to date ({latest})")
                stats[ticker] = 0
                continue

            logger.info(f"{ticker}: fetching {start_date} to {today}")
            data = yf.download(
                ticker,
                start=start_date,
                end=(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
                progress=False,
                auto_adjust=True,
            )

            if data.empty:
                logger.warning(f"{ticker}: no data returned from Yahoo Finance")
                stats[ticker] = 0
                continue

            # Insert into cache
            conn = sqlite3.connect(str(db_path), timeout=10)
            cursor = conn.cursor()
            inserted = 0

            for date_idx, row in data.iterrows():
                date_str = date_idx.strftime('%Y-%m-%d')
                # Handle both single-ticker and multi-ticker column formats
                close = float(row['Close'].iloc[0]) if hasattr(row['Close'], 'iloc') else float(row['Close'])

                try:
                    cursor.execute(
                        "INSERT OR IGNORE INTO benchmark_prices (date, ticker, close_price) "
                        "VALUES (?, ?, ?)",
                        (date_str, ticker, round(close, 2))
                    )
                    if cursor.rowcount > 0:
                        inserted += 1
                except sqlite3.IntegrityError:
                    pass  # Already cached

            conn.commit()
            conn.close()

            stats[ticker] = inserted
            logger.info(f"{ticker}: {inserted} new prices cached")

        except Exception as e:
            logger.error(f"{ticker}: fetch failed - {e}")
            stats[ticker] = 0

    return stats


def get_benchmark_data(
    db_path: Path,
    tickers: Optional[List[str]] = None,
    days: int = 90,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, List[Dict]]:
    """
    Retrieve cached benchmark data for chart generation.

    Args:
        db_path: Path to SQLite database.
        tickers: Tickers to retrieve (default: BENCHMARK_TICKERS).
        days: Number of calendar days to retrieve.
        start_date: Optional start date (YYYY-MM-DD), overrides days.
        end_date: Optional end date (YYYY-MM-DD).

    Returns:
        Dict mapping ticker -> list of {'date': str, 'close_price': float}
        Ordered chronologically (oldest first).
    """
    if tickers is None:
        tickers = BENCHMARK_TICKERS

    _ensure_table(db_path)

    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    result = {}

    for ticker in tickers:
        if start_date:
            query = (
                "SELECT date, close_price FROM benchmark_prices "
                "WHERE ticker = ? AND date >= ?"
            )
            params = [ticker, start_date]
            if end_date:
                query += " AND date <= ?"
                params.append(end_date)
            query += " ORDER BY date ASC"
        else:
            cutoff = (
                datetime.now() - timedelta(days=days)
            ).strftime('%Y-%m-%d')
            query = (
                "SELECT date, close_price FROM benchmark_prices "
                "WHERE ticker = ? AND date >= ? ORDER BY date ASC"
            )
            params = [ticker, cutoff]

        cursor.execute(query, params)
        rows = cursor.fetchall()
        result[ticker] = [
            {'date': row['date'], 'close_price': row['close_price']}
            for row in rows
        ]

    conn.close()
    return result


def normalize_series(
    series: List[Dict],
    price_key: str = 'close_price',
) -> List[Dict]:
    """
    Normalize a price series to percentage change from first value.

    Args:
        series: List of dicts with 'date' and price_key.
        price_key: Key containing the price value.

    Returns:
        List of dicts with 'date' and 'pct_change' (0.0 at start).
    """
    if not series:
        return []

    base = series[0][price_key]
    if base == 0:
        return [{'date': s['date'], 'pct_change': 0.0} for s in series]

    return [
        {
            'date': s['date'],
            'pct_change': round((s[price_key] / base - 1) * 100, 4),
        }
        for s in series
    ]
