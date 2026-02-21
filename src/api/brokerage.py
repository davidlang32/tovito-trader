"""
Brokerage API Protocol and Factory
===================================
Defines the common interface that all brokerage clients must implement,
and provides factory functions to instantiate clients based on configuration.

Supports two modes:
  1. Single provider — BROKERAGE_PROVIDER env var (legacy, backwards-compatible)
  2. Multi-provider — BROKERAGE_PROVIDERS env var (comma-separated list)
     for combined NAV across multiple brokerages.

Usage:
    from src.api.brokerage import get_brokerage_client

    # Single client (uses BROKERAGE_PROVIDER env var, defaults to 'tradier')
    client = get_brokerage_client()

    # Or specify explicitly
    client = get_brokerage_client('tastytrade')

    balance = client.get_account_balance()
    # Returns: {'total_equity': float, 'total_cash': float, 'timestamp': datetime, ...}

    # Combined balance from ALL configured brokerages
    from src.api.brokerage import get_all_brokerage_clients, get_combined_balance

    clients = get_all_brokerage_clients()  # Reads BROKERAGE_PROVIDERS
    combined = get_combined_balance()       # Returns aggregated totals
"""

import os
import logging
from typing import Dict, List, Protocol, runtime_checkable
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@runtime_checkable
class BrokerageClient(Protocol):
    """
    Protocol defining the interface all brokerage API clients must implement.

    Any class that has these methods with compatible signatures satisfies
    this protocol — no explicit inheritance required (structural subtyping).
    """

    def get_account_balance(self) -> Dict:
        """
        Get current account balance and equity.

        Returns:
            dict with at minimum:
                'total_equity': float — Total account value (net liquidating value)
                'total_cash': float — Cash balance
                'timestamp': datetime — When the data was fetched
        """
        ...

    def get_positions(self) -> List[Dict]:
        """
        Get current open positions.

        Returns:
            list of dicts, each containing at minimum:
                'symbol': str
                'quantity': float
                'instrument_type': str
        """
        ...

    def is_market_open(self) -> bool:
        """
        Check if the US equity market is currently open.

        Returns:
            bool: True if market is open
        """
        ...

    def get_transactions(
        self,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> List[Dict]:
        """
        Get transaction/trade history for a date range (normalized).

        Args:
            start_date: Start of date range (defaults to 30 days ago)
            end_date: End of date range (defaults to today)

        Returns:
            list of dicts, each containing at minimum:
                'date': str (YYYY-MM-DD)
                'transaction_type': str (trade, ach, dividend, etc.)
                'symbol': str
                'quantity': float or None
                'price': float or None
                'amount': float
                'commission': float
                'fees': float
                'description': str
                'brokerage_transaction_id': str
                'category': str (Trade, Transfer, Income, Fee, Other)
                'subcategory': str
        """
        ...

    def get_raw_transactions(
        self,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> List[Dict]:
        """
        Get raw transaction data from the brokerage API for ETL staging.

        Unlike get_transactions() which normalizes the data, this method
        preserves the original API response structure. Each dict must include:
            'brokerage_transaction_id': str — Unique ID from the brokerage
            'raw_data': dict — Complete original API response for this transaction
            'transaction_date': str — Date in YYYY-MM-DD format
            'transaction_type': str — Original type string from the brokerage
            'transaction_subtype': str or None — Original subtype if available
            'symbol': str or None
            'amount': float
            'description': str

        Args:
            start_date: Start of date range (defaults to 30 days ago)
            end_date: End of date range (defaults to today)

        Returns:
            list of dicts with raw brokerage data for ETL staging
        """
        ...


def get_brokerage_client(provider: str = None) -> BrokerageClient:
    """
    Factory function to create a single brokerage client.

    Reads the BROKERAGE_PROVIDER environment variable if no provider
    is specified. Defaults to 'tradier' to preserve existing behavior.

    Args:
        provider: 'tradier' or 'tastytrade'. If None, reads from
                  BROKERAGE_PROVIDER env var (default: 'tradier').

    Returns:
        A brokerage client implementing the BrokerageClient protocol.

    Raises:
        ValueError: If the provider is unknown.
    """
    if provider is None:
        provider = os.getenv('BROKERAGE_PROVIDER', 'tradier').lower().strip()

    if provider == 'tastytrade':
        from src.api.tastytrade_client import TastyTradeClient
        return TastyTradeClient()
    elif provider == 'tradier':
        from src.api.tradier import TradierClient
        return TradierClient()
    else:
        raise ValueError(
            f"Unknown brokerage provider: '{provider}'. "
            f"Supported providers: 'tradier', 'tastytrade'"
        )


def get_configured_providers() -> List[str]:
    """
    Get the list of configured brokerage providers.

    Reads BROKERAGE_PROVIDERS first (comma-separated list for multi-brokerage).
    Falls back to BROKERAGE_PROVIDER (single provider) for backwards compatibility.

    Returns:
        List of provider name strings, e.g. ['tradier', 'tastytrade']
    """
    providers_str = os.getenv('BROKERAGE_PROVIDERS', '').strip()

    if providers_str:
        # Multi-provider mode: parse comma-separated list
        providers = [p.strip().lower() for p in providers_str.split(',') if p.strip()]
    else:
        # Single-provider fallback
        single = os.getenv('BROKERAGE_PROVIDER', 'tradier').strip().lower()
        providers = [single]

    return providers


def get_all_brokerage_clients() -> Dict[str, BrokerageClient]:
    """
    Create clients for ALL configured brokerage providers.

    Reads BROKERAGE_PROVIDERS env var (comma-separated, e.g. "tradier,tastytrade").
    Falls back to BROKERAGE_PROVIDER for single-provider backwards compatibility.

    Returns:
        Dict mapping provider name to client instance.
        e.g. {'tradier': TradierClient(), 'tastytrade': TastyTradeClient()}

    Raises:
        ValueError: If any provider is unknown or fails to initialize.
    """
    providers = get_configured_providers()
    clients = {}

    for provider in providers:
        try:
            clients[provider] = get_brokerage_client(provider)
            logger.info("Initialized brokerage client: %s", provider)
        except Exception as e:
            logger.error("Failed to initialize %s client: %s", provider, e)
            raise ValueError(
                f"Failed to initialize brokerage client '{provider}': {e}"
            ) from e

    if not clients:
        raise ValueError(
            "No brokerage providers configured. "
            "Set BROKERAGE_PROVIDERS (e.g. 'tradier,tastytrade') "
            "or BROKERAGE_PROVIDER in .env."
        )

    return clients


def get_combined_balance() -> Dict:
    """
    Fetch and aggregate account balances from ALL configured brokerages.

    Queries each configured brokerage, sums their total_equity and total_cash
    values, and returns a combined balance dict. Individual brokerage results
    are preserved in the 'brokerage_details' key for auditing/logging.

    Returns:
        dict: {
            'total_equity': float,       — Combined net liquidating value
            'total_cash': float,         — Combined cash balance
            'timestamp': datetime,       — When the combined data was assembled
            'source': str,               — Comma-separated list of providers
            'brokerage_details': dict,   — Per-provider balance dicts
        }

    Raises:
        ValueError: If no providers are configured or all fail.
        RuntimeError: If any individual brokerage fetch fails (fail-fast —
                      partial NAV is dangerous for financial accuracy).
    """
    clients = get_all_brokerage_clients()

    combined_equity = 0.0
    combined_cash = 0.0
    brokerage_details = {}
    sources = []

    for provider, client in clients.items():
        try:
            balance = client.get_account_balance()
            equity = balance.get('total_equity', 0.0)
            cash = balance.get('total_cash', 0.0)

            combined_equity += equity
            combined_cash += cash
            brokerage_details[provider] = balance
            sources.append(provider)

            logger.info(
                "Balance from %s: equity=$%s, cash=$%s",
                provider, f"{equity:,.2f}", f"{cash:,.2f}"
            )

        except Exception as e:
            # Fail-fast: partial NAV is worse than no NAV.
            # If we can't get data from one brokerage, the combined total
            # would be inaccurate. Better to fail and alert than record
            # a wrong NAV that affects all investor share values.
            logger.error("Failed to fetch balance from %s: %s", provider, e)
            raise RuntimeError(
                f"Failed to fetch balance from {provider}: {e}. "
                f"Combined NAV requires ALL brokerages to respond. "
                f"Fix the issue or temporarily remove '{provider}' from "
                f"BROKERAGE_PROVIDERS to proceed with remaining brokerages."
            ) from e

    result = {
        'total_equity': round(combined_equity, 2),
        'total_cash': round(combined_cash, 2),
        'timestamp': datetime.now(),
        'source': ','.join(sources),
        'brokerage_details': brokerage_details,
    }

    logger.info(
        "Combined balance across %d brokerages: equity=$%s, cash=$%s",
        len(clients), f"{result['total_equity']:,.2f}", f"{result['total_cash']:,.2f}"
    )

    return result
