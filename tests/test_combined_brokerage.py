"""
Test Combined Brokerage NAV Aggregation
=========================================
Unit tests for multi-brokerage balance aggregation.

Tests verify:
- get_configured_providers() reads BROKERAGE_PROVIDERS correctly
- get_configured_providers() falls back to BROKERAGE_PROVIDER
- get_all_brokerage_clients() creates clients for all providers
- get_combined_balance() sums equity/cash across brokerages
- Fail-fast behavior when any brokerage fails
- Per-brokerage details preserved in combined result
- Backwards compatibility with single-provider mode
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestGetConfiguredProviders:
    """Test provider list configuration parsing."""

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDERS': 'tradier,tastytrade',
    })
    def test_reads_comma_separated_providers(self):
        """Should parse comma-separated BROKERAGE_PROVIDERS."""
        from src.api.brokerage import get_configured_providers

        providers = get_configured_providers()
        assert providers == ['tradier', 'tastytrade']

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDERS': '  Tradier , TastyTrade  ',
    })
    def test_handles_whitespace_and_case(self):
        """Should strip whitespace and lowercase provider names."""
        from src.api.brokerage import get_configured_providers

        providers = get_configured_providers()
        assert providers == ['tradier', 'tastytrade']

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDERS': 'tastytrade',
    })
    def test_single_provider_in_providers_list(self):
        """Should handle a single provider in BROKERAGE_PROVIDERS."""
        from src.api.brokerage import get_configured_providers

        providers = get_configured_providers()
        assert providers == ['tastytrade']

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDER': 'tradier',
    }, clear=True)
    def test_falls_back_to_single_provider(self):
        """Should fall back to BROKERAGE_PROVIDER when BROKERAGE_PROVIDERS is not set."""
        from src.api.brokerage import get_configured_providers

        providers = get_configured_providers()
        assert providers == ['tradier']

    @patch.dict('os.environ', {}, clear=True)
    def test_defaults_to_tradier_when_no_env(self):
        """Should default to tradier when no env vars are set."""
        from src.api.brokerage import get_configured_providers

        providers = get_configured_providers()
        assert providers == ['tradier']

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDERS': '',
        'BROKERAGE_PROVIDER': 'tastytrade',
    })
    def test_empty_providers_falls_back_to_single(self):
        """Should fall back to BROKERAGE_PROVIDER when BROKERAGE_PROVIDERS is empty."""
        from src.api.brokerage import get_configured_providers

        providers = get_configured_providers()
        assert providers == ['tastytrade']

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDERS': 'tradier,,tastytrade,',
    })
    def test_ignores_empty_entries(self):
        """Should ignore empty entries from extra commas."""
        from src.api.brokerage import get_configured_providers

        providers = get_configured_providers()
        assert providers == ['tradier', 'tastytrade']


class TestGetAllBrokerageClients:
    """Test multi-client factory function."""

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDERS': 'tradier,tastytrade',
        'TRADIER_API_KEY': 'test_key',
        'TRADIER_ACCOUNT_ID': 'test_account',
        'TASTYTRADE_CLIENT_SECRET': 'test_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_creates_both_clients(self):
        """Should create client instances for both providers."""
        from src.api.brokerage import get_all_brokerage_clients
        from src.api.tradier import TradierClient
        from src.api.tastytrade_client import TastyTradeClient

        clients = get_all_brokerage_clients()

        assert 'tradier' in clients
        assert 'tastytrade' in clients
        assert isinstance(clients['tradier'], TradierClient)
        assert isinstance(clients['tastytrade'], TastyTradeClient)

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDERS': 'tradier',
        'TRADIER_API_KEY': 'test_key',
        'TRADIER_ACCOUNT_ID': 'test_account',
    })
    def test_creates_single_client(self):
        """Should work with a single provider in the list."""
        from src.api.brokerage import get_all_brokerage_clients
        from src.api.tradier import TradierClient

        clients = get_all_brokerage_clients()

        assert len(clients) == 1
        assert isinstance(clients['tradier'], TradierClient)

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDERS': 'tradier,robinhood',
        'TRADIER_API_KEY': 'test_key',
        'TRADIER_ACCOUNT_ID': 'test_account',
    })
    def test_raises_on_unknown_provider(self):
        """Should raise ValueError when an unknown provider is in the list."""
        from src.api.brokerage import get_all_brokerage_clients

        with pytest.raises(ValueError, match="Failed to initialize brokerage client 'robinhood'"):
            get_all_brokerage_clients()

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDERS': 'tradier,tastytrade',
        'TRADIER_API_KEY': 'test_key',
        'TRADIER_ACCOUNT_ID': 'test_account',
        # Missing TastyTrade creds — should fail
    }, clear=True)
    def test_raises_when_provider_creds_missing(self):
        """Should raise ValueError when a provider's credentials are missing."""
        from src.api.brokerage import get_all_brokerage_clients

        with pytest.raises(ValueError, match="Failed to initialize"):
            get_all_brokerage_clients()


