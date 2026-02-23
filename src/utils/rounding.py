"""
Financial Rounding Utilities
=============================
Consistent rounding for all financial calculations in Tovito Trader.

Industry Standards (SEC / mutual fund conventions):
    - NAV per share:     4 decimal places  (e.g., $1.0526)
    - Share quantities:  4 decimal places  (e.g., 15000.0000 shares)
    - Dollar amounts:    2 decimal places  (e.g., $17,380.97)
    - Percentages:       2 decimal places  (e.g., 1.32%)
    - Rounding method:   ROUND_HALF_UP (banker's standard)

Usage:
    from src.utils.rounding import round_nav, round_shares, round_dollars, round_pct

    nav = round_nav(portfolio_value / total_shares)   # -> 4 decimals
    shares = round_shares(amount / nav)                # -> 4 decimals
    dollars = round_dollars(amount)                    # -> 2 decimals
    pct = round_pct(daily_change_percent)              # -> 2 decimals
"""


def round_nav(value):
    """Round NAV per share to 4 decimal places."""
    if value is None:
        return None
    return round(float(value), 4)


def round_shares(value):
    """Round share quantities to 4 decimal places."""
    if value is None:
        return None
    return round(float(value), 4)


def round_dollars(value):
    """Round dollar amounts to 2 decimal places."""
    if value is None:
        return None
    return round(float(value), 2)


def round_pct(value):
    """Round percentages to 2 decimal places."""
    if value is None:
        return None
    return round(float(value), 2)
