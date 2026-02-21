"""
Test Brokerage Factory and Protocol
=====================================
Unit tests for the brokerage client factory function
and BrokerageClient protocol compliance.

Tests verify:
- Factory returns correct client type based on provider string
- Factory reads BROKERAGE_PROVIDER env var as default
- Factory raises on unknown provider
- Both TradierClient and TastyTradeClient satisfy BrokerageClient protocol
"""

import pytest
from unittest.mock import patch


class TestBrokerageFactory:
    """Test the get_brokerage_client factory function."""

    @patch.dict('os.environ', {
        'TRADIER_API_KEY': 'test_key',
        'TRADIER_ACCOUNT_ID': 'test_account',
    })
    def test_factory_returns_tradier_for_tradier_provider(self):
        """Factory should return TradierClient when provider is 'tradier'."""
        from src.api.brokerage import get_brokerage_client
        from src.api.tradier import TradierClient

        client = get_brokerage_client('tradier')
        assert isinstance(client, TradierClient)

    @patch.dict('os.environ', {
        'TASTYTRADE_CLIENT_SECRET': 'test_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_factory_returns_tastytrade_for_tastytrade_provider(self):
        """Factory should return TastyTradeClient when provider is 'tastytrade'."""
        from src.api.brokerage import get_brokerage_client
        from src.api.tastytrade_client import TastyTradeClient

        client = get_brokerage_client('tastytrade')
        assert isinstance(client, TastyTradeClient)

    def test_factory_raises_on_unknown_provider(self):
        """Factory should raise ValueError for unsupported provider."""
        from src.api.brokerage import get_brokerage_client

        with pytest.raises(ValueError, match="Unknown brokerage provider"):
            get_brokerage_client('robinhood')

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDER': 'tradier',
        'TRADIER_API_KEY': 'test_key',
        'TRADIER_ACCOUNT_ID': 'test_account',
    })
    def test_factory_reads_env_var_default(self):
        """Factory should use BROKERAGE_PROVIDER env var when no arg given."""
        from src.api.brokerage import get_brokerage_client
        from src.api.tradier import TradierClient

        client = get_brokerage_client()  # No argument
        assert isinstance(client, TradierClient)

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDER': 'tastytrade',
        'TASTYTRADE_CLIENT_SECRET': 'test_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_factory_env_var_tastytrade(self):
        """Factory should return TastyTradeClient from env var."""
        from src.api.brokerage import get_brokerage_client
        from src.api.tastytrade_client import TastyTradeClient

        client = get_brokerage_client()  # No argument, reads env
        assert isinstance(client, TastyTradeClient)

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDER': '  TastyTrade  ',
        'TASTYTRADE_CLIENT_SECRET': 'test_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_factory_handles_whitespace_and_case(self):
        """Factory should handle whitespace and mixed case in provider name."""
        from src.api.brokerage import get_brokerage_client
        from src.api.tastytrade_client import TastyTradeClient

        client = get_brokerage_client()
        assert isinstance(client, TastyTradeClient)

    @patch.dict('os.environ', {}, clear=True)
    def test_factory_defaults_to_tradier_when_no_env(self):
        """Factory should default to 'tradier' when env var is not set."""
        from src.api.brokerage import get_brokerage_client

        # This will fail because Tradier creds are missing,
        # but it should attempt Tradier (not TastyTrade)
        with pytest.raises(ValueError, match="Tradier API credentials"):
            get_brokerage_client()


class TestBrokerageProtocol:
    """Test that clients satisfy the BrokerageClient protocol."""

    def test_tradier_satisfies_protocol(self):
        """TradierClient should satisfy BrokerageClient protocol."""
        from src.api.brokerage import BrokerageClient
        from src.api.tradier import TradierClient

        # Check structural subtyping (has required methods)
        assert hasattr(TradierClient, 'get_account_balance')
        assert hasattr(TradierClient, 'get_positions')
        assert hasattr(TradierClient, 'is_market_open')

    def test_tastytrade_satisfies_protocol(self):
        """TastyTradeClient should satisfy BrokerageClient protocol."""
        from src.api.brokerage import BrokerageClient
        from src.api.tastytrade_client import TastyTradeClient

        assert hasattr(TastyTradeClient, 'get_account_balance')
        assert hasattr(TastyTradeClient, 'get_positions')
        assert hasattr(TastyTradeClient, 'is_market_open')

    @patch.dict('os.environ', {
        'TASTYTRADE_CLIENT_SECRET': 'test_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_tastytrade_runtime_checkable(self):
        """TastyTradeClient instance should pass isinstance check."""
        from src.api.brokerage import BrokerageClient
        from src.api.tastytrade_client import TastyTradeClient

        client = TastyTradeClient()
        assert isinstance(client, BrokerageClient)

    @patch.dict('os.environ', {
        'TRADIER_API_KEY': 'test_key',
        'TRADIER_ACCOUNT_ID': 'test_account',
    })
    def test_tradier_runtime_checkable(self):
        """TradierClient instance should pass isinstance check."""
        from src.api.brokerage import BrokerageClient
        from src.api.tradier import TradierClient

        client = TradierClient()
        assert isinstance(client, BrokerageClient)