class TestGetCombinedBalance:
    """Test combined balance aggregation across multiple brokerages."""

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDERS': 'tradier,tastytrade',
        'TRADIER_API_KEY': 'test_key',
        'TRADIER_ACCOUNT_ID': 'test_account',
        'TASTYTRADE_CLIENT_SECRET': 'test_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_combined_balance_sums_equity(self):
        """Combined total_equity should be the sum of both brokerages."""
        from src.api.brokerage import get_combined_balance

        tradier_balance = {
            'total_equity': 25000.00,
            'total_cash': 8000.00,
            'timestamp': datetime.now(),
            'source': 'tradier',
        }
        tastytrade_balance = {
            'total_equity': 45000.00,
            'total_cash': 12000.00,
            'timestamp': datetime.now(),
            'source': 'tastytrade',
        }

        with patch('src.api.brokerage.get_all_brokerage_clients') as mock_clients:
            mock_tradier = MagicMock()
            mock_tradier.get_account_balance.return_value = tradier_balance
            mock_tastytrade = MagicMock()
            mock_tastytrade.get_account_balance.return_value = tastytrade_balance

            mock_clients.return_value = {
                'tradier': mock_tradier,
                'tastytrade': mock_tastytrade,
            }

            combined = get_combined_balance()

        assert combined['total_equity'] == 70000.00
        assert combined['total_cash'] == 20000.00

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDERS': 'tradier,tastytrade',
        'TRADIER_API_KEY': 'test_key',
        'TRADIER_ACCOUNT_ID': 'test_account',
        'TASTYTRADE_CLIENT_SECRET': 'test_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_combined_balance_has_timestamp(self):
        """Combined result should have a timestamp."""
        from src.api.brokerage import get_combined_balance

        with patch('src.api.brokerage.get_all_brokerage_clients') as mock_clients:
            mock_client = MagicMock()
            mock_client.get_account_balance.return_value = {
                'total_equity': 10000.00,
                'total_cash': 3000.00,
                'timestamp': datetime.now(),
                'source': 'mock',
            }
            mock_clients.return_value = {'tradier': mock_client}

            combined = get_combined_balance()

        assert 'timestamp' in combined
        assert isinstance(combined['timestamp'], datetime)

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDERS': 'tradier,tastytrade',
        'TRADIER_API_KEY': 'test_key',
        'TRADIER_ACCOUNT_ID': 'test_account',
        'TASTYTRADE_CLIENT_SECRET': 'test_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_combined_balance_source_lists_all_providers(self):
        """Source field should list all contributing providers."""
        from src.api.brokerage import get_combined_balance

        with patch('src.api.brokerage.get_all_brokerage_clients') as mock_clients:
            mock_tradier = MagicMock()
            mock_tradier.get_account_balance.return_value = {
                'total_equity': 25000.00, 'total_cash': 8000.00,
                'timestamp': datetime.now(), 'source': 'tradier',
            }
            mock_tastytrade = MagicMock()
            mock_tastytrade.get_account_balance.return_value = {
                'total_equity': 45000.00, 'total_cash': 12000.00,
                'timestamp': datetime.now(), 'source': 'tastytrade',
            }
            mock_clients.return_value = {
                'tradier': mock_tradier,
                'tastytrade': mock_tastytrade,
            }

            combined = get_combined_balance()

        assert 'tradier' in combined['source']
        assert 'tastytrade' in combined['source']

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDERS': 'tradier,tastytrade',
        'TRADIER_API_KEY': 'test_key',
        'TRADIER_ACCOUNT_ID': 'test_account',
        'TASTYTRADE_CLIENT_SECRET': 'test_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_combined_balance_preserves_per_broker_details(self):
        """brokerage_details should contain individual balance dicts."""
        from src.api.brokerage import get_combined_balance

        tradier_balance = {
            'total_equity': 25000.00, 'total_cash': 8000.00,
            'timestamp': datetime.now(), 'source': 'tradier',
        }
        tastytrade_balance = {
            'total_equity': 45000.00, 'total_cash': 12000.00,
            'timestamp': datetime.now(), 'source': 'tastytrade',
        }

        with patch('src.api.brokerage.get_all_brokerage_clients') as mock_clients:
            mock_tradier = MagicMock()
            mock_tradier.get_account_balance.return_value = tradier_balance
            mock_tastytrade = MagicMock()
            mock_tastytrade.get_account_balance.return_value = tastytrade_balance
            mock_clients.return_value = {
                'tradier': mock_tradier,
                'tastytrade': mock_tastytrade,
            }

            combined = get_combined_balance()

        details = combined['brokerage_details']
        assert details['tradier']['total_equity'] == 25000.00
        assert details['tastytrade']['total_equity'] == 45000.00

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDERS': 'tradier,tastytrade',
        'TRADIER_API_KEY': 'test_key',
        'TRADIER_ACCOUNT_ID': 'test_account',
        'TASTYTRADE_CLIENT_SECRET': 'test_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_fail_fast_when_one_brokerage_fails(self):
        """Should raise RuntimeError if any brokerage fails (no partial NAV)."""
        from src.api.brokerage import get_combined_balance

        with patch('src.api.brokerage.get_all_brokerage_clients') as mock_clients:
            mock_tradier = MagicMock()
            mock_tradier.get_account_balance.return_value = {
                'total_equity': 25000.00, 'total_cash': 8000.00,
                'timestamp': datetime.now(), 'source': 'tradier',
            }
            mock_tastytrade = MagicMock()
            mock_tastytrade.get_account_balance.side_effect = Exception("Connection timeout")

            mock_clients.return_value = {
                'tradier': mock_tradier,
                'tastytrade': mock_tastytrade,
            }

            with pytest.raises(RuntimeError, match="Failed to fetch balance from tastytrade"):
                get_combined_balance()

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDERS': 'tradier,tastytrade',
        'TRADIER_API_KEY': 'test_key',
        'TRADIER_ACCOUNT_ID': 'test_account',
        'TASTYTRADE_CLIENT_SECRET': 'test_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_combined_balance_rounds_to_two_decimals(self):
        """Combined values should be rounded to 2 decimal places."""
        from src.api.brokerage import get_combined_balance

        with patch('src.api.brokerage.get_all_brokerage_clients') as mock_clients:
            mock_tradier = MagicMock()
            mock_tradier.get_account_balance.return_value = {
                'total_equity': 25000.333, 'total_cash': 8000.111,
                'timestamp': datetime.now(), 'source': 'tradier',
            }
            mock_tastytrade = MagicMock()
            mock_tastytrade.get_account_balance.return_value = {
                'total_equity': 45000.777, 'total_cash': 12000.999,
                'timestamp': datetime.now(), 'source': 'tastytrade',
            }
            mock_clients.return_value = {
                'tradier': mock_tradier,
                'tastytrade': mock_tastytrade,
            }

            combined = get_combined_balance()

        assert combined['total_equity'] == 70001.11
        assert combined['total_cash'] == 20001.11


