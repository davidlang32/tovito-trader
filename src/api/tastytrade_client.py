"""
TastyTrade API Client
======================
Handles all interactions with the TastyTrade brokerage API.
Wraps the async tastytrade SDK (v12+) in synchronous methods
that match the BrokerageClient protocol.

Authentication:
    Uses OAuth (client_id + refresh_token). Session tokens are
    automatically refreshed by the SDK. No password or 2FA needed.

Account Selection:
    The user may have multiple TastyTrade accounts. Set
    TASTYTRADE_ACCOUNT_ID in .env to specify which account
    to use for NAV calculations.

Environment Variables:
    TASTYTRADE_CLIENT_SECRET — OAuth client secret from TastyTrade app
    TASTYTRADE_REFRESH_TOKEN — OAuth refresh token (permanent, never expires)
    TASTYTRADE_ACCOUNT_ID    — Specific account number to use
"""

import os
import asyncio
import logging
from datetime import datetime, time as dt_time
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class TastyTradeClient:
    """
    Client for TastyTrade API interactions.

    Implements the BrokerageClient protocol defined in src/api/brokerage.py.
    Uses the tastytrade SDK v12+ with OAuth authentication.

    Important: The tastytrade SDK uses httpx.AsyncClient and asyncio.Lock
    internally. These objects are tied to an event loop, so we must use a
    single persistent event loop for all async calls (not multiple
    asyncio.run() calls, which each create and destroy their own loop).
    """

    def __init__(self):
        self.client_secret = os.getenv('TASTYTRADE_CLIENT_SECRET')
        self.refresh_token = os.getenv('TASTYTRADE_REFRESH_TOKEN')
        self.target_account_id = os.getenv('TASTYTRADE_ACCOUNT_ID')

        if not self.client_secret or not self.refresh_token:
            raise ValueError(
                "TastyTrade OAuth credentials not configured. "
                "Set TASTYTRADE_CLIENT_SECRET and TASTYTRADE_REFRESH_TOKEN in .env. "
                "Create an OAuth app at https://my.tastytrade.com → API Access."
            )

        if not self.target_account_id:
            raise ValueError(
                "TASTYTRADE_ACCOUNT_ID not configured in .env. "
                "This is required to select the correct account for NAV updates."
            )

        self._session = None
        self._account = None
        self._loop = None

    def _get_loop(self):
        """
        Get or create a persistent event loop.

        The tastytrade SDK's Session creates an httpx.AsyncClient and
        asyncio.Lock that are bound to a specific event loop. We must
        reuse the same loop for all async operations to avoid
        'Invalid JWT' / event loop mismatch errors.
        """
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        return self._loop

    def _run_async(self, coro):
        """
        Run an async coroutine synchronously using a persistent event loop.

        Unlike asyncio.run() which creates and destroys a loop each time,
        this reuses the same loop so the SDK's internal async objects
        (httpx client, locks) remain valid across calls.
        """
        loop = self._get_loop()
        return loop.run_until_complete(coro)

    def _get_session(self):
        """
        Get or create a TastyTrade OAuth session.

        The session is created inside the persistent event loop context.
        OAuth sessions auto-refresh their tokens internally.
        The refresh_token is permanent and never expires.
        """
        if self._session is not None:
            return self._session

        from tastytrade import Session

        # Session.__init__ is synchronous but creates async objects
        # (httpx.AsyncClient, asyncio.Lock). These must live in our
        # persistent loop's context, so we set it as current first.
        loop = self._get_loop()
        asyncio.set_event_loop(loop)

        self._session = Session(self.client_secret, self.refresh_token)
        logger.info("TastyTrade OAuth session established")

        return self._session

    def _get_account(self):
        """
        Get the configured TastyTrade account.

        Fetches the specific account matching TASTYTRADE_ACCOUNT_ID.
        If not found, raises ValueError with masked account info.
        """
        if self._account is not None:
            return self._account

        from tastytrade import Account

        session = self._get_session()

        try:
            # Fetch the specific account directly by account number
            self._account = self._run_async(
                Account.get(session, account_number=self.target_account_id)
            )
            logger.info(
                "TastyTrade account loaded (ending ...%s)",
                self.target_account_id[-4:]
            )
            return self._account

        except Exception as e:
            # If direct fetch fails, try listing all accounts to give a helpful error
            try:
                all_accounts = self._run_async(Account.get(session))
                available = [f"...{a.account_number[-4:]}" for a in all_accounts]
                raise ValueError(
                    f"TASTYTRADE_ACCOUNT_ID '...{self.target_account_id[-4:]}' "
                    f"not found or inaccessible. "
                    f"Available accounts: {available}"
                ) from e
            except ValueError:
                raise  # Re-raise our custom error
            except Exception:
                raise ValueError(
                    f"Failed to access TastyTrade account "
                    f"'...{self.target_account_id[-4:]}': {e}"
                ) from e

    def get_account_balance(self) -> Dict:
        """
        Get current account balance.

        Maps TastyTrade's balance fields to the standard format
        expected by the NAV pipeline. The key field is
        'net_liquidating_value' which represents total account equity.

        Returns:
            dict: {
                'total_equity': float,  — Net liquidating value
                'total_cash': float,    — Cash balance
                'option_long_value': float,
                'option_short_value': float,
                'stock_long_value': float,
                'timestamp': datetime,
                'source': 'tastytrade'
            }
        """
        session = self._get_session()
        account = self._get_account()

        balance = self._run_async(account.get_balances(session))

        # Map TastyTrade Decimal fields to float for consistency
        # with existing Tradier pipeline (which uses float throughout)
        result = {
            'total_equity': float(balance.net_liquidating_value),
            'total_cash': float(balance.cash_balance),
            'option_long_value': float(balance.long_derivative_value),
            'option_short_value': float(balance.short_derivative_value),
            'stock_long_value': float(balance.long_equity_value),
            'timestamp': datetime.now(),
            'source': 'tastytrade'
        }

        logger.info(
            "TastyTrade balance fetched: equity=$%s",
            f"{result['total_equity']:,.2f}"
        )

        return result

    def get_positions(self) -> List[Dict]:
        """
        Get current open positions.

        Returns:
            list of dicts with position details.
        """
        session = self._get_session()
        account = self._get_account()

        positions = self._run_async(account.get_positions(session))

        return [
            {
                'symbol': pos.symbol,
                'quantity': float(pos.quantity),
                'instrument_type': str(pos.instrument_type.value)
                    if hasattr(pos.instrument_type, 'value')
                    else str(pos.instrument_type),
                'underlying_symbol': pos.underlying_symbol,
                'average_open_price': float(pos.average_open_price),
                'close_price': float(pos.close_price),
                'multiplier': pos.multiplier,
                'quantity_direction': pos.quantity_direction,
            }
            for pos in positions
        ]

    def get_transactions(self, start_date=None, end_date=None):
        """
        Get normalized transaction history from TastyTrade.

        Uses the TastyTrade SDK to fetch account transactions and
        normalizes them to the standard BrokerageClient format.

        Args:
            start_date: Start date (defaults to 30 days ago)
            end_date: End date (defaults to today)

        Returns:
            list of dicts with standardized transaction fields
        """
        from datetime import timedelta

        session = self._get_session()
        account = self._get_account()

        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()

        # Convert to date objects if datetime
        sd = start_date.date() if hasattr(start_date, 'date') else start_date
        ed = end_date.date() if hasattr(end_date, 'date') else end_date

        # SDK method is get_history(), not get_transactions()
        transactions = self._run_async(
            account.get_history(session, start_date=sd, end_date=ed)
        )

        normalized = []
        for txn in transactions:
            txn_type = self._map_transaction_type(txn)
            category, subcategory = self._categorize_tastytrade_txn(txn, txn_type)

            # Extract date
            txn_date = None
            if hasattr(txn, 'executed_at') and txn.executed_at:
                txn_date = str(txn.executed_at.date())
            elif hasattr(txn, 'transaction_date') and txn.transaction_date:
                td = txn.transaction_date
                txn_date = str(td.date()) if hasattr(td, 'date') else str(td)[:10]

            # Extract financial values safely
            amount = float(txn.value) if hasattr(txn, 'value') and txn.value else 0.0
            commission = float(txn.commission) if hasattr(txn, 'commission') and txn.commission else 0.0
            fees = 0.0
            if hasattr(txn, 'clearing_fees') and txn.clearing_fees:
                fees += float(txn.clearing_fees)
            if hasattr(txn, 'regulatory_fees') and txn.regulatory_fees:
                fees += float(txn.regulatory_fees)

            normalized.append({
                'date': txn_date or '',
                'transaction_type': txn_type,
                'symbol': getattr(txn, 'underlying_symbol', '') or getattr(txn, 'symbol', '') or '',
                'quantity': float(txn.quantity) if hasattr(txn, 'quantity') and txn.quantity else None,
                'price': float(txn.price) if hasattr(txn, 'price') and txn.price else None,
                'amount': amount,
                'commission': commission,
                'fees': round(fees, 2),
                'option_type': getattr(txn, 'option_type', None),
                'strike': float(txn.strike_price) if hasattr(txn, 'strike_price') and txn.strike_price else None,
                'expiration_date': str(txn.expiration_date)[:10] if hasattr(txn, 'expiration_date') and txn.expiration_date else None,
                'description': getattr(txn, 'description', '') or '',
                'brokerage_transaction_id': str(txn.id) if hasattr(txn, 'id') else '',
                'category': category,
                'subcategory': subcategory,
            })

        logger.info("TastyTrade transactions fetched: %d records", len(normalized))
        return normalized

    def get_raw_transactions(self, start_date=None, end_date=None):
        """
        Get raw transaction data from TastyTrade API for ETL staging.

        Preserves original SDK transaction objects as dicts, including all
        fields the API returns. This data goes into brokerage_transactions_raw
        for full audit trail before normalization.

        Args:
            start_date: Start date (defaults to 30 days ago)
            end_date: End date (defaults to today)

        Returns:
            list of dicts with raw brokerage data for ETL staging
        """
        import json
        from datetime import timedelta

        session = self._get_session()
        account = self._get_account()

        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()

        sd = start_date.date() if hasattr(start_date, 'date') else start_date
        ed = end_date.date() if hasattr(end_date, 'date') else end_date

        transactions = self._run_async(
            account.get_history(session, start_date=sd, end_date=ed)
        )

        raw_results = []
        for txn in transactions:
            # Serialize all available attributes to a dict for raw_data JSON
            raw_dict = {}
            for attr in dir(txn):
                if attr.startswith('_'):
                    continue
                try:
                    val = getattr(txn, attr)
                    if callable(val):
                        continue
                    # Convert non-serializable types
                    if hasattr(val, 'value'):  # Enum
                        raw_dict[attr] = str(val.value)
                    elif hasattr(val, 'isoformat'):  # datetime/date
                        raw_dict[attr] = val.isoformat()
                    elif isinstance(val, (str, int, float, bool, type(None))):
                        raw_dict[attr] = val
                    else:
                        raw_dict[attr] = str(val)
                except Exception:
                    continue

            # Extract date
            txn_date = None
            if hasattr(txn, 'executed_at') and txn.executed_at:
                txn_date = str(txn.executed_at.date())
            elif hasattr(txn, 'transaction_date') and txn.transaction_date:
                td = txn.transaction_date
                txn_date = str(td.date()) if hasattr(td, 'date') else str(td)[:10]

            # Extract original type and subtype
            tt_type = getattr(txn, 'transaction_type', '') or ''
            tt_sub = getattr(txn, 'transaction_sub_type', '') or ''
            if hasattr(tt_type, 'value'):
                tt_type = str(tt_type.value)
            if hasattr(tt_sub, 'value'):
                tt_sub = str(tt_sub.value)

            amount = float(txn.value) if hasattr(txn, 'value') and txn.value else 0.0

            raw_results.append({
                'brokerage_transaction_id': str(txn.id) if hasattr(txn, 'id') else '',
                'raw_data': raw_dict,
                'transaction_date': txn_date or '',
                'transaction_type': str(tt_type),
                'transaction_subtype': str(tt_sub) if tt_sub else None,
                'symbol': getattr(txn, 'underlying_symbol', '') or getattr(txn, 'symbol', '') or '',
                'amount': amount,
                'description': getattr(txn, 'description', '') or '',
            })

        logger.info("TastyTrade raw transactions fetched: %d records", len(raw_results))
        return raw_results

    @staticmethod
    def _map_transaction_type(txn):
        """Map TastyTrade transaction type to standard trade_type values."""
        tt_type = (getattr(txn, 'transaction_type', '') or '').lower()
        tt_sub = (getattr(txn, 'transaction_sub_type', '') or '').lower()

        trade_sub_map = {
            'buy to open': 'buy_to_open',
            'sell to close': 'sell_to_close',
            'buy to close': 'buy_to_close',
            'sell to open': 'sell_to_open',
            'buy': 'buy',
            'sell': 'sell',
        }

        if tt_type == 'trade':
            return trade_sub_map.get(
                tt_sub,
                'buy' if 'buy' in tt_sub else 'sell' if 'sell' in tt_sub else 'other'
            )
        elif tt_type in ('money movement', 'balance adjustment'):
            return 'ach'
        elif tt_type == 'dividend':
            return 'dividend'
        elif tt_type == 'interest':
            return 'interest'
        elif tt_type == 'fee':
            return 'fee'
        elif tt_type == 'receive deliver':
            return 'other'
        else:
            return 'other'

    @staticmethod
    def _categorize_tastytrade_txn(txn, txn_type):
        """Categorize a TastyTrade transaction."""
        if txn_type in ('buy', 'sell', 'buy_to_open', 'sell_to_close',
                         'buy_to_close', 'sell_to_open'):
            category = 'Trade'
            # SDK Transaction has instrument_type (InstrumentType enum), not option_type
            instrument = getattr(txn, 'instrument_type', None)
            instrument_str = str(instrument.value).lower() if hasattr(instrument, 'value') else str(instrument or '').lower()
            is_option = 'option' in instrument_str
            if is_option:
                # Determine call/put from symbol (TastyTrade symbols contain C/P)
                symbol = getattr(txn, 'symbol', '') or ''
                if 'C' in symbol.split()[-1] if symbol else '':
                    subcategory = 'Option Call'
                elif 'P' in symbol.split()[-1] if symbol else '':
                    subcategory = 'Option Put'
                else:
                    subcategory = 'Option Trade'
            elif txn_type in ('buy', 'buy_to_open', 'buy_to_close'):
                subcategory = 'Stock Buy'
            else:
                subcategory = 'Stock Sell'
        elif txn_type == 'ach':
            category = 'Transfer'
            amount = float(txn.value) if hasattr(txn, 'value') and txn.value else 0
            subcategory = 'Deposit' if amount > 0 else 'Withdrawal'
        elif txn_type == 'dividend':
            category = 'Income'
            subcategory = 'Dividend'
        elif txn_type == 'interest':
            category = 'Income'
            subcategory = 'Interest'
        elif txn_type == 'fee':
            category = 'Fee'
            subcategory = 'Fee'
        else:
            category = 'Other'
            subcategory = txn_type.title() if txn_type else 'Unknown'

        return category, subcategory

    def is_market_open(self) -> bool:
        """
        Check if the US equity market is currently open.

        TastyTrade API does not have a market clock endpoint,
        so we use standard US market hours in Eastern Time.
        Checks for weekends only — does not account for holidays.
        For holiday awareness, the daily_runner.py has separate logic.

        Returns:
            bool: True if market is open (Mon-Fri 9:30-16:00 ET)
        """
        try:
            import pytz
            et = pytz.timezone('America/New_York')
            now_et = datetime.now(et)
        except ImportError:
            # Fallback if pytz not available — use basic offset
            from datetime import timezone, timedelta
            et_offset = timezone(timedelta(hours=-5))
            now_et = datetime.now(et_offset)

        # Weekend check
        if now_et.weekday() >= 5:
            return False

        market_open = dt_time(9, 30)
        market_close = dt_time(16, 0)
        current_time = now_et.time()

        return market_open <= current_time <= market_close


