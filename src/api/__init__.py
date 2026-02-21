"""
Brokerage API Clients
Provides unified access to brokerage APIs (Tradier, TastyTrade).

Usage:
    from src.api.brokerage import get_brokerage_client

    client = get_brokerage_client()  # Uses BROKERAGE_PROVIDER env var
    balance = client.get_account_balance()
"""
