"""
Migration: Add Plan Daily Performance Table
=============================================

Creates the plan_daily_performance table for tracking
per-plan allocation and performance over time.

Plans:
  - plan_cash: Treasury/money market (SGOV, cash)
  - plan_etf: Index ETFs (SPY, QQQ, SPXL, TQQQ)
  - plan_a: Leveraged options (everything else)

Usage:
    python scripts/setup/migrate_add_plan_performance.py
    python scripts/setup/migrate_add_plan_performance.py --backfill
"""

import os
import sys
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

DB_PATH = os.getenv("DATABASE_PATH", str(PROJECT_DIR / "data" / "tovito.db"))


def run_migration(backfill: bool = False):
    """Create plan_daily_performance table and optionally backfill."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print(f"Database: {DB_PATH}")
    print()

    # Create table
    print("Creating table: plan_daily_performance...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plan_daily_performance (
            date TEXT NOT NULL,
            plan_id TEXT NOT NULL,
            market_value REAL NOT NULL,
            cost_basis REAL NOT NULL,
            unrealized_pl REAL NOT NULL,
            allocation_pct REAL NOT NULL,
            position_count INTEGER NOT NULL,
            PRIMARY KEY (date, plan_id)
        )
    """)
    conn.commit()
    print("[OK] plan_daily_performance table created")

    if backfill:
        print()
        print("Backfilling from historical position snapshots...")
        _backfill_plan_performance(conn)

    conn.close()
    print()
    print("[OK] Migration complete")


def _backfill_plan_performance(conn):
    """Backfill plan performance from existing position_snapshots."""
    from src.plans.classification import classify_position_by_underlying

    cursor = conn.cursor()

    # Get all snapshot dates
    cursor.execute("""
        SELECT DISTINCT hs.date, hs.snapshot_id
        FROM holdings_snapshots hs
        ORDER BY hs.date
    """)
    snapshots = cursor.fetchall()

    if not snapshots:
        print("  No snapshots found to backfill.")
        return

    backfilled = 0
    for snapshot in snapshots:
        snap_date = snapshot["date"]
        snap_id = snapshot["snapshot_id"]

        # Get positions for this snapshot
        cursor.execute("""
            SELECT symbol, underlying_symbol, instrument_type,
                   quantity, market_value, cost_basis, unrealized_pl
            FROM position_snapshots
            WHERE snapshot_id = ?
        """, (snap_id,))
        positions = [dict(row) for row in cursor.fetchall()]

        if not positions:
            continue

        # Classify and aggregate
        plans = {}
        total_value = 0.0
        for pos in positions:
            plan_id = classify_position_by_underlying(
                symbol=pos.get("symbol", ""),
                underlying_symbol=pos.get("underlying_symbol"),
                instrument_type=pos.get("instrument_type"),
            )
            if plan_id not in plans:
                plans[plan_id] = {
                    "market_value": 0.0,
                    "cost_basis": 0.0,
                    "unrealized_pl": 0.0,
                    "position_count": 0,
                }
            mv = pos.get("market_value") or 0.0
            plans[plan_id]["market_value"] += mv
            plans[plan_id]["cost_basis"] += (pos.get("cost_basis") or 0.0)
            plans[plan_id]["unrealized_pl"] += (pos.get("unrealized_pl") or 0.0)
            plans[plan_id]["position_count"] += 1
            total_value += mv

        # Write plan performance
        for plan_id, data in plans.items():
            alloc_pct = (data["market_value"] / total_value * 100) if total_value > 0 else 0.0
            cursor.execute("""
                INSERT OR REPLACE INTO plan_daily_performance
                    (date, plan_id, market_value, cost_basis, unrealized_pl,
                     allocation_pct, position_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                snap_date, plan_id,
                round(data["market_value"], 2),
                round(data["cost_basis"], 2),
                round(data["unrealized_pl"], 2),
                round(alloc_pct, 2),
                data["position_count"],
            ))
            backfilled += 1

    conn.commit()
    print(f"  [OK] Backfilled {backfilled} plan performance records "
          f"from {len(snapshots)} snapshots")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Add plan_daily_performance table"
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Backfill from existing position snapshots",
    )
    args = parser.parse_args()
    run_migration(backfill=args.backfill)