# Manual test / verification
if __name__ == "__main__":
    """Test TastyTrade API connection."""

    try:
        client = TastyTradeClient()
        print("✅ TastyTrade client initialized (OAuth)")

        # Test balance fetch
        balance = client.get_account_balance()
        print(f"\n✅ Account Balance Retrieved:")
        print(f"   Total Equity: ${balance['total_equity']:,.2f}")
        print(f"   Total Cash: ${balance['total_cash']:,.2f}")
        print(f"   Timestamp: {balance['timestamp']}")

        # Test market status
        is_open = client.is_market_open()
        print(f"\n✅ Market Status: {'OPEN' if is_open else 'CLOSED'}")

        # Test positions
        positions = client.get_positions()
        print(f"\n✅ Current Positions: {len(positions)} position(s)")

        print("\n🎉 All TastyTrade API tests passed!")

    except Exception as e:
        print(f"\n❌ API Test Failed: {str(e)}")
        print("\nPlease check:")
        print("1. .env file has TASTYTRADE_CLIENT_ID set")
        print("2. .env file has TASTYTRADE_REFRESH_TOKEN set")
        print("3. .env file has TASTYTRADE_ACCOUNT_ID set")
        print("4. OAuth app is configured at https://my.tastytrade.com")
        print("5. Internet connection is working")
