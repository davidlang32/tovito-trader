"""
TOVITO TRADER - Discord Monthly Performance Summary

Posts a fund-level monthly performance summary to Discord.
Does NOT include individual investor data — only aggregate fund metrics.

Usage:
    python scripts/reporting/discord_monthly_summary.py                    # Previous month
    python scripts/reporting/discord_monthly_summary.py --month 1 --year 2026  # Specific month
    python scripts/reporting/discord_monthly_summary.py --test             # Test embed

Can be wired into the monthly report generation pipeline or run standalone.
"""

import sys
import os
import sqlite3
import argparse
import logging
import calendar
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv
load_dotenv(PROJECT_DIR / ".env")

from src.utils.discord import post_embed, make_embed, COLORS, utc_timestamp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("monthly_summary")

WEBHOOK_URL = os.getenv("DISCORD_TRADES_WEBHOOK_URL", "")
DB_PATH = PROJECT_DIR / os.getenv("DATABASE_PATH", "data/tovito.db")


# ---------------------------------------------------------------------------
# Database queries
# ---------------------------------------------------------------------------

def get_monthly_performance(cursor, year: int, month: int) -> dict:
    """
    Pull aggregate fund performance for a given month.

    Returns dict with: start_nav, end_nav, nav_change_pct, high_nav, low_nav,
    trading_days, total_portfolio_value, total_shares, investor_count,
    total_trades, month_name, year.
    """
    month_str = f"{month:02d}"
    year_str = str(year)
    month_name = calendar.month_name[month]

    # Start of month NAV
    if month == 1:
        cursor.execute(
            "SELECT nav_per_share FROM daily_nav WHERE date = ? LIMIT 1",
            (f"{year}-01-01",),
        )
    else:
        prev_month = f"{month - 1:02d}"
        cursor.execute(
            """SELECT nav_per_share FROM daily_nav
               WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
               ORDER BY date DESC LIMIT 1""",
            (year_str, prev_month),
        )
    row = cursor.fetchone()
    start_nav = row[0] if row else None

    # End of month NAV + portfolio value + shares
    cursor.execute(
        """SELECT nav_per_share, total_portfolio_value, total_shares, date
           FROM daily_nav
           WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
           ORDER BY date DESC LIMIT 1""",
        (year_str, month_str),
    )
    row = cursor.fetchone()
    if not row:
        return None
    end_nav, total_value, total_shares, end_date = row

    # High / low NAV for the month
    cursor.execute(
        """SELECT MIN(nav_per_share), MAX(nav_per_share), COUNT(*)
           FROM daily_nav
           WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?""",
        (year_str, month_str),
    )
    low_nav, high_nav, trading_days = cursor.fetchone()

    # Active investor count
    cursor.execute(
        "SELECT COUNT(*) FROM investors WHERE status = 'Active'"
    )
    investor_count = cursor.fetchone()[0]

    # Trade count for the month
    cursor.execute(
        """SELECT COUNT(*) FROM trades
           WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
           AND category = 'Trade'""",
        (year_str, month_str),
    )
    total_trades = cursor.fetchone()[0]

    # Calculate return
    nav_change_pct = None
    if start_nav and start_nav > 0:
        nav_change_pct = ((end_nav - start_nav) / start_nav) * 100

    return {
        "month_name": month_name,
        "year": year,
        "start_nav": start_nav,
        "end_nav": end_nav,
        "nav_change_pct": nav_change_pct,
        "high_nav": high_nav,
        "low_nav": low_nav,
        "trading_days": trading_days,
        "total_portfolio_value": total_value,
        "total_shares": total_shares,
        "investor_count": investor_count,
        "total_trades": total_trades,
        "end_date": end_date,
    }


def get_inception_return(cursor) -> float:
    """Calculate return since fund inception (Jan 1, 2026)."""
    cursor.execute(
        "SELECT nav_per_share FROM daily_nav ORDER BY date ASC LIMIT 1"
    )
    first = cursor.fetchone()
    cursor.execute(
        "SELECT nav_per_share FROM daily_nav ORDER BY date DESC LIMIT 1"
    )
    last = cursor.fetchone()
    if first and last and first[0] > 0:
        return ((last[0] - first[0]) / first[0]) * 100
    return 0.0


# ---------------------------------------------------------------------------
# Embed builder
# ---------------------------------------------------------------------------

def build_monthly_embed(perf: dict, inception_return: float) -> dict:
    """Build a rich Discord embed for monthly fund performance."""
    change = perf["nav_change_pct"]
    if change is not None:
        is_positive = change >= 0
        arrow = "\u2B06\uFE0F" if is_positive else "\u2B07\uFE0F"  # ⬆️ / ⬇️
        color = COLORS["green"] if is_positive else COLORS["red"]
        change_str = f"{arrow} {change:+.2f}%"
    else:
        color = COLORS["blue"]
        change_str = "N/A"

    title = f"\U0001F4CA {perf['month_name']} {perf['year']} — Fund Performance"  # 📊

    fields = [
        {"name": "Monthly Return", "value": change_str, "inline": True},
        {"name": "Inception Return", "value": f"{inception_return:+.2f}%", "inline": True},
        {"name": "NAV/Share", "value": f"${perf['end_nav']:,.4f}", "inline": True},
        {"name": "Month High", "value": f"${perf['high_nav']:,.4f}", "inline": True},
        {"name": "Month Low", "value": f"${perf['low_nav']:,.4f}", "inline": True},
        {"name": "Trading Days", "value": str(perf["trading_days"]), "inline": True},
        {"name": "Trades Executed", "value": str(perf["total_trades"]), "inline": True},
        {"name": "Active Investors", "value": str(perf["investor_count"]), "inline": True},
    ]

    return make_embed(
        title=title,
        color=color,
        fields=fields,
        footer="Tovito Trader — Monthly Summary",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Post monthly performance to Discord")
    parser.add_argument("--month", type=int, help="Month number (1-12)")
    parser.add_argument("--year", type=int, help="Year")
    parser.add_argument("--test", action="store_true", help="Post a test embed")
    args = parser.parse_args()

    if args.test:
        embed = make_embed(
            title="\u2705 Monthly Summary — Test Message",
            color=COLORS["blue"],
            description="If you see this, the monthly summary webhook is working.",
            fields=[{"name": "Status", "value": "Connected", "inline": True}],
        )
        success = post_embed(WEBHOOK_URL, embed)
        print("[OK] Test sent" if success else "[FAIL] Could not send test")
        sys.exit(0 if success else 1)

    # Default to previous month
    now = datetime.now()
    if args.month and args.year:
        month, year = args.month, args.year
    else:
        # Previous month
        if now.month == 1:
            month, year = 12, now.year - 1
        else:
            month, year = now.month - 1, now.year

    logger.info("Generating %s %d summary...", calendar.month_name[month], year)

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    cursor = conn.cursor()

    try:
        perf = get_monthly_performance(cursor, year, month)
        if not perf:
            logger.error("No NAV data found for %s %d", calendar.month_name[month], year)
            sys.exit(1)

        inception_return = get_inception_return(cursor)
        embed = build_monthly_embed(perf, inception_return)
        success = post_embed(WEBHOOK_URL, embed)

        if success:
            logger.info("Monthly summary posted to Discord")
        else:
            logger.error("Failed to post monthly summary")
            sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
