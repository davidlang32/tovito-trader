"""
TOVITO TRADER - Discord Trade Notifier

Persistent service that polls brokerage APIs every 5 minutes for new trades
and posts opening/closing trades to Discord via webhook.

Usage:
    python scripts/trading/discord_trade_notifier.py              # Run service
    python scripts/trading/discord_trade_notifier.py --test       # Post a test embed and exit
    python scripts/trading/discord_trade_notifier.py --once       # Run one poll cycle and exit

Features:
    - Polls TastyTrade and Tradier every 5 minutes during market hours
    - Posts only opening/closing trades (excludes dividends, fees, ACH, etc.)
    - Deduplicates via in-memory seen-set with warm-up on startup
    - Color-coded Discord embeds (green=open, red=close)
    - Graceful error handling — API failures never crash the service
"""

import sys
import os
import time
import signal
import sqlite3
import logging
import requests
from pathlib import Path
from datetime import datetime, timedelta, time as dt_time, timezone

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv
load_dotenv(PROJECT_DIR / ".env")

from src.api.brokerage import get_all_brokerage_clients

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

POLL_INTERVAL_SECONDS = 300   # 5 minutes
OFF_HOURS_CHECK_SECONDS = 60  # Check clock every 60s when outside market hours

WEBHOOK_URL = os.getenv("DISCORD_TRADES_WEBHOOK_URL", "")

# Market-hours window (Eastern Time) — slightly wider to catch edge fills
MARKET_START = dt_time(9, 25)
MARKET_END = dt_time(16, 30)

# Trade types we care about (opening and closing trades only)
TRADING_TYPES = frozenset({
    "buy", "sell",
    "buy_to_open", "sell_to_open",
    "buy_to_close", "sell_to_close",
})

OPENING_TYPES = frozenset({"buy", "buy_to_open", "sell_to_open"})
CLOSING_TYPES = frozenset({"sell", "sell_to_close", "buy_to_close"})

# Discord embed colours
COLOR_OPEN = 0x00C853    # Green
COLOR_CLOSE = 0xFF1744   # Red
COLOR_INFO = 0x2196F3    # Blue (startup/status messages)

DB_PATH = PROJECT_DIR / os.getenv("DATABASE_PATH", "data/tovito.db")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("trade_notifier")


def log_to_db(level: str, message: str):
    """Write a log entry to the system_logs table."""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO system_logs (timestamp, log_type, category, message) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(), level, "TradeNotifier", message),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Never let DB logging crash the service


# ---------------------------------------------------------------------------
# Timezone helper
# ---------------------------------------------------------------------------

def _now_et() -> datetime:
    """Return current time in US Eastern."""
    try:
        import pytz
        return datetime.now(pytz.timezone("America/New_York"))
    except ImportError:
        from datetime import timezone
        return datetime.now(timezone(timedelta(hours=-5)))


def is_market_hours() -> bool:
    """True if current ET time is within the polling window (weekdays only)."""
    now = _now_et()
    if now.weekday() >= 5:
        return False
    return MARKET_START <= now.time() <= MARKET_END


# ---------------------------------------------------------------------------
# Trade filtering
# ---------------------------------------------------------------------------

def is_trading_trade(txn: dict) -> bool:
    """Return True if the transaction is an opening or closing trade."""
    return txn.get("transaction_type", "").lower() in TRADING_TYPES


# ---------------------------------------------------------------------------
# Discord formatting
# ---------------------------------------------------------------------------

def _format_action_label(txn_type: str) -> str:
    """Human-readable action label."""
    labels = {
        "buy": "BUY",
        "sell": "SELL",
        "buy_to_open": "BUY TO OPEN",
        "sell_to_open": "SELL TO OPEN",
        "buy_to_close": "BUY TO CLOSE",
        "sell_to_close": "SELL TO CLOSE",
    }
    return labels.get(txn_type.lower(), txn_type.upper())