class TestCombinedBalanceBackwardsCompatibility:
    """Test that combined balance works in single-provider mode."""

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDER': 'tradier',
        'TRADIER_API_KEY': 'test_key',
        'TRADIER_ACCOUNT_ID': 'test_account',
    }, clear=True)
    def test_single_provider_combined_balance(self):
        """get_combined_balance should work with single BROKERAGE_PROVIDER."""
        from src.api.brokerage import get_combined_balance

        with patch('src.api.brokerage.get_all_brokerage_clients') as mock_clients:
            mock_tradier = MagicMock()
            mock_tradier.get_account_balance.return_value = {
                'total_equity': 40000.00, 'total_cash': 15000.00,
                'timestamp': datetime.now(), 'source': 'tradier',
            }
            mock_clients.return_value = {'tradier': mock_tradier}

            combined = get_combined_balance()

        assert combined['total_equity'] == 40000.00
        assert combined['total_cash'] == 15000.00
        assert combined['source'] == 'tradier'
        assert len(combined['brokerage_details']) == 1

    @patch.dict('os.environ', {
        'BROKERAGE_PROVIDERS': 'tradier,tastytrade',
        'TRADIER_API_KEY': 'test_key',
        'TRADIER_ACCOUNT_ID': 'test_account',
        'TASTYTRADE_CLIENT_SECRET': 'test_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_combined_balance_with_zero_equity_brokerage(self):
        """Should correctly sum when one brokerage has zero equity."""
        from src.api.brokerage import get_combined_balance

        with patch('src.api.brokerage.get_all_brokerage_clients') as mock_clients:
            mock_tradier = MagicMock()
            mock_tradier.get_account_balance.return_value = {
                'total_equity': 0.00, 'total_cash': 0.00,
                'timestamp': datetime.now(), 'source': 'tradier',
            }
            mock_tastytrade = MagicMock()
            mock_tastytrade.get_account_balance.return_value = {
                'total_equity': 45000.00, 'total_cash': 12000.00,
                'timestamp': datetime.now(), 'source': 'tastytrade',
            }
            mock_clients.return_value = {
                'tradier': mock_tradier,
                'tastytrade': mock_tastytrade,
            }

            combined = get_combined_balance()

        # Total should be just TastyTrade's value
        assert combined['total_equity'] == 45000.00
        assert combined['total_cash'] == 12000.00
