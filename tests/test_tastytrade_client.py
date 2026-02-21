"""
Test TastyTrade API Client
============================
Unit tests for the TastyTrade brokerage client.
All tests use mocked SDK calls — no real API access needed.

Tests verify:
- Client initialization with valid/missing env vars
- Account balance fetching with correct field mapping
- Account selection from multiple accounts
- Error handling for missing/invalid accounts
- Position fetching
- Market status logic
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from decimal import Decimal


class TestTastyTradeClientInit:
    """Test TastyTrade client initialization."""

    @patch.dict('os.environ', {
        'TASTYTRADE_CLIENT_SECRET': 'test_client_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_refresh_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_client_initializes_with_valid_env(self):
        """Client should initialize when all required env vars are set."""
        from src.api.tastytrade_client import TastyTradeClient
        client = TastyTradeClient()
        assert client.client_secret == 'test_client_id'
        assert client.refresh_token == 'test_refresh_token'
        assert client.target_account_id == 'TEST001'

    @patch.dict('os.environ', {}, clear=True)
    def test_client_raises_without_credentials(self):
        """Client should raise ValueError when OAuth credentials are missing."""
        from src.api.tastytrade_client import TastyTradeClient
        with pytest.raises(ValueError, match="OAuth credentials not configured"):
            TastyTradeClient()

    @patch.dict('os.environ', {
        'TASTYTRADE_CLIENT_SECRET': 'test_client_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_refresh_token',
    }, clear=True)
    def test_client_raises_without_account_id(self):
        """Client should raise ValueError when account ID is missing."""
        from src.api.tastytrade_client import TastyTradeClient
        with pytest.raises(ValueError, match="TASTYTRADE_ACCOUNT_ID not configured"):
            TastyTradeClient()

    @patch.dict('os.environ', {
        'TASTYTRADE_CLIENT_SECRET': '',
        'TASTYTRADE_REFRESH_TOKEN': 'test_refresh_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_client_raises_with_empty_client_id(self):
        """Client should raise ValueError when client ID is empty string."""
        from src.api.tastytrade_client import TastyTradeClient
        with pytest.raises(ValueError, match="OAuth credentials not configured"):
            TastyTradeClient()


class TestTastyTradeAccountBalance:
    """Test account balance fetching and field mapping."""

    def _create_mock_balance(self):
        """Create a mock AccountBalance with Decimal fields."""
        mock_balance = MagicMock()
        mock_balance.net_liquidating_value = Decimal('45000.00')
        mock_balance.cash_balance = Decimal('12000.00')
        mock_balance.long_equity_value = Decimal('28000.00')
        mock_balance.long_derivative_value = Decimal('5000.00')
        mock_balance.short_derivative_value = Decimal('0.00')
        return mock_balance

    def _create_mock_account(self, account_number='TEST001'):
        """Create a mock Account."""
        mock_account = MagicMock()
        mock_account.account_number = account_number
        return mock_account

    @patch.dict('os.environ', {
        'TASTYTRADE_CLIENT_SECRET': 'test_client_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_refresh_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_get_account_balance_returns_expected_format(self):
        """Balance dict should have all required keys with correct types."""
        from src.api.tastytrade_client import TastyTradeClient

        mock_balance = self._create_mock_balance()
        mock_account = self._create_mock_account()

        client = TastyTradeClient()
        client._session = MagicMock()  # Skip session creation
        client._account = mock_account

        with patch.object(client, '_run_async', return_value=mock_balance):
            balance = client.get_account_balance()

        # Verify all required keys exist
        assert 'total_equity' in balance
        assert 'total_cash' in balance
        assert 'timestamp' in balance
        assert 'source' in balance

        # Verify values are correct floats (not Decimals)
        assert balance['total_equity'] == 45000.00
        assert isinstance(balance['total_equity'], float)
        assert balance['total_cash'] == 12000.00
        assert isinstance(balance['total_cash'], float)
        assert balance['source'] == 'tastytrade'
        assert isinstance(balance['timestamp'], datetime)

    @patch.dict('os.environ', {
        'TASTYTRADE_CLIENT_SECRET': 'test_client_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_refresh_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_get_account_balance_maps_option_values(self):
        """Balance should include option long/short values."""
        from src.api.tastytrade_client import TastyTradeClient

        mock_balance = self._create_mock_balance()
        mock_account = self._create_mock_account()

        client = TastyTradeClient()
        client._session = MagicMock()
        client._account = mock_account

        with patch.object(client, '_run_async', return_value=mock_balance):
            balance = client.get_account_balance()

        assert balance['option_long_value'] == 5000.00
        assert balance['option_short_value'] == 0.00
        assert balance['stock_long_value'] == 28000.00

    @patch.dict('os.environ', {
        'TASTYTRADE_CLIENT_SECRET': 'test_client_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_refresh_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_total_equity_uses_net_liquidating_value(self):
        """total_equity should map from net_liquidating_value, not cash + positions."""
        from src.api.tastytrade_client import TastyTradeClient

        mock_balance = MagicMock()
        mock_balance.net_liquidating_value = Decimal('99999.99')
        mock_balance.cash_balance = Decimal('50000.00')
        mock_balance.long_equity_value = Decimal('40000.00')
        mock_balance.long_derivative_value = Decimal('9999.99')
        mock_balance.short_derivative_value = Decimal('0.00')

        client = TastyTradeClient()
        client._session = MagicMock()
        client._account = self._create_mock_account()

        with patch.object(client, '_run_async', return_value=mock_balance):
            balance = client.get_account_balance()

        # Should use net_liquidating_value, NOT sum of parts
        assert balance['total_equity'] == 99999.99


class TestTastyTradeAccountSelection:
    """Test account selection from multiple accounts."""

    @patch.dict('os.environ', {
        'TASTYTRADE_CLIENT_SECRET': 'test_client_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_refresh_token',
        'TASTYTRADE_ACCOUNT_ID': 'ACCT002',
    })
    def test_selects_correct_account_by_id(self):
        """Should fetch the specific account matching TASTYTRADE_ACCOUNT_ID."""
        from src.api.tastytrade_client import TastyTradeClient

        mock_account = MagicMock()
        mock_account.account_number = 'ACCT002'

        client = TastyTradeClient()
        client._session = MagicMock()

        # Mock _run_async to return the account directly (simulating Account.get with specific ID)
        with patch.object(client, '_run_async', return_value=mock_account):
            account = client._get_account()

        assert account.account_number == 'ACCT002'

    @patch.dict('os.environ', {
        'TASTYTRADE_CLIENT_SECRET': 'test_client_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_refresh_token',
        'TASTYTRADE_ACCOUNT_ID': 'NONEXISTENT',
    })
    def test_raises_when_account_not_found(self):
        """Should raise ValueError with masked account info when account not found."""
        from src.api.tastytrade_client import TastyTradeClient

        # First call (direct fetch) raises, second call (list all) returns accounts
        mock_acct1 = MagicMock()
        mock_acct1.account_number = 'ACCT001'
        mock_acct2 = MagicMock()
        mock_acct2.account_number = 'ACCT002'

        client = TastyTradeClient()
        client._session = MagicMock()

        # Simulate: direct fetch fails, list returns two accounts
        def side_effect(coro):
            # Check if this is the direct fetch or the list-all
            if not hasattr(side_effect, '_call_count'):
                side_effect._call_count = 0
            side_effect._call_count += 1

            if side_effect._call_count == 1:
                raise Exception("Account not found")
            else:
                return [mock_acct1, mock_acct2]

        with patch.object(client, '_run_async', side_effect=side_effect):
            with pytest.raises(ValueError, match="not found"):
                client._get_account()


class TestTastyTradePositions:
    """Test position fetching."""

    @patch.dict('os.environ', {
        'TASTYTRADE_CLIENT_SECRET': 'test_client_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_refresh_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_get_positions_returns_list_of_dicts(self):
        """Positions should be returned as list of dicts with expected keys."""
        from src.api.tastytrade_client import TastyTradeClient

        mock_pos = MagicMock()
        mock_pos.symbol = 'SPY'
        mock_pos.quantity = Decimal('100')
        mock_pos.instrument_type = MagicMock(value='Equity')
        mock_pos.underlying_symbol = 'SPY'
        mock_pos.average_open_price = Decimal('450.00')
        mock_pos.close_price = Decimal('455.50')
        mock_pos.multiplier = 1
        mock_pos.quantity_direction = 'Long'

        client = TastyTradeClient()
        client._session = MagicMock()
        client._account = MagicMock()

        with patch.object(client, '_run_async', return_value=[mock_pos]):
            positions = client.get_positions()

        assert len(positions) == 1
        pos = positions[0]
        assert pos['symbol'] == 'SPY'
        assert pos['quantity'] == 100.0
        assert isinstance(pos['quantity'], float)
        assert pos['instrument_type'] == 'Equity'

    @patch.dict('os.environ', {
        'TASTYTRADE_CLIENT_SECRET': 'test_client_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_refresh_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_get_positions_empty(self):
        """Should return empty list when no positions exist."""
        from src.api.tastytrade_client import TastyTradeClient

        client = TastyTradeClient()
        client._session = MagicMock()
        client._account = MagicMock()

        with patch.object(client, '_run_async', return_value=[]):
            positions = client.get_positions()

        assert positions == []


class TestTastyTradeMarketStatus:
    """Test market open/closed logic."""

    @patch.dict('os.environ', {
        'TASTYTRADE_CLIENT_SECRET': 'test_client_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_refresh_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_market_closed_on_weekend(self):
        """Market should be closed on Saturday and Sunday."""
        from src.api.tastytrade_client import TastyTradeClient
        from unittest.mock import patch as mock_patch

        client = TastyTradeClient()

        # Mock a Saturday at noon ET
        import pytz
        et = pytz.timezone('America/New_York')
        saturday_noon = datetime(2026, 2, 14, 12, 0, 0, tzinfo=et)  # Saturday

        with mock_patch('src.api.tastytrade_client.datetime') as mock_dt:
            mock_dt.now.return_value = saturday_noon
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            result = client.is_market_open()

        assert result is False

    @patch.dict('os.environ', {
        'TASTYTRADE_CLIENT_SECRET': 'test_client_id',
        'TASTYTRADE_REFRESH_TOKEN': 'test_refresh_token',
        'TASTYTRADE_ACCOUNT_ID': 'TEST001',
    })
    def test_market_open_during_trading_hours(self):
        """Market should be open Mon-Fri 9:30 AM - 4:00 PM ET."""
        from src.api.tastytrade_client import TastyTradeClient
        from unittest.mock import patch as mock_patch

        client = TastyTradeClient()

        # Mock a Wednesday at 11:00 AM ET
        import pytz
        et = pytz.timezone('America/New_York')
        wednesday_11am = datetime(2026, 2, 11, 11, 0, 0, tzinfo=et)  # Wednesday

        with mock_patch('src.api.tastytrade_client.datetime') as mock_dt:
            mock_dt.now.return_value = wednesday_11am
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            result = client.is_market_open()

        assert result is True
