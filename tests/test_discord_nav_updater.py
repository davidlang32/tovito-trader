"""
Tests for the Discord Pinned NAV Updater.

Covers:
- NAV data queries
- Embed building (correct fields, colours)
- Chart generation integration
- Pinned message finding logic
- Synchronous entry point
"""

import pytest
import sqlite3
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone
from pathlib import Path
import discord


class _AsyncPinIterator:
    """Helper that makes a list work with 'async for'."""

    def __init__(self, items):
        self._items = items
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item

import sys

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from scripts.discord.update_nav_message import (
    get_nav_history,
    get_current_nav_data,
    get_trade_counts,
    build_nav_embed,
    find_bot_pinned_message,
    update_nav_message,
    DEFAULT_CHART_DAYS,
)


# ============================================================
# Database fixtures
# ============================================================

@pytest.fixture
def nav_db(tmp_path):
    """Create a temp database with NAV data."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE daily_nav (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL UNIQUE,
            total_portfolio_value REAL NOT NULL,
            total_shares REAL NOT NULL,
            nav_per_share REAL NOT NULL,
            daily_change_value REAL,
            daily_change_percent REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE investors (
            investor_id TEXT PRIMARY KEY,
            name TEXT, email TEXT,
            current_shares REAL, net_investment REAL,
            status TEXT DEFAULT 'Active'
        )
    """)
    cursor.execute("""
        CREATE TABLE trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE, trade_type TEXT, symbol TEXT,
            quantity REAL, price REAL, amount REAL,
            category TEXT, source TEXT DEFAULT 'tastytrade'
        )
    """)

    # NAV data
    nav_rows = [
        ("2026-01-01", 20000, 2000, 10.0000, 0, 0),
        ("2026-01-02", 20100, 2000, 10.0500, 0.0500, 0.50),
        ("2026-01-03", 20200, 2000, 10.1000, 0.0500, 0.50),
        ("2026-02-01", 21000, 2000, 10.5000, 0.0200, 0.19),
        ("2026-02-20", 22000, 2000, 11.0000, 0.0500, 0.46),
        ("2026-02-21", 22100, 2000, 11.0500, 0.0500, 0.45),
    ]
    cursor.executemany(
        "INSERT INTO daily_nav (date, total_portfolio_value, total_shares, nav_per_share, daily_change_value, daily_change_percent) VALUES (?,?,?,?,?,?)",
        nav_rows,
    )

    # Investors
    cursor.execute(
        "INSERT INTO investors VALUES (?, ?, ?, ?, ?, ?)",
        ("20260101-01A", "Test A", "a@test.com", 1000, 10000, "Active"),
    )
    cursor.execute(
        "INSERT INTO investors VALUES (?, ?, ?, ?, ?, ?)",
        ("20260101-02A", "Test B", "b@test.com", 1000, 10000, "Active"),
    )

    # Trades
    cursor.execute(
        "INSERT INTO trades (date, trade_type, symbol, quantity, price, amount, category) VALUES (?,?,?,?,?,?,?)",
        ("2026-02-21", "buy_to_open", "AAPL", 10, 175, -1750, "Trade"),
    )

    conn.commit()
    conn.close()
    return db_path


# ============================================================
# NAV data queries
# ============================================================

class TestGetNavHistory:
    def test_returns_correct_count(self, nav_db):
        with patch("scripts.discord.update_nav_message.DB_PATH", nav_db):
            history = get_nav_history(days=3)
            assert len(history) == 3

    def test_ordered_oldest_first(self, nav_db):
        with patch("scripts.discord.update_nav_message.DB_PATH", nav_db):
            history = get_nav_history(days=10)
            dates = [h["date"] for h in history]
            assert dates == sorted(dates)

    def test_has_required_keys(self, nav_db):
        with patch("scripts.discord.update_nav_message.DB_PATH", nav_db):
            history = get_nav_history(days=1)
            assert "date" in history[0]
            assert "nav_per_share" in history[0]


class TestGetCurrentNavData:
    def test_returns_latest_nav(self, nav_db):
        with patch("scripts.discord.update_nav_message.DB_PATH", nav_db):
            data = get_current_nav_data()
            assert data is not None
            assert data["date"] == "2026-02-21"
            assert data["nav_per_share"] == 11.0500

    def test_inception_return_calculated(self, nav_db):
        with patch("scripts.discord.update_nav_message.DB_PATH", nav_db):
            data = get_current_nav_data()
            # First NAV: 10.0, Latest: 11.05 → 10.5% return
            expected = ((11.05 - 10.0) / 10.0) * 100
            assert data["inception_return"] == pytest.approx(expected)

    def test_investor_count(self, nav_db):
        with patch("scripts.discord.update_nav_message.DB_PATH", nav_db):
            data = get_current_nav_data()
            assert data["investor_count"] == 2

    def test_trading_days(self, nav_db):
        with patch("scripts.discord.update_nav_message.DB_PATH", nav_db):
            data = get_current_nav_data()
            assert data["trading_days"] == 6


