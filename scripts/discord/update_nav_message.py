"""
TOVITO TRADER - Discord Pinned NAV Updater

Uses a Discord bot to post or edit a pinned message in a designated channel
with the current NAV and a chart showing NAV history.

Usage:
    python scripts/discord/update_nav_message.py          # Update pinned NAV message
    python scripts/discord/update_nav_message.py --test    # Post a test embed
    python scripts/discord/update_nav_message.py --days 90 # Chart with 90 days of history

Requirements:
    - discord.py installed (pip install discord.py)
    - DISCORD_BOT_TOKEN in .env
    - DISCORD_NAV_CHANNEL_ID in .env (right-click channel → Copy Channel ID)
    - Bot has permissions: Send Messages, Manage Messages, Attach Files, Read Message History

How the pinned message works:
    - First run: Posts a new message and pins it
    - Subsequent runs: Finds the bot's pinned message and edits it in place
    - No message ID storage needed — the bot finds its own pinned message each time
"""

import sys
import os
import sqlite3
import asyncio
import logging
import argparse
import tempfile
from pathlib import Path
from datetime import datetime, timezone

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv
load_dotenv(PROJECT_DIR / ".env")

import discord

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("nav_updater")

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
CHANNEL_ID = os.getenv("DISCORD_NAV_CHANNEL_ID", "")
DB_PATH = PROJECT_DIR / os.getenv("DATABASE_PATH", "data/tovito.db")
DEFAULT_CHART_DAYS = 90


# ---------------------------------------------------------------------------
# Database queries
# ---------------------------------------------------------------------------