def format_embed(txn: dict, source: str) -> dict:
    """Build a Discord embed dict for one trade."""
    txn_type = txn.get("transaction_type", "").lower()
    is_open = txn_type in OPENING_TYPES
    color = COLOR_OPEN if is_open else COLOR_CLOSE
    emoji = "\U0001f7e2" if is_open else "\U0001f534"  # 🟢 / 🔴

    symbol = txn.get("symbol", "???")
    action = _format_action_label(txn_type)
    quantity = txn.get("quantity")
    price = txn.get("price")
    amount = txn.get("amount", 0)

    # Build title — include option details if present
    title_parts = [emoji, action, "|", symbol]
    option_type = txn.get("option_type")
    strike = txn.get("strike")
    expiration = txn.get("expiration_date")
    if option_type and strike:
        opt_label = f"${strike:g}{option_type[0].upper()}"
        title_parts.append(opt_label)
        if expiration:
            title_parts.append(expiration)

    title = " ".join(str(p) for p in title_parts)

    # Build fields
    fields = []
    if quantity is not None:
        fields.append({"name": "Qty", "value": f"{abs(quantity):g}", "inline": True})
    if price is not None:
        fields.append({"name": "Price", "value": f"${price:,.2f}", "inline": True})
    if amount:
        fields.append({"name": "Total", "value": f"${abs(amount):,.2f}", "inline": True})
    if txn.get("commission") or txn.get("fees"):
        total_fees = (txn.get("commission") or 0) + (txn.get("fees") or 0)
        if total_fees:
            fields.append({"name": "Fees", "value": f"${abs(total_fees):,.2f}", "inline": True})

    fields.append({"name": "Source", "value": source.title(), "inline": True})

    now_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "title": title,
        "color": color,
        "fields": fields,
        "timestamp": now_str,
        "footer": {"text": "Tovito Trader"},
    }


