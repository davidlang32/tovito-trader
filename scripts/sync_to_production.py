"""
TOVITO TRADER - Sync to Production
====================================

Pushes daily pipeline data from the local SQLite database
to the production Railway API via POST /admin/sync.

Called as Step 9 of the daily NAV pipeline, or standalone:

    python scripts/sync_to_production.py              # Push today's data
    python scripts/sync_to_production.py --date 2026-02-24
    python scripts/sync_to_production.py --dry-run     # Show payload, don't send
    python scripts/sync_to_production.py --days 3      # Sync last 3 days

Requires .env:
    ADMIN_API_KEY=<same key as Railway>
    PRODUCTION_API_URL=https://api.tovitotrader.com
"""

import os
import sys
import json
import sqlite3
import argparse
import requests
from datetime import datetime, timedelta
from pathlib import Path

# Setup paths
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))
DB_PATH = PROJECT_DIR / "data" / "tovito.db"

# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_DIR / ".env")
except ImportError:
    pass

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
PRODUCTION_API_URL = os.getenv("PRODUCTION_API_URL", "").rstrip("/")


def get_connection():
    """Get local database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def collect_daily_nav(target_date: str) -> dict:
    """Collect daily NAV record for the given date."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, nav_per_share, total_portfolio_value, total_shares,
                   daily_change_dollars, daily_change_percent
            FROM daily_nav
            WHERE date = ?
        """, (target_date,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def collect_holdings_snapshot(target_date: str) -> dict:
    """Collect holdings snapshot + positions for the given date."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT snapshot_id, date, source, snapshot_time, total_positions
            FROM holdings_snapshots
            WHERE date = ?
            ORDER BY snapshot_id DESC
            LIMIT 1
        """, (target_date,))
        header = cursor.fetchone()
        if not header:
            return None

        header_dict = dict(header)
        snapshot_id = header_dict.pop("snapshot_id")

        cursor.execute("""
            SELECT symbol, underlying_symbol, quantity, instrument_type,
                   average_open_price, close_price, market_value, cost_basis,
                   unrealized_pl, option_type, strike, expiration_date, multiplier
            FROM position_snapshots
            WHERE snapshot_id = ?
        """, (snapshot_id,))
        positions = [dict(row) for row in cursor.fetchall()]
        header_dict["positions"] = positions
        return header_dict
    finally:
        conn.close()


def collect_trades(since_date: str) -> list:
    """Collect trades from the given date onward."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, trade_type, symbol, quantity, price, amount,
                   option_type, strike, expiration_date,
                   commission, fees, category, subcategory,
                   description, notes, source, brokerage_transaction_id
            FROM trades
            WHERE date >= ? AND is_deleted = 0
            ORDER BY date DESC
        """, (since_date,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def collect_benchmark_prices(since_date: str) -> list:
    """Collect benchmark prices from the given date onward."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, ticker, close_price
            FROM benchmark_prices
            WHERE date >= ?
            ORDER BY date DESC
        """, (since_date,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def collect_plan_performance(target_date: str) -> list:
    """Collect plan daily performance records for the given date."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, plan_id, market_value, cost_basis,
                   unrealized_pl, allocation_pct, position_count
            FROM plan_daily_performance
            WHERE date = ?
        """, (target_date,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def collect_reconciliation(target_date: str) -> dict:
    """Collect daily reconciliation record for the given date."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, tradier_balance, calculated_portfolio_value,
                   difference, total_shares, nav_per_share, status, notes
            FROM daily_reconciliation
            WHERE date = ?
        """, (target_date,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def build_sync_payload(target_date: str, lookback_days: int = 3) -> dict:
    """Build the full sync payload for the given date.

    Args:
        target_date: The primary date to sync (YYYY-MM-DD)
        lookback_days: How many days back to include for trades/benchmarks
    Returns:
        Dict matching the SyncPayload schema
    """
    since_date = (
        datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=lookback_days)
    ).strftime("%Y-%m-%d")

    payload = {}

    # Daily NAV
    nav = collect_daily_nav(target_date)
    if nav:
        payload["daily_nav"] = nav

    # Holdings snapshot
    snapshot = collect_holdings_snapshot(target_date)
    if snapshot:
        payload["holdings_snapshot"] = snapshot

    # Trades (last N days)
    trades = collect_trades(since_date)
    if trades:
        payload["trades"] = trades

    # Benchmark prices (last N days)
    benchmarks = collect_benchmark_prices(since_date)
    if benchmarks:
        payload["benchmark_prices"] = benchmarks

    # Reconciliation
    recon = collect_reconciliation(target_date)
    if recon:
        payload["reconciliation"] = recon

    # Plan daily performance
    plan_perf = collect_plan_performance(target_date)
    if plan_perf:
        payload["plan_performance"] = plan_perf

    return payload


def push_to_production(payload: dict) -> dict:
    """POST the sync payload to the production API.

    Returns:
        API response as dict
    Raises:
        Exception on HTTP error or network failure
    """
    if not PRODUCTION_API_URL:
        raise ValueError("PRODUCTION_API_URL not configured in .env")
    if not ADMIN_API_KEY:
        raise ValueError("ADMIN_API_KEY not configured in .env")

    url = f"{PRODUCTION_API_URL}/admin/sync"
    headers = {
        "X-Admin-Key": ADMIN_API_KEY,
        "Content-Type": "application/json",
    }

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def sync_to_production(target_date: str = None, lookback_days: int = 3,
                       dry_run: bool = False) -> dict:
    """Main sync function — collects data and pushes to production.

    Args:
        target_date: Date to sync (default: today)
        lookback_days: How many days back for trades/benchmarks
        dry_run: If True, build payload but don't send
    Returns:
        API response dict (or payload dict if dry_run)
    """
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")

    print(f"[SYNC] Building payload for {target_date}...")
    payload = build_sync_payload(target_date, lookback_days)

    # Summary
    has_nav = "daily_nav" in payload
    positions_count = len(payload.get("holdings_snapshot", {}).get("positions", []))
    trades_count = len(payload.get("trades", []))
    benchmarks_count = len(payload.get("benchmark_prices", []))
    has_recon = "reconciliation" in payload
    plan_perf_count = len(payload.get("plan_performance", []))

    print(f"  NAV: {'yes' if has_nav else 'no'}")
    print(f"  Positions: {positions_count}")
    print(f"  Trades: {trades_count}")
    print(f"  Benchmarks: {benchmarks_count}")
    print(f"  Reconciliation: {'yes' if has_recon else 'no'}")
    print(f"  Plan Performance: {plan_perf_count}")

    if not payload:
        print("[SYNC] Nothing to sync for this date.")
        return {"success": True, "message": "Nothing to sync"}

    if dry_run:
        print("\n[DRY RUN] Payload (not sending):")
        # Truncate large arrays for display
        display = dict(payload)
        if "trades" in display and len(display["trades"]) > 3:
            display["trades"] = display["trades"][:3] + [
                f"... and {len(display['trades']) - 3} more"
            ]
        if "benchmark_prices" in display and len(display["benchmark_prices"]) > 5:
            display["benchmark_prices"] = display["benchmark_prices"][:5] + [
                f"... and {len(display['benchmark_prices']) - 5} more"
            ]
        if "holdings_snapshot" in display:
            positions = display["holdings_snapshot"].get("positions", [])
            if len(positions) > 3:
                display["holdings_snapshot"]["positions"] = positions[:3] + [
                    f"... and {len(positions) - 3} more"
                ]
        print(json.dumps(display, indent=2, default=str))
        return payload

    print(f"\n[SYNC] Pushing to {PRODUCTION_API_URL}...")
    result = push_to_production(payload)
    print(f"[SYNC] Result: success={result.get('success')}")
    if result.get("nav_synced"):
        print(f"  NAV synced: yes")
    if result.get("positions_synced"):
        print(f"  Positions synced: {result['positions_synced']}")
    if result.get("trades_inserted"):
        print(f"  Trades inserted: {result['trades_inserted']}")
    if result.get("trades_skipped"):
        print(f"  Trades skipped (dupes): {result['trades_skipped']}")
    if result.get("benchmarks_inserted"):
        print(f"  Benchmarks inserted: {result['benchmarks_inserted']}")
    if result.get("reconciliation_synced"):
        print(f"  Reconciliation synced: yes")
    if result.get("plan_performance_synced"):
        print(f"  Plan performance synced: {result['plan_performance_synced']}")
    if result.get("errors"):
        for err in result["errors"]:
            print(f"  [ERROR] {err}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Sync daily pipeline data to production Railway API"
    )
    parser.add_argument(
        "--date",
        help="Target date (YYYY-MM-DD, default: today)",
        default=None,
    )
    parser.add_argument(
        "--days",
        type=int,
        default=3,
        help="Lookback days for trades/benchmarks (default: 3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show payload without sending",
    )
    args = parser.parse_args()

    try:
        result = sync_to_production(
            target_date=args.date,
            lookback_days=args.days,
            dry_run=args.dry_run,
        )
        if not args.dry_run:
            if result.get("success"):
                print("\n[OK] Production sync completed successfully.")
            else:
                print("\n[ERROR] Production sync completed with errors.")
                sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        print(f"\n[ERROR] Could not connect to production API: {e}")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"\n[ERROR] Production API returned error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Sync failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
