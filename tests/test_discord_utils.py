"""
Tests for Discord utility module and related automations.

Covers:
- Shared discord utility (src/utils/discord.py)
- Monthly performance summary (scripts/reporting/discord_monthly_summary.py)
- Channel setup content (scripts/discord/setup_channels.py)
"""

import pytest
import sqlite3
import os
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path

import sys

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from src.utils.discord import (
    post_embed,
    post_embeds,
    make_embed,
    utc_timestamp,
    COLORS,
    FOOTER,
)
from scripts.reporting.discord_monthly_summary import (
    get_monthly_performance,
    get_inception_return,
    build_monthly_embed,
)
from scripts.discord.setup_channels import (
    get_welcome_embeds,
    get_about_embeds,
    get_faq_embeds,
    get_rules_embeds,
    CHANNEL_MAP,
)


# ============================================================
# Shared Discord Utilities
# ============================================================

class TestMakeEmbed:
    """Test embed builder."""

    def test_basic_embed(self):
        embed = make_embed("Test Title", color=COLORS["blue"])
        assert embed["title"] == "Test Title"
        assert embed["color"] == COLORS["blue"]
        assert "timestamp" in embed
        assert embed["footer"]["text"] == "Tovito Trader"

    def test_with_description(self):
        embed = make_embed("T", description="Hello world")
        assert embed["description"] == "Hello world"

    def test_without_description(self):
        embed = make_embed("T")
        assert "description" not in embed

    def test_with_fields(self):
        fields = [{"name": "A", "value": "1", "inline": True}]
        embed = make_embed("T", fields=fields)
        assert embed["fields"] == fields

    def test_custom_footer(self):
        embed = make_embed("T", footer="Custom Footer")
        assert embed["footer"]["text"] == "Custom Footer"


class TestUtcTimestamp:
    """Test timestamp generation."""

    def test_format(self):
        ts = utc_timestamp()
        assert ts.endswith("Z")
        assert "T" in ts
        assert len(ts) == 20  # YYYY-MM-DDTHH:MM:SSZ


class TestPostEmbed:
    """Test Discord webhook posting."""

    @patch("src.utils.discord.requests.post")
    def test_success(self, mock_post):
        mock_post.return_value = MagicMock(status_code=204)
        mock_post.return_value.raise_for_status = MagicMock()

        result = post_embed("https://example.com/webhook", {"title": "Test"})
        assert result is True
        mock_post.assert_called_once()

    @patch("src.utils.discord.requests.post")
    def test_with_content(self, mock_post):
        mock_post.return_value = MagicMock(status_code=204)
        mock_post.return_value.raise_for_status = MagicMock()

        post_embed("https://example.com/webhook", {"title": "T"}, content="@everyone")
        payload = mock_post.call_args[1]["json"]
        assert payload["content"] == "@everyone"

    def test_no_url_returns_false(self):
        result = post_embed("", {"title": "Test"})
        assert result is False

    @patch("src.utils.discord.requests.post")
    def test_rate_limit_retry(self, mock_post):
        rate_resp = MagicMock(status_code=429)
        rate_resp.json.return_value = {"retry_after": 0.01}
        ok_resp = MagicMock(status_code=204)
        ok_resp.raise_for_status = MagicMock()
        mock_post.side_effect = [rate_resp, ok_resp]

        result = post_embed("https://example.com/webhook", {"title": "T"})
        assert result is True
        assert mock_post.call_count == 2


class TestPostEmbeds:
    """Test multiple embed posting."""

    @patch("src.utils.discord.requests.post")
    def test_single_batch(self, mock_post):
        mock_post.return_value = MagicMock(status_code=204)
        mock_post.return_value.raise_for_status = MagicMock()

        embeds = [{"title": f"T{i}"} for i in range(5)]
        result = post_embeds("https://example.com/webhook", embeds)
        assert result is True
        # 5 embeds < 10 limit, so 1 call
        assert mock_post.call_count == 1

    @patch("src.utils.discord.requests.post")
    def test_multiple_batches(self, mock_post):
        mock_post.return_value = MagicMock(status_code=204)
        mock_post.return_value.raise_for_status = MagicMock()

        embeds = [{"title": f"T{i}"} for i in range(15)]
        result = post_embeds("https://example.com/webhook", embeds)
        assert result is True
        # 15 embeds = 2 batches (10 + 5)
        assert mock_post.call_count == 2

    def test_no_url_returns_false(self):
        result = post_embeds("", [{"title": "T"}])
        assert result is False


# ============================================================
# Monthly Performance Summary
# ============================================================