class TestGetTradeCounts:
    def test_returns_trade_counts(self, nav_db):
        with patch("scripts.discord.update_nav_message.DB_PATH", nav_db):
            counts = get_trade_counts(days=30)
            assert len(counts) >= 1
            assert counts[0]["trade_count"] == 1


# ============================================================
# Embed building
# ============================================================

class TestBuildNavEmbed:
    @pytest.fixture
    def sample_nav_data(self):
        return {
            "date": "2026-02-21",
            "nav_per_share": 11.0500,
            "total_portfolio_value": 22100,
            "total_shares": 2000,
            "daily_change_value": 0.0500,
            "daily_change_percent": 0.45,
            "inception_return": 10.5,
            "inception_nav": 10.0,
            "trading_days": 38,
            "investor_count": 5,
        }

    def test_positive_day_is_green(self, sample_nav_data):
        embed = build_nav_embed(sample_nav_data)
        assert embed.colour.value == 0x2ECC71  # discord.Colour.green()

    def test_negative_day_is_red(self, sample_nav_data):
        sample_nav_data["daily_change_percent"] = -1.5
        sample_nav_data["daily_change_value"] = -0.15
        embed = build_nav_embed(sample_nav_data)
        assert embed.colour == discord.Colour.red()

    def test_has_nav_field(self, sample_nav_data):
        embed = build_nav_embed(sample_nav_data)
        field_names = [f.name for f in embed.fields]
        assert "NAV/Share" in field_names

    def test_has_daily_change_field(self, sample_nav_data):
        embed = build_nav_embed(sample_nav_data)
        field_names = [f.name for f in embed.fields]
        assert "Daily Change" in field_names

    def test_has_inception_field(self, sample_nav_data):
        embed = build_nav_embed(sample_nav_data)
        field_names = [f.name for f in embed.fields]
        assert "Since Inception" in field_names

    def test_chart_image_attached(self, sample_nav_data):
        embed = build_nav_embed(sample_nav_data, chart_filename="nav_chart.png")
        assert embed.image.url == "attachment://nav_chart.png"

    def test_footer_present(self, sample_nav_data):
        embed = build_nav_embed(sample_nav_data)
        assert "Tovito Trader" in embed.footer.text

    def test_title_present(self, sample_nav_data):
        embed = build_nav_embed(sample_nav_data)
        assert "NAV" in embed.title


# ============================================================
# Pinned message finder
# ============================================================

class TestFindBotPinnedMessage:
    @pytest.mark.asyncio
    async def test_finds_bot_message(self):
        bot_msg = MagicMock()
        bot_msg.author.id = 12345
        other_msg = MagicMock()
        other_msg.author.id = 99999

        channel = MagicMock()
        channel.pins.return_value = _AsyncPinIterator([other_msg, bot_msg])

        result = await find_bot_pinned_message(channel, 12345)
        assert result == bot_msg

    @pytest.mark.asyncio
    async def test_returns_none_when_no_match(self):
        other_msg = MagicMock()
        other_msg.author.id = 99999

        channel = MagicMock()
        channel.pins.return_value = _AsyncPinIterator([other_msg])

        result = await find_bot_pinned_message(channel, 12345)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_pins(self):
        channel = MagicMock()
        channel.pins.return_value = _AsyncPinIterator([])

        result = await find_bot_pinned_message(channel, 12345)
        assert result is None


# ============================================================
# Synchronous entry point
# ============================================================

class TestUpdateNavMessage:
    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "", "DISCORD_NAV_CHANNEL_ID": ""})
    def test_missing_token_returns_false(self):
        with patch("scripts.discord.update_nav_message.BOT_TOKEN", ""):
            result = update_nav_message()
            assert result is False

    @patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "fake-token", "DISCORD_NAV_CHANNEL_ID": ""})
    def test_missing_channel_returns_false(self):
        with patch("scripts.discord.update_nav_message.BOT_TOKEN", "fake-token"), \
             patch("scripts.discord.update_nav_message.CHANNEL_ID", ""):
            result = update_nav_message()
            assert result is False

    def test_invalid_channel_id_returns_false(self):
        with patch("scripts.discord.update_nav_message.BOT_TOKEN", "fake-token"), \
             patch("scripts.discord.update_nav_message.CHANNEL_ID", "not-a-number"):
            result = update_nav_message()
            assert result is False
