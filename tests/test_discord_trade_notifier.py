"""
Tests for the Discord Trade Notifier service.

Covers:
- Trade filtering logic (only opening/closing trades)
- Deduplication (same trade ID not posted twice)
- Warm-up behaviour (no posts on startup)
- Embed formatting (correct colours, fields)
- Market hours check logic
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, time as dt_time

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from scripts.trading.discord_trade_notifier import (
    is_trading_trade,
    is_market_hours,
    format_embed,
    post_to_discord,
    TradeNotifier,
    OPENING_TYPES,
    CLOSING_TYPES,
    TRADING_TYPES,
    COLOR_OPEN,
    COLOR_CLOSE,
)


# ============================================================
# Test data factories
# ============================================================

def make_trade(
    txn_type="buy_to_open",
    symbol="AAPL",
    quantity=10,
    price=175.50,
    amount=-1755.00,
    option_type=None,
    strike=None,
    expiration_date=None,
    brokerage_id="txn-001",
    category="Trade",
    subcategory="Stock Buy",
):
    return {
        "date": "2026-02-21",
        "transaction_type": txn_type,
        "symbol": symbol,
        "quantity": quantity,
        "price": price,
        "amount": amount,
        "commission": 0.0,
        "fees": 0.0,
        "option_type": option_type,
        "strike": strike,
        "expiration_date": expiration_date,
        "description": f"{txn_type} {symbol}",
        "brokerage_transaction_id": brokerage_id,
        "category": category,
        "subcategory": subcategory,
    }


# ============================================================
# Trade filtering
# ============================================================

class TestTradeFiltering:
    """Test that only opening/closing trades pass the filter."""

    @pytest.mark.parametrize("txn_type", [
        "buy", "sell",
        "buy_to_open", "sell_to_open",
        "buy_to_close", "sell_to_close",
    ])
    def test_trading_types_pass(self, txn_type):
        txn = make_trade(txn_type=txn_type)
        assert is_trading_trade(txn) is True

    @pytest.mark.parametrize("txn_type", [
        "dividend", "interest", "ach", "fee", "journal", "other",
    ])
    def test_non_trading_types_rejected(self, txn_type):
        txn = make_trade(txn_type=txn_type)
        assert is_trading_trade(txn) is False

    def test_empty_type_rejected(self):
        txn = make_trade(txn_type="")
        assert is_trading_trade(txn) is False

    def test_missing_type_rejected(self):
        txn = {"symbol": "AAPL", "amount": -100}
        assert is_trading_trade(txn) is False

    def test_case_insensitive(self):
        txn = make_trade(txn_type="Buy_To_Open")
        assert is_trading_trade(txn) is True


# ============================================================
# Embed formatting
# ============================================================

class TestEmbedFormatting:
    """Test Discord embed generation."""

    def test_opening_trade_green(self):
        txn = make_trade(txn_type="buy_to_open")
        embed = format_embed(txn, "tastytrade")
        assert embed["color"] == COLOR_OPEN

    def test_closing_trade_red(self):
        txn = make_trade(txn_type="sell_to_close")
        embed = format_embed(txn, "tastytrade")
        assert embed["color"] == COLOR_CLOSE

    def test_embed_has_required_fields(self):
        txn = make_trade()
        embed = format_embed(txn, "tastytrade")
        assert "title" in embed
        assert "color" in embed
        assert "fields" in embed
        assert "timestamp" in embed
        assert "footer" in embed

    def test_embed_title_contains_symbol(self):
        txn = make_trade(symbol="TSLA")
        embed = format_embed(txn, "tastytrade")
        assert "TSLA" in embed["title"]

    def test_embed_title_contains_action(self):
        txn = make_trade(txn_type="sell_to_close")
        embed = format_embed(txn, "tastytrade")
        assert "SELL TO CLOSE" in embed["title"]

    def test_option_trade_includes_strike_and_expiry(self):
        txn = make_trade(
            txn_type="buy_to_open",
            symbol="AAPL",
            option_type="call",
            strike=180.0,
            expiration_date="2026-03-21",
        )
        embed = format_embed(txn, "tastytrade")
        assert "180C" in embed["title"]
        assert "2026-03-21" in embed["title"]

    def test_source_in_fields(self):
        txn = make_trade()
        embed = format_embed(txn, "tradier")
        source_fields = [f for f in embed["fields"] if f["name"] == "Source"]
        assert len(source_fields) == 1
        assert source_fields[0]["value"] == "Tradier"

    def test_footer_text(self):
        txn = make_trade()
        embed = format_embed(txn, "tastytrade")
        assert embed["footer"]["text"] == "Tovito Trader"

    def test_equity_buy_is_green(self):
        txn = make_trade(txn_type="buy")
        embed = format_embed(txn, "tastytrade")
        assert embed["color"] == COLOR_OPEN

    def test_equity_sell_is_red(self):
        txn = make_trade(txn_type="sell")
        embed = format_embed(txn, "tastytrade")
        assert embed["color"] == COLOR_CLOSE


# ============================================================
# Deduplication
# ============================================================

class TestDeduplication:
    """Test that the same trade is never posted twice."""

    @patch("scripts.trading.discord_trade_notifier.post_to_discord", return_value=True)
    @patch("scripts.trading.discord_trade_notifier.get_all_brokerage_clients")
    def test_same_trade_not_posted_twice(self, mock_clients, mock_post):
        trade = make_trade(brokerage_id="txn-100")
        mock_client = MagicMock()
        mock_client.get_transactions.return_value = [trade]
        mock_clients.return_value = {"tastytrade": mock_client}

        notifier = TradeNotifier()
        notifier._clients = {"tastytrade": mock_client}

        # First cycle — should post
        count1 = notifier.poll_cycle()
        assert count1 == 1

        # Second cycle — same trade, should not post again
        count2 = notifier.poll_cycle()
        assert count2 == 0
        assert mock_post.call_count == 1

    @patch("scripts.trading.discord_trade_notifier.post_to_discord", return_value=True)
    @patch("scripts.trading.discord_trade_notifier.get_all_brokerage_clients")
    def test_different_trades_both_posted(self, mock_clients, mock_post):
        trade1 = make_trade(brokerage_id="txn-100")
        trade2 = make_trade(brokerage_id="txn-101", txn_type="sell_to_close")

        mock_client = MagicMock()
        mock_client.get_transactions.side_effect = [
            [trade1],
            [trade1, trade2],
        ]
        mock_clients.return_value = {"tastytrade": mock_client}

        notifier = TradeNotifier()
        notifier._clients = {"tastytrade": mock_client}

        count1 = notifier.poll_cycle()
        assert count1 == 1

        count2 = notifier.poll_cycle()
        assert count2 == 1
        assert mock_post.call_count == 2

    @patch("scripts.trading.discord_trade_notifier.post_to_discord", return_value=True)
    def test_same_id_different_sources_both_posted(self, mock_post):
        """Same brokerage_transaction_id from different sources are distinct."""
        trade = make_trade(brokerage_id="txn-100")

        mock_tt = MagicMock()
        mock_tt.get_transactions.return_value = [trade]
        mock_tradier = MagicMock()
        mock_tradier.get_transactions.return_value = [trade]

        notifier = TradeNotifier()
        notifier._clients = {"tastytrade": mock_tt, "tradier": mock_tradier}

        count = notifier.poll_cycle()
        assert count == 2  # Same ID, different sources = 2 posts


# ============================================================
# Warm-up
# ============================================================

class TestWarmUp:
    """Test that warm-up populates seen-set without posting."""

    @patch("scripts.trading.discord_trade_notifier.post_to_discord", return_value=True)
    @patch("scripts.trading.discord_trade_notifier.log_to_db")
    def test_warm_up_does_not_post(self, mock_log_db, mock_post):
        trade = make_trade(brokerage_id="txn-200")
        mock_client = MagicMock()
        mock_client.get_transactions.return_value = [trade]

        notifier = TradeNotifier()
        notifier._clients = {"tastytrade": mock_client}

        notifier.warm_up()

        # Should NOT have posted anything
        mock_post.assert_not_called()

        # But seen-set should be populated
        assert ("tastytrade", "txn-200") in notifier.seen

    @patch("scripts.trading.discord_trade_notifier.post_to_discord", return_value=True)
    @patch("scripts.trading.discord_trade_notifier.log_to_db")
    def test_warm_up_then_poll_skips_existing(self, mock_log_db, mock_post):
        trade = make_trade(brokerage_id="txn-200")
        mock_client = MagicMock()
        mock_client.get_transactions.return_value = [trade]

        notifier = TradeNotifier()
        notifier._clients = {"tastytrade": mock_client}

        notifier.warm_up()
        count = notifier.poll_cycle()

        assert count == 0
        mock_post.assert_not_called()

    @patch("scripts.trading.discord_trade_notifier.post_to_discord", return_value=True)
    @patch("scripts.trading.discord_trade_notifier.log_to_db")
    def test_warm_up_ignores_non_trading(self, mock_log_db, mock_post):
        dividend = make_trade(txn_type="dividend", brokerage_id="div-001")
        mock_client = MagicMock()
        mock_client.get_transactions.return_value = [dividend]

        notifier = TradeNotifier()
        notifier._clients = {"tastytrade": mock_client}

        notifier.warm_up()
        assert len(notifier.seen) == 0


# ============================================================
# Market hours
# ============================================================

class TestMarketHours:
    """Test market hours detection."""

    @patch("scripts.trading.discord_trade_notifier._now_et")
    def test_weekday_during_market(self, mock_now):
        # Wednesday 10:30 AM ET
        mock_now.return_value = datetime(2026, 2, 18, 10, 30)
        assert is_market_hours() is True

    @patch("scripts.trading.discord_trade_notifier._now_et")
    def test_weekday_before_market(self, mock_now):
        # Wednesday 8:00 AM ET
        mock_now.return_value = datetime(2026, 2, 18, 8, 0)
        assert is_market_hours() is False

    @patch("scripts.trading.discord_trade_notifier._now_et")
    def test_weekday_after_market(self, mock_now):
        # Wednesday 5:00 PM ET
        mock_now.return_value = datetime(2026, 2, 18, 17, 0)
        assert is_market_hours() is False

    @patch("scripts.trading.discord_trade_notifier._now_et")
    def test_saturday_rejected(self, mock_now):
        # Saturday 11:00 AM ET
        mock_now.return_value = datetime(2026, 2, 21, 11, 0)
        assert is_market_hours() is False

    @patch("scripts.trading.discord_trade_notifier._now_et")
    def test_sunday_rejected(self, mock_now):
        # Sunday 11:00 AM ET
        mock_now.return_value = datetime(2026, 2, 22, 11, 0)
        assert is_market_hours() is False

    @patch("scripts.trading.discord_trade_notifier._now_et")
    def test_edge_market_open(self, mock_now):
        # 9:25 AM ET — within our wider window
        mock_now.return_value = datetime(2026, 2, 18, 9, 25)
        assert is_market_hours() is True

    @patch("scripts.trading.discord_trade_notifier._now_et")
    def test_edge_market_close(self, mock_now):
        # 4:30 PM ET — within our wider window
        mock_now.return_value = datetime(2026, 2, 18, 16, 30)
        assert is_market_hours() is True


# ============================================================
# Discord posting
# ============================================================

class TestDiscordPosting:
    """Test webhook interaction."""

    @patch("scripts.trading.discord_trade_notifier.requests.post")
    def test_successful_post(self, mock_post):
        mock_post.return_value = MagicMock(status_code=204)
        mock_post.return_value.raise_for_status = MagicMock()

        embed = format_embed(make_trade(), "tastytrade")
        result = post_to_discord(embed, webhook_url="https://example.com/webhook")
        assert result is True
        mock_post.assert_called_once()

    @patch("scripts.trading.discord_trade_notifier.requests.post")
    def test_rate_limited_retries(self, mock_post):
        # First call rate-limited, second succeeds
        rate_resp = MagicMock(status_code=429)
        rate_resp.json.return_value = {"retry_after": 0.1}

        ok_resp = MagicMock(status_code=204)
        ok_resp.raise_for_status = MagicMock()

        mock_post.side_effect = [rate_resp, ok_resp]

        embed = format_embed(make_trade(), "tastytrade")
        result = post_to_discord(embed, webhook_url="https://example.com/webhook")
        assert result is True
        assert mock_post.call_count == 2

    def test_no_webhook_url_returns_false(self):
        embed = format_embed(make_trade(), "tastytrade")
        result = post_to_discord(embed, webhook_url="")
        assert result is False

    @patch("scripts.trading.discord_trade_notifier.requests.post")
    def test_network_error_retries_and_fails(self, mock_post):
        import requests as req
        mock_post.side_effect = req.ConnectionError("network down")

        embed = format_embed(make_trade(), "tastytrade")
        result = post_to_discord(embed, webhook_url="https://example.com/webhook")
        assert result is False
        assert mock_post.call_count == 3  # 3 retry attempts


# ============================================================
# Error resilience
# ============================================================

class TestErrorResilience:
    """Test that API failures don't crash the service."""

    def test_poll_cycle_survives_api_error(self):
        mock_client = MagicMock()
        mock_client.get_transactions.side_effect = Exception("API timeout")

        notifier = TradeNotifier()
        notifier._clients = {"tastytrade": mock_client}

        # Should not raise
        count = notifier.poll_cycle()
        assert count == 0

    @patch("scripts.trading.discord_trade_notifier.log_to_db")
    def test_warm_up_survives_api_error(self, mock_log_db):
        mock_client = MagicMock()
        mock_client.get_transactions.side_effect = Exception("API timeout")

        notifier = TradeNotifier()
        notifier._clients = {"tastytrade": mock_client}

        # Should not raise
        notifier.warm_up()
        assert len(notifier.seen) == 0

    @patch("scripts.trading.discord_trade_notifier.post_to_discord", return_value=False)
    def test_discord_failure_does_not_crash(self, mock_post):
        trade = make_trade(brokerage_id="txn-300")
        mock_client = MagicMock()
        mock_client.get_transactions.return_value = [trade]

        notifier = TradeNotifier()
        notifier._clients = {"tastytrade": mock_client}

        count = notifier.poll_cycle()
        # Trade was attempted but Discord failed — count is 0
        assert count == 0
        # Trade should still be in seen-set so we don't spam retries
        assert ("tastytrade", "txn-300") in notifier.seen