@pytest.fixture
def perf_db():
    """Create an in-memory database with NAV data for testing."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE daily_nav (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL UNIQUE,
            total_portfolio_value REAL NOT NULL,
            total_shares REAL NOT NULL,
            nav_per_share REAL NOT NULL
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

    # Seed January 2026 NAV data
    nav_data = [
        ("2026-01-01", 20000, 2000, 10.0000),
        ("2026-01-02", 20200, 2000, 10.1000),
        ("2026-01-15", 20500, 2000, 10.2500),
        ("2026-01-31", 21000, 2000, 10.5000),
    ]
    cursor.executemany(
        "INSERT INTO daily_nav (date, total_portfolio_value, total_shares, nav_per_share) VALUES (?,?,?,?)",
        nav_data,
    )

    # February data
    nav_data_feb = [
        ("2026-02-02", 21200, 2000, 10.6000),
        ("2026-02-15", 21500, 2000, 10.7500),
        ("2026-02-20", 22000, 2000, 11.0000),
    ]
    cursor.executemany(
        "INSERT INTO daily_nav (date, total_portfolio_value, total_shares, nav_per_share) VALUES (?,?,?,?)",
        nav_data_feb,
    )

    # Investors
    cursor.execute(
        "INSERT INTO investors (investor_id, name, email, current_shares, net_investment, status) VALUES (?,?,?,?,?,?)",
        ("20260101-01A", "Test A", "a@test.com", 1000, 10000, "Active"),
    )
    cursor.execute(
        "INSERT INTO investors (investor_id, name, email, current_shares, net_investment, status) VALUES (?,?,?,?,?,?)",
        ("20260101-02A", "Test B", "b@test.com", 1000, 10000, "Active"),
    )

    # Trades
    trades = [
        ("2026-01-05", "buy_to_open", "AAPL", 10, 175, -1750, "Trade"),
        ("2026-01-10", "sell_to_close", "AAPL", 10, 180, 1800, "Trade"),
        ("2026-01-20", "buy", "TSLA", 5, 200, -1000, "Trade"),
    ]
    cursor.executemany(
        "INSERT INTO trades (date, trade_type, symbol, quantity, price, amount, category) VALUES (?,?,?,?,?,?,?)",
        trades,
    )

    conn.commit()
    yield cursor
    conn.close()


class TestMonthlyPerformance:
    """Test monthly performance data retrieval."""

    def test_january_performance(self, perf_db):
        perf = get_monthly_performance(perf_db, 2026, 1)
        assert perf is not None
        assert perf["month_name"] == "January"
        assert perf["year"] == 2026
        assert perf["start_nav"] == 10.0  # Jan 1
        assert perf["end_nav"] == 10.5    # Jan 31
        assert perf["nav_change_pct"] == pytest.approx(5.0)
        assert perf["trading_days"] == 4
        assert perf["total_trades"] == 3
        assert perf["investor_count"] == 2
        assert perf["high_nav"] == 10.5
        assert perf["low_nav"] == 10.0

    def test_february_performance(self, perf_db):
        perf = get_monthly_performance(perf_db, 2026, 2)
        assert perf is not None
        assert perf["month_name"] == "February"
        assert perf["start_nav"] == 10.5  # Last day of Jan
        assert perf["end_nav"] == 11.0    # Feb 20 (last entry)
        assert perf["nav_change_pct"] == pytest.approx(100 * (11.0 - 10.5) / 10.5)

    def test_no_data_returns_none(self, perf_db):
        perf = get_monthly_performance(perf_db, 2026, 12)
        assert perf is None

    def test_inception_return(self, perf_db):
        ret = get_inception_return(perf_db)
        # First NAV: 10.0, Last NAV: 11.0 → 10%
        assert ret == pytest.approx(10.0)


class TestMonthlyEmbed:
    """Test embed generation for monthly summary."""

    def test_positive_month_is_green(self, perf_db):
        perf = get_monthly_performance(perf_db, 2026, 1)
        embed = build_monthly_embed(perf, 10.0)
        assert embed["color"] == COLORS["green"]

    def test_embed_has_key_fields(self, perf_db):
        perf = get_monthly_performance(perf_db, 2026, 1)
        embed = build_monthly_embed(perf, 10.0)
        field_names = {f["name"] for f in embed["fields"]}
        assert "Monthly Return" in field_names
        assert "Inception Return" in field_names
        assert "NAV/Share" in field_names
        assert "Trading Days" in field_names
        assert "Trades Executed" in field_names
        assert "Active Investors" in field_names

    def test_title_contains_month_year(self, perf_db):
        perf = get_monthly_performance(perf_db, 2026, 1)
        embed = build_monthly_embed(perf, 10.0)
        assert "January" in embed["title"]
        assert "2026" in embed["title"]


# ============================================================
# Channel Setup Content
# ============================================================

class TestChannelContent:
    """Test that channel content generates valid embeds."""

    def test_welcome_embeds_not_empty(self):
        embeds = get_welcome_embeds()
        assert len(embeds) >= 3
        for embed in embeds:
            assert "title" in embed
            assert "color" in embed

    def test_welcome_points_to_channels(self):
        embeds = get_welcome_embeds()
        # The "Find Your Way Around" embed should reference other channels
        all_text = " ".join(
            embed.get("description", "") for embed in embeds
        )
        assert "#about-tovito" in all_text
        assert "#faq" in all_text
        assert "#rules-and-disclaimers" in all_text
        assert "#tovito-trader-trades" in all_text

    def test_welcome_channel_in_map(self):
        assert "welcome" in CHANNEL_MAP
        assert CHANNEL_MAP["welcome"]["env_key"] == "DISCORD_WELCOME_WEBHOOK_URL"

    def test_about_embeds_not_empty(self):
        embeds = get_about_embeds()
        assert len(embeds) >= 2
        for embed in embeds:
            assert "title" in embed
            assert "color" in embed

    def test_faq_embeds_not_empty(self):
        embeds = get_faq_embeds()
        assert len(embeds) >= 3
        for embed in embeds:
            assert "title" in embed

    def test_rules_embeds_not_empty(self):
        embeds = get_rules_embeds()
        assert len(embeds) >= 2
        for embed in embeds:
            assert "title" in embed

    def test_channel_map_has_required_keys(self):
        for key, info in CHANNEL_MAP.items():
            assert "name" in info
            assert "env_key" in info
            assert "builder" in info
            assert callable(info["builder"])

    def test_all_builders_return_lists(self):
        for key, info in CHANNEL_MAP.items():
            result = info["builder"]()
            assert isinstance(result, list)
            assert len(result) > 0
