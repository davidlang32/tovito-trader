"""
Plan Classification
====================

Classifies portfolio positions into one of three investment plans:

- **Plan CASH** (plan_cash): Treasury ETFs, money market funds, and
  cash balances. Conservative, earns daily interest. Includes positions
  in SGOV, BIL, SHV, SCHO, VMFXX, and any instrument typed as
  'Cash' or 'money-market'.

- **Plan ETF** (plan_etf): Index-tracking ETFs including leveraged
  variants. Moderate risk. Includes SPY, QQQ, SPXL, TQQQ, IWM
  (equity shares only, not options on these symbols).

- **Plan A** (plan_a): Leveraged options strategy. Aggressive risk.
  Everything else -- individual stock options, index options, and
  any symbol/type not matched by the above two plans.

Usage:
    from src.plans.classification import classify_position

    plan = classify_position("SGOV", "Equity")     # -> "plan_cash"
    plan = classify_position("SPY", "Equity")       # -> "plan_etf"
    plan = classify_position("AAPL", "Option")      # -> "plan_a"
    plan = classify_position("SPY", "Option")        # -> "plan_a"
"""

from typing import Dict, List, Optional


# ============================================================
# Plan identifiers (used as DB keys and API identifiers)
# ============================================================

PLAN_IDS = ("plan_cash", "plan_etf", "plan_a")

# ============================================================
# Symbol sets for each plan
# ============================================================

# Treasury ETFs and money market funds
PLAN_CASH_SYMBOLS = frozenset({
    "SGOV",   # iShares 0-3 Month Treasury Bond ETF
    "BIL",    # SPDR Bloomberg 1-3 Month T-Bill ETF
    "SHV",    # iShares Short Treasury Bond ETF
    "SCHO",   # Schwab Short-Term U.S. Treasury ETF
    "VMFXX",  # Vanguard Federal Money Market Fund
    "VUSXX",  # Vanguard Treasury Money Market Fund
})

# Index-tracking ETFs (equity shares only)
PLAN_ETF_SYMBOLS = frozenset({
    "SPY",    # SPDR S&P 500 ETF
    "QQQ",    # Invesco QQQ Trust (Nasdaq-100)
    "SPXL",   # Direxion Daily S&P 500 Bull 3X
    "TQQQ",   # ProShares UltraPro QQQ 3X
    "IWM",    # iShares Russell 2000 ETF
    "DIA",    # SPDR Dow Jones Industrial Average ETF
    "VOO",    # Vanguard S&P 500 ETF
})

# Cash-like instrument types from brokerage
CASH_INSTRUMENT_TYPES = frozenset({
    "Cash",
    "cash",
    "money-market",
    "Money Market",
    "Sweep",
})


# ============================================================
# Classification function
# ============================================================

def classify_position(symbol: str, instrument_type: Optional[str] = None) -> str:
    """Classify a single position into a plan.

    Args:
        symbol: Ticker symbol (e.g., 'SGOV', 'SPY', 'AAPL 250321C00200000').
            For options, the underlying symbol should be extracted first
            or passed via the symbol parameter.
        instrument_type: Instrument type from brokerage API (e.g., 'Equity',
            'Option', 'Cash', 'money-market'). Case-sensitive matching
            against known types, but the logic handles common variations.

    Returns:
        One of: 'plan_cash', 'plan_etf', 'plan_a'
    """
    # Cash instrument types always go to plan_cash
    if instrument_type and instrument_type in CASH_INSTRUMENT_TYPES:
        return "plan_cash"

    # Normalize symbol: take the root ticker (before any space for options)
    root_symbol = symbol.split()[0].upper() if symbol else ""

    # Treasury/money market symbols
    if root_symbol in PLAN_CASH_SYMBOLS:
        return "plan_cash"

    # Index ETFs — only if held as equity (not options on these ETFs)
    if root_symbol in PLAN_ETF_SYMBOLS:
        # Options on ETFs are Plan A (leveraged strategy)
        if instrument_type and instrument_type.lower() in ("option", "options"):
            return "plan_a"
        return "plan_etf"

    # Everything else is Plan A (options, individual stocks, etc.)
    return "plan_a"