def post_to_discord(embed: dict, webhook_url: str = WEBHOOK_URL) -> bool:
    """POST an embed to the Discord webhook. Returns True on success."""
    if not webhook_url:
        logger.warning("No DISCORD_TRADES_WEBHOOK_URL configured — skipping post")
        return False

    payload = {"embeds": [embed]}

    for attempt in range(3):
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            if resp.status_code == 429:
                # Rate-limited — wait and retry
                retry_after = resp.json().get("retry_after", 5)
                logger.warning("Discord rate-limited, waiting %.1fs", retry_after)
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.error("Discord POST failed (attempt %d): %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(2 ** attempt)

    return False


# ---------------------------------------------------------------------------
# TradeNotifier service
# ---------------------------------------------------------------------------

class TradeNotifier:
    """Polls brokerages for new trades and posts them to Discord."""

    def __init__(self):
        self.seen: set = set()  # (source, brokerage_transaction_id)
        self.running = False
        self._clients = None

    # -- Brokerage clients (lazy init) -------------------------------------

    def _get_clients(self) -> dict:
        """Get brokerage clients, re-initializing if needed."""
        if self._clients is None:
            try:
                self._clients = get_all_brokerage_clients()
                logger.info(
                    "Brokerage clients initialized: %s",
                    ", ".join(self._clients.keys()),
                )
            except Exception as e:
                logger.error("Failed to initialize brokerage clients: %s", e)
                self._clients = {}
        return self._clients

    # -- Warm-up -----------------------------------------------------------

    def warm_up(self):
        """Load today's existing trades into the seen-set without posting."""
        logger.info("Warming up — loading today's existing trades...")
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        total = 0

        for source, client in self._get_clients().items():
            try:
                transactions = client.get_transactions(
                    start_date=today, end_date=datetime.now()
                )
                for txn in transactions:
                    if is_trading_trade(txn):
                        key = (source, txn.get("brokerage_transaction_id", ""))
                        self.seen.add(key)
                        total += 1
            except Exception as e:
                logger.warning("Warm-up failed for %s: %s", source, e)

        logger.info("Warm-up complete — %d trades already seen today", total)
        log_to_db("INFO", f"Trade notifier started. Warm-up loaded {total} existing trades.")

    # -- Poll cycle --------------------------------------------------------

    def poll_cycle(self) -> int:
        """Run one fetch-filter-post cycle. Returns count of new trades posted."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        posted = 0

        for source, client in self._get_clients().items():
            try:
                transactions = client.get_transactions(
                    start_date=today, end_date=datetime.now()
                )
            except Exception as e:
                logger.warning("API fetch failed for %s: %s", source, e)
                continue

            for txn in transactions:
                if not is_trading_trade(txn):
                    continue

                key = (source, txn.get("brokerage_transaction_id", ""))
                if key in self.seen:
                    continue

                # New trade — post to Discord
                self.seen.add(key)
                embed = format_embed(txn, source)
                success = post_to_discord(embed)

                if success:
                    posted += 1
                    logger.info(
                        "Posted: %s %s %s @ %s [%s]",
                        txn.get("transaction_type"),
                        txn.get("symbol"),
                        txn.get("quantity"),
                        txn.get("price"),
                        source,
                    )
                else:
                    logger.error(
                        "Failed to post: %s %s [%s]",
                        txn.get("transaction_type"),
                        txn.get("symbol"),
                        source,
                    )

        return posted

    # -- Main loop ---------------------------------------------------------

    def start(self):
        """Blocking main loop — runs until stopped or interrupted."""
        if not WEBHOOK_URL:
            logger.error("DISCORD_TRADES_WEBHOOK_URL not set in .env — cannot start")
            sys.exit(1)

        self.running = True
        self.warm_up()

        logger.info(
            "Trade notifier running (poll every %ds, market hours %s-%s ET)",
            POLL_INTERVAL_SECONDS,
            MARKET_START.strftime("%H:%M"),
            MARKET_END.strftime("%H:%M"),
        )

        while self.running:
            try:
                if is_market_hours():
                    new_count = self.poll_cycle()
                    if new_count:
                        logger.info("Cycle complete — %d new trades posted", new_count)
                    time.sleep(POLL_INTERVAL_SECONDS)
                else:
                    # Outside market hours — check less frequently
                    time.sleep(OFF_HOURS_CHECK_SECONDS)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error("Unexpected error in poll loop: %s", e)
                time.sleep(POLL_INTERVAL_SECONDS)

        logger.info("Trade notifier stopped.")
        log_to_db("INFO", "Trade notifier stopped.")

    def stop(self):
        """Signal the main loop to exit."""
        self.running = False


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def send_test_embed():
    """Post a test embed to verify the webhook works."""
    embed = {
        "title": "\u2705 Trade Notifier — Test Message",
        "description": "If you see this, the webhook is working correctly.",
        "color": COLOR_INFO,
        "timestamp": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "footer": {"text": "Tovito Trader"},
        "fields": [
            {"name": "Status", "value": "Connected", "inline": True},
            {"name": "Providers", "value": ", ".join(get_all_brokerage_clients().keys()) or "none", "inline": True},
        ],
    }
    success = post_to_discord(embed)
    if success:
        print("[OK] Test message sent to Discord")
    else:
        print("[FAIL] Could not send test message — check webhook URL")
    return success


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Discord Trade Notifier Service")
    parser.add_argument("--test", action="store_true", help="Send a test embed and exit")
    parser.add_argument("--once", action="store_true", help="Run one poll cycle and exit")
    args = parser.parse_args()

    if args.test:
        success = send_test_embed()
        sys.exit(0 if success else 1)

    notifier = TradeNotifier()

    # Graceful shutdown on SIGINT / SIGTERM
    def handle_signal(signum, frame):
        logger.info("Received signal %d — shutting down", signum)
        notifier.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if args.once:
        notifier.warm_up()
        # Clear seen-set so --once actually posts today's trades
        notifier.seen.clear()
        count = notifier.poll_cycle()
        print(f"Posted {count} trades to Discord")
        sys.exit(0)

    notifier.start()


if __name__ == "__main__":
    main()