def get_nav_history(days: int = DEFAULT_CHART_DAYS) -> list:
    """Fetch recent NAV history for chart generation."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    cursor = conn.cursor()
    cursor.execute(
        """SELECT date, nav_per_share
           FROM daily_nav
           ORDER BY date DESC
           LIMIT ?""",
        (days,),
    )
    rows = cursor.fetchall()
    conn.close()
    # Reverse so oldest first (for chart)
    return [{"date": r[0], "nav_per_share": r[1]} for r in reversed(rows)]


def get_current_nav_data() -> dict:
    """Fetch current NAV and performance metrics."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    cursor = conn.cursor()

    # Latest NAV
    cursor.execute(
        """SELECT date, nav_per_share, total_portfolio_value, total_shares,
                  daily_change_value, daily_change_percent
           FROM daily_nav ORDER BY date DESC LIMIT 1"""
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    current = {
        "date": row[0],
        "nav_per_share": row[1],
        "total_portfolio_value": row[2],
        "total_shares": row[3],
        "daily_change_value": row[4] or 0,
        "daily_change_percent": row[5] or 0,
    }

    # Inception NAV (first entry)
    cursor.execute(
        "SELECT nav_per_share FROM daily_nav ORDER BY date ASC LIMIT 1"
    )
    first = cursor.fetchone()
    if first and first[0] > 0:
        current["inception_return"] = ((current["nav_per_share"] - first[0]) / first[0]) * 100
        current["inception_nav"] = first[0]
    else:
        current["inception_return"] = 0.0
        current["inception_nav"] = current["nav_per_share"]

    # Trading days count
    cursor.execute("SELECT COUNT(*) FROM daily_nav")
    current["trading_days"] = cursor.fetchone()[0]

    # Active investors
    cursor.execute("SELECT COUNT(*) FROM investors WHERE status = 'Active'")
    current["investor_count"] = cursor.fetchone()[0]

    conn.close()
    return current


def get_trade_counts(days: int = DEFAULT_CHART_DAYS) -> list:
    """Fetch daily trade counts for chart overlay."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    cursor = conn.cursor()
    cursor.execute(
        """SELECT date, COUNT(*) as trade_count
           FROM trades
           WHERE category = 'Trade'
           GROUP BY date
           ORDER BY date DESC
           LIMIT ?""",
        (days,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"date": r[0], "trade_count": r[1]} for r in reversed(rows)]


# ---------------------------------------------------------------------------
# Chart generation
# ---------------------------------------------------------------------------

# Discord-optimized chart dimensions (large, high-res for full-width display)
DISCORD_CHART_WIDTH = 14.0   # inches — nearly full Discord embed width
DISCORD_CHART_HEIGHT = 7.0   # inches — tall enough to be impactful
DISCORD_CHART_DPI = 200      # high-res for crisp rendering


def generate_chart(days: int = DEFAULT_CHART_DAYS) -> Path:
    """Generate NAV vs Benchmarks chart PNG sized for Discord.

    Falls back to the NAV-only chart if benchmark data is unavailable.
    """
    nav_history = get_nav_history(days)

    if not nav_history:
        logger.warning("No NAV history found — cannot generate chart")
        return None

    # Try benchmark chart first (includes NAV mountain + SPY/QQQ/BTC)
    try:
        from src.reporting.charts import generate_benchmark_chart
        from src.market_data.benchmarks import get_benchmark_data

        benchmark_data = get_benchmark_data(DB_PATH, days=days)
        has_benchmarks = any(len(v) > 0 for v in benchmark_data.values())

        if has_benchmarks:
            chart_path = generate_benchmark_chart(
                nav_history,
                benchmark_data,
                width=DISCORD_CHART_WIDTH,
                height=DISCORD_CHART_HEIGHT,
                dpi=DISCORD_CHART_DPI,
            )
            logger.info("Benchmark chart generated: %s", chart_path)
            return chart_path
    except Exception as e:
        logger.warning("Benchmark chart failed, falling back to NAV chart: %s", e)

    # Fallback: NAV-only chart
    from src.reporting.charts import generate_nav_chart

    trade_counts = get_trade_counts(days)
    chart_path = generate_nav_chart(
        nav_history,
        trade_counts,
        width=DISCORD_CHART_WIDTH,
        height=DISCORD_CHART_HEIGHT,
        dpi=DISCORD_CHART_DPI,
    )
    logger.info("NAV chart generated (fallback): %s", chart_path)
    return chart_path


# ---------------------------------------------------------------------------
# Embed builder
# ---------------------------------------------------------------------------

def build_nav_embed(nav_data: dict, chart_filename: str = None) -> discord.Embed:
    """Build a Discord embed with current NAV data."""
    change = nav_data["daily_change_percent"]
    is_positive = change >= 0
    arrow = "\u2B06\uFE0F" if is_positive else "\u2B07\uFE0F"  # ⬆️ / ⬇️
    color = discord.Colour.green() if is_positive else discord.Colour.red()

    embed = discord.Embed(
        title="\U0001F4CA Tovito Trader \u2014 Daily NAV Update",  # 📊
        color=color,
        timestamp=datetime.now(tz=timezone.utc),
    )

    # NAV per share
    embed.add_field(
        name="NAV/Share",
        value=f"**${nav_data['nav_per_share']:,.4f}**",
        inline=True,
    )

    # Daily change
    change_val = nav_data["daily_change_value"]
    embed.add_field(
        name="Daily Change",
        value=f"{arrow} ${abs(change_val):,.4f} ({change:+.2f}%)",
        inline=True,
    )

    # Inception return
    inception = nav_data.get("inception_return", 0)
    inception_arrow = "\u2B06\uFE0F" if inception >= 0 else "\u2B07\uFE0F"
    embed.add_field(
        name="Since Inception",
        value=f"{inception_arrow} {inception:+.2f}%",
        inline=True,
    )

    # Trading days
    embed.add_field(
        name="Trading Days",
        value=str(nav_data.get("trading_days", 0)),
        inline=True,
    )

    # Active investors
    embed.add_field(
        name="Active Investors",
        value=str(nav_data.get("investor_count", 0)),
        inline=True,
    )

    # NAV date
    embed.add_field(
        name="As Of",
        value=nav_data["date"],
        inline=True,
    )

    # Attach chart image
    if chart_filename:
        embed.set_image(url=f"attachment://{chart_filename}")

    embed.set_footer(text="Tovito Trader \u2022 Updated daily after market close")

    return embed


# ---------------------------------------------------------------------------
# Bot logic
# ---------------------------------------------------------------------------

async def find_bot_pinned_message(channel, bot_user_id: int):
    """Find the bot's own pinned message in the channel, if any."""
    try:
        async for msg in channel.pins():
            if msg.author.id == bot_user_id:
                return msg
    except Exception as e:
        logger.warning("Could not fetch pins: %s", e)
    return None


async def update_pinned_message(
    bot_token: str,
    channel_id: int,
    chart_days: int = DEFAULT_CHART_DAYS,
    test_mode: bool = False,
):
    """
    Connect to Discord, update (or create) the pinned NAV message.

    Uses discord.py Client for a one-shot connect → update → disconnect.
    """
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        try:
            logger.info("Connected as %s", client.user)

            channel = client.get_channel(channel_id)
            if channel is None:
                channel = await client.fetch_channel(channel_id)

            if channel is None:
                logger.error("Channel %d not found", channel_id)
                await client.close()
                return

            # Log bot permissions for debugging
            perms = channel.permissions_for(channel.guild.me)
            logger.info(
                "Bot permissions — send: %s, embed: %s, attach: %s, "
                "read_history: %s, manage_messages: %s",
                perms.send_messages, perms.embed_links, perms.attach_files,
                perms.read_message_history, perms.manage_messages,
            )

            if test_mode:
                embed = discord.Embed(
                    title="\u2705 NAV Updater \u2014 Test Message",
                    description="If you see this, the bot is working correctly.",
                    color=discord.Colour.blue(),
                    timestamp=datetime.now(tz=timezone.utc),
                )
                embed.set_footer(text="Tovito Trader")
                await channel.send(embed=embed)
                logger.info("Test message sent")
                await client.close()
                return

            # Get NAV data
            nav_data = get_current_nav_data()
            if not nav_data:
                logger.error("No NAV data available")
                await client.close()
                return

            # Generate chart
            chart_path = generate_chart(chart_days)
            chart_file = None
            chart_filename = None
            if chart_path and chart_path.exists():
                chart_filename = "nav_chart.png"
                chart_file = discord.File(str(chart_path), filename=chart_filename)

            # Build embed
            embed = build_nav_embed(nav_data, chart_filename)

            # Find existing pinned message by this bot
            existing = await find_bot_pinned_message(channel, client.user.id)

            if existing:
                # Edit existing pinned message
                logger.info("Editing existing pinned message (ID: %d)", existing.id)
                # Must create a new File for the edit
                if chart_path and chart_path.exists():
                    chart_file = discord.File(str(chart_path), filename=chart_filename)
                    await existing.edit(embed=embed, attachments=[chart_file])
                else:
                    await existing.edit(embed=embed)
                logger.info("Pinned message updated successfully")
            else:
                # Post new message and pin it
                logger.info("No existing pinned message found — creating new one")
                if chart_file:
                    msg = await channel.send(embed=embed, file=chart_file)
                else:
                    msg = await channel.send(embed=embed)

                try:
                    await msg.pin()
                    logger.info("New message pinned (ID: %d)", msg.id)
                except discord.Forbidden:
                    logger.warning("Bot lacks permission to pin messages")

            # Clean up chart temp file
            if chart_path and chart_path.exists():
                try:
                    chart_path.unlink()
                except OSError:
                    pass

        except Exception as e:
            logger.error("Error updating NAV message: %s", e)
        finally:
            await client.close()

    await client.start(bot_token)


# ---------------------------------------------------------------------------
# Public API (called from daily_nav_enhanced.py)
# ---------------------------------------------------------------------------

def update_nav_message(chart_days: int = DEFAULT_CHART_DAYS):
    """
    Synchronous entry point for updating the Discord pinned NAV message.

    Can be called from the daily NAV pipeline as a non-fatal step.
    """
    if not BOT_TOKEN:
        logger.warning("DISCORD_BOT_TOKEN not set — skipping Discord NAV update")
        return False
    if not CHANNEL_ID:
        logger.warning("DISCORD_NAV_CHANNEL_ID not set — skipping Discord NAV update")
        return False

    try:
        channel_id = int(CHANNEL_ID)
    except ValueError:
        logger.error("DISCORD_NAV_CHANNEL_ID is not a valid integer: %s", CHANNEL_ID)
        return False

    try:
        asyncio.run(update_pinned_message(BOT_TOKEN, channel_id, chart_days))
        return True
    except Exception as e:
        logger.error("Discord NAV update failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Update Discord pinned NAV message")
    parser.add_argument("--test", action="store_true", help="Post a test embed")
    parser.add_argument("--days", type=int, default=DEFAULT_CHART_DAYS,
                        help=f"Days of NAV history for chart (default: {DEFAULT_CHART_DAYS})")
    args = parser.parse_args()

    if not BOT_TOKEN:
        print("[FAIL] DISCORD_BOT_TOKEN not set in .env")
        sys.exit(1)
    if not CHANNEL_ID:
        print("[FAIL] DISCORD_NAV_CHANNEL_ID not set in .env")
        sys.exit(1)

    try:
        channel_id = int(CHANNEL_ID)
    except ValueError:
        print(f"[FAIL] DISCORD_NAV_CHANNEL_ID is not a valid integer: {CHANNEL_ID}")
        sys.exit(1)

    if args.test:
        asyncio.run(update_pinned_message(BOT_TOKEN, channel_id, test_mode=True))
    else:
        asyncio.run(update_pinned_message(BOT_TOKEN, channel_id, chart_days=args.days))


if __name__ == "__main__":
    main()