def classify_position_by_underlying(
    symbol: str,
    underlying_symbol: Optional[str] = None,
    instrument_type: Optional[str] = None,
) -> str:
    """Classify using the underlying symbol when available (for options).

    For options positions, the brokerage often provides both a full
    option symbol ('SPY 250321C00500000') and the underlying ('SPY').
    This function uses the underlying for classification.

    Args:
        symbol: Full position symbol
        underlying_symbol: Underlying ticker (from brokerage position data)
        instrument_type: Instrument type from brokerage

    Returns:
        One of: 'plan_cash', 'plan_etf', 'plan_a'
    """
    # Use underlying symbol for classification if available
    effective_symbol = underlying_symbol if underlying_symbol else symbol
    return classify_position(effective_symbol, instrument_type)


# ============================================================
# Plan metadata
# ============================================================

PLAN_METADATA = {
    "plan_cash": {
        "name": "Plan CASH",
        "description": "Treasury & money market",
        "strategy": "Interest-bearing treasuries and cash equivalents",
        "risk_level": "Conservative",
    },
    "plan_etf": {
        "name": "Plan ETF",
        "description": "Index ETF strategy",
        "strategy": "Broad market index tracking via SPY, QQQ, and leveraged variants",
        "risk_level": "Moderate",
    },
    "plan_a": {
        "name": "Plan A",
        "description": "Leveraged options strategy",
        "strategy": "Momentum-based leveraged options to maximize capital efficiency",
        "risk_level": "Aggressive",
    },
}


def get_plan_metadata(plan_id: str) -> Dict:
    """Get display metadata for a plan.

    Args:
        plan_id: One of 'plan_cash', 'plan_etf', 'plan_a'

    Returns:
        Dict with name, description, strategy, risk_level
    """
    return PLAN_METADATA.get(plan_id, {
        "name": plan_id,
        "description": "Unknown plan",
        "strategy": "",
        "risk_level": "Unknown",
    })


def compute_plan_performance(positions: List[Dict]) -> Dict[str, Dict]:
    """Aggregate position data by plan.

    Takes a list of position snapshots and returns per-plan aggregates.

    Args:
        positions: List of position dicts with keys:
            symbol, underlying_symbol (optional), instrument_type (optional),
            quantity, market_value, cost_basis, unrealized_pl

    Returns:
        Dict keyed by plan_id with aggregated values:
        {
            'plan_cash': {
                'market_value': 10000.0,
                'cost_basis': 9950.0,
                'unrealized_pl': 50.0,
                'position_count': 2,
                'allocation_pct': 45.5,
                'symbols': ['SGOV', 'Cash'],
            },
            ...
        }
    """
    plans = {}
    total_value = 0.0

    for pos in positions:
        plan_id = classify_position_by_underlying(
            symbol=pos.get("symbol", ""),
            underlying_symbol=pos.get("underlying_symbol"),
            instrument_type=pos.get("instrument_type"),
        )

        if plan_id not in plans:
            plans[plan_id] = {
                "market_value": 0.0,
                "cost_basis": 0.0,
                "unrealized_pl": 0.0,
                "position_count": 0,
                "allocation_pct": 0.0,
                "symbols": [],
            }

        mv = pos.get("market_value") or 0.0
        cb = pos.get("cost_basis") or 0.0
        upl = pos.get("unrealized_pl") or 0.0

        plans[plan_id]["market_value"] += mv
        plans[plan_id]["cost_basis"] += cb
        plans[plan_id]["unrealized_pl"] += upl
        plans[plan_id]["position_count"] += 1
        plans[plan_id]["symbols"].append(pos.get("symbol", ""))
        total_value += mv

    # Calculate allocation percentages
    if total_value > 0:
        for plan_id in plans:
            plans[plan_id]["allocation_pct"] = round(
                (plans[plan_id]["market_value"] / total_value) * 100, 2
            )

    # Round financial values
    for plan_id in plans:
        plans[plan_id]["market_value"] = round(plans[plan_id]["market_value"], 2)
        plans[plan_id]["cost_basis"] = round(plans[plan_id]["cost_basis"], 2)
        plans[plan_id]["unrealized_pl"] = round(plans[plan_id]["unrealized_pl"], 2)

    return plans
