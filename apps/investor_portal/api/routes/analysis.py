"""
Portfolio Analysis Routes
=========================

GET /analysis/holdings            - Current holdings breakdown
GET /analysis/risk-metrics        - Risk metrics (Sharpe, drawdown, volatility)
GET /analysis/monthly-performance - Month-by-month returns grid
"""

import logging
import math
from datetime import date, timedelta
from typing import List, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..dependencies import get_current_user, CurrentUser
from ..models.database import get_connection

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Response Models
# ============================================================

class HoldingItem(BaseModel):
    """Single holding position"""
    symbol: str
    instrument_type: str
    quantity: float
    market_value: float
    cost_basis: Optional[float]
    unrealized_pl: Optional[float]
    unrealized_pl_pct: Optional[float]
    weight_pct: float


class HoldingsResponse(BaseModel):
    """Portfolio holdings breakdown"""
    snapshot_date: Optional[str]
    total_market_value: float
    total_unrealized_pl: float
    position_count: int
    holdings: List[HoldingItem]
    by_type: Dict[str, float]
    by_symbol: List[Dict]


class RiskMetricsResponse(BaseModel):
    """Risk and performance metrics"""
    period_start: str
    period_end: str
    trading_days: int
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: Optional[float]
    max_drawdown_pct: float
    max_drawdown_start: Optional[str]
    max_drawdown_end: Optional[str]
    annualized_volatility_pct: float
    best_day_date: Optional[str]
    best_day_pct: float
    worst_day_date: Optional[str]
    worst_day_pct: float
    positive_days: int
    negative_days: int
    win_rate_pct: float


class MonthlyPerfItem(BaseModel):
    """Single month performance"""
    month: str
    month_label: str
    start_nav: float
    end_nav: float
    return_pct: float
    min_nav: float
    max_nav: float
    trading_days: int


class MonthlyPerformanceResponse(BaseModel):
    """Month-by-month performance grid"""
    months: List[MonthlyPerfItem]
    best_month: Optional[str]
    best_month_return: float
    worst_month: Optional[str]
    worst_month_return: float


# ============================================================
# Routes
# ============================================================

@router.get("/holdings", response_model=HoldingsResponse)
async def get_holdings(
    user: CurrentUser = Depends(get_current_user),
):
    """
    Get current portfolio holdings breakdown.

    Returns positions from the latest holdings snapshot with market values,
    cost basis, unrealized P&L, and allocation weights.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get most recent snapshot
        cursor.execute("""
            SELECT snapshot_id, date
            FROM holdings_snapshots
            ORDER BY date DESC
            LIMIT 1
        """)
        snapshot = cursor.fetchone()

        if not snapshot:
            return HoldingsResponse(
                snapshot_date=None, total_market_value=0,
                total_unrealized_pl=0, position_count=0,
                holdings=[], by_type={}, by_symbol=[],
            )

        snapshot_id = snapshot['snapshot_id']
        snapshot_date = str(snapshot['date'])

        # Get all positions for this snapshot
        cursor.execute("""
            SELECT symbol, quantity, market_value, cost_basis,
                   unrealized_pl, instrument_type
            FROM position_snapshots
            WHERE snapshot_id = ?
            ORDER BY market_value DESC
        """, (snapshot_id,))
        positions = [dict(r) for r in cursor.fetchall()]

        # Aggregate options by underlying (strip option suffixes)
        aggregated = {}
        for pos in positions:
            symbol = pos['symbol']
            inst_type = pos.get('instrument_type', 'Other') or 'Other'

            # For options, group by underlying
            if 'Option' in inst_type and ' ' in symbol:
                key = symbol.split(' ')[0]  # underlying
            else:
                key = symbol

            if key not in aggregated:
                aggregated[key] = {
                    'symbol': key,
                    'instrument_type': inst_type,
                    'quantity': 0,
                    'market_value': 0,
                    'cost_basis': 0,
                    'unrealized_pl': 0,
                }
            aggregated[key]['market_value'] += pos.get('market_value', 0) or 0
            aggregated[key]['cost_basis'] += pos.get('cost_basis', 0) or 0
            aggregated[key]['unrealized_pl'] += pos.get('unrealized_pl', 0) or 0
            aggregated[key]['quantity'] += pos.get('quantity', 0) or 0

        holdings_list = list(aggregated.values())
        total_mv = sum(h['market_value'] for h in holdings_list)
        total_upl = sum(h['unrealized_pl'] for h in holdings_list)

        # Build response items
        items = []
        for h in sorted(holdings_list, key=lambda x: abs(x['market_value']), reverse=True):
            mv = h['market_value']
            cb = h['cost_basis']
            upl = h['unrealized_pl']
            upl_pct = (upl / cb * 100) if cb and cb != 0 else 0
            weight = (mv / total_mv * 100) if total_mv else 0

            items.append(HoldingItem(
                symbol=h['symbol'],
                instrument_type=h['instrument_type'],
                quantity=round(h['quantity'], 4),
                market_value=round(mv, 2),
                cost_basis=round(cb, 2) if cb else None,
                unrealized_pl=round(upl, 2),
                unrealized_pl_pct=round(upl_pct, 2),
                weight_pct=round(weight, 2),
            ))

        # Allocation by instrument type
        by_type = {}
        for h in holdings_list:
            t = h['instrument_type']
            by_type[t] = by_type.get(t, 0) + h['market_value']
        by_type = {k: round(v, 2) for k, v in by_type.items()}

        # Allocation by symbol (top 8 + Other)
        sorted_by_mv = sorted(holdings_list, key=lambda x: abs(x['market_value']), reverse=True)
        by_symbol = []
        other_value = 0
        for i, h in enumerate(sorted_by_mv):
            if i < 8:
                by_symbol.append({'name': h['symbol'], 'value': round(abs(h['market_value']), 2)})
            else:
                other_value += abs(h['market_value'])
        if other_value > 0:
            by_symbol.append({'name': 'Other', 'value': round(other_value, 2)})

        return HoldingsResponse(
            snapshot_date=snapshot_date,
            total_market_value=round(total_mv, 2),
            total_unrealized_pl=round(total_upl, 2),
            position_count=len(items),
            holdings=items,
            by_type=by_type,
            by_symbol=by_symbol,
        )

    finally:
        conn.close()


@router.get("/risk-metrics", response_model=RiskMetricsResponse)
async def get_risk_metrics(
    user: CurrentUser = Depends(get_current_user),
    days: int = Query(default=365, le=730, description="Lookback period in days"),
):
    """
    Calculate risk and performance metrics from daily NAV history.

    Includes Sharpe ratio, max drawdown, volatility, best/worst days,
    and win rate.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT date, nav_per_share, daily_change_percent
            FROM daily_nav
            ORDER BY date DESC
            LIMIT ?
        """, (days,))
        rows = [dict(r) for r in cursor.fetchall()]
        rows.reverse()  # oldest first

        if len(rows) < 2:
            return RiskMetricsResponse(
                period_start=rows[0]['date'] if rows else str(date.today()),
                period_end=rows[-1]['date'] if rows else str(date.today()),
                trading_days=len(rows),
                total_return_pct=0, annualized_return_pct=0,
                sharpe_ratio=None,
                max_drawdown_pct=0, max_drawdown_start=None, max_drawdown_end=None,
                annualized_volatility_pct=0,
                best_day_date=None, best_day_pct=0,
                worst_day_date=None, worst_day_pct=0,
                positive_days=0, negative_days=0, win_rate_pct=0,
            )

        start_nav = rows[0]['nav_per_share']
        end_nav = rows[-1]['nav_per_share']
        n_days = len(rows)
        period_start = rows[0]['date']
        period_end = rows[-1]['date']

        # Daily returns
        daily_returns = []
        for r in rows:
            pct = r.get('daily_change_percent')
            if pct is not None:
                daily_returns.append(pct)

        # Total return
        total_return = ((end_nav / start_nav) - 1) * 100 if start_nav > 0 else 0

        # Annualized return (252 trading days per year)
        years = n_days / 252
        ann_return = ((end_nav / start_nav) ** (1 / years) - 1) * 100 if years > 0 and start_nav > 0 else 0

        # Volatility (annualized)
        if len(daily_returns) > 1:
            mean_ret = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            daily_vol = math.sqrt(variance)
            ann_vol = daily_vol * math.sqrt(252)
        else:
            daily_vol = 0
            ann_vol = 0

        # Sharpe ratio (risk-free rate = 5.25%)
        risk_free = 5.25
        sharpe = (ann_return - risk_free) / ann_vol if ann_vol > 0 else None

        # Max drawdown
        peak = rows[0]['nav_per_share']
        max_dd = 0
        dd_start = rows[0]['date']
        dd_end = rows[0]['date']
        peak_date = rows[0]['date']
        current_dd_start = rows[0]['date']

        for r in rows:
            nav = r['nav_per_share']
            if nav > peak:
                peak = nav
                peak_date = r['date']
                current_dd_start = r['date']
            dd = ((nav - peak) / peak) * 100
            if dd < max_dd:
                max_dd = dd
                dd_start = current_dd_start
                dd_end = r['date']

        # Best / worst days
        best_day_date = None
        best_day_pct = 0
        worst_day_date = None
        worst_day_pct = 0

        for r in rows:
            pct = r.get('daily_change_percent')
            if pct is None:
                continue
            if pct > best_day_pct:
                best_day_pct = pct
                best_day_date = r['date']
            if pct < worst_day_pct:
                worst_day_pct = pct
                worst_day_date = r['date']

        # Win rate
        pos = sum(1 for r in daily_returns if r > 0)
        neg = sum(1 for r in daily_returns if r < 0)
        total_nonzero = pos + neg
        win_rate = (pos / total_nonzero * 100) if total_nonzero > 0 else 0

        return RiskMetricsResponse(
            period_start=str(period_start),
            period_end=str(period_end),
            trading_days=n_days,
            total_return_pct=round(total_return, 2),
            annualized_return_pct=round(ann_return, 2),
            sharpe_ratio=round(sharpe, 2) if sharpe is not None else None,
            max_drawdown_pct=round(max_dd, 2),
            max_drawdown_start=str(dd_start) if max_dd < 0 else None,
            max_drawdown_end=str(dd_end) if max_dd < 0 else None,
            annualized_volatility_pct=round(ann_vol, 2),
            best_day_date=str(best_day_date) if best_day_date else None,
            best_day_pct=round(best_day_pct, 2),
            worst_day_date=str(worst_day_date) if worst_day_date else None,
            worst_day_pct=round(worst_day_pct, 2),
            positive_days=pos,
            negative_days=neg,
            win_rate_pct=round(win_rate, 1),
        )

    finally:
        conn.close()


@router.get("/monthly-performance", response_model=MonthlyPerformanceResponse)
async def get_monthly_performance(
    user: CurrentUser = Depends(get_current_user),
):
    """
    Get month-by-month performance data.

    Uses the v_monthly_performance SQL view for efficient calculation.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT month, start_nav, end_nav, min_nav, max_nav, trading_days
            FROM v_monthly_performance
            ORDER BY month ASC
        """)
        rows = [dict(r) for r in cursor.fetchall()]

        months = []
        best_month = None
        best_return = -999
        worst_month = None
        worst_return = 999

        for r in rows:
            start_nav = r['start_nav']
            end_nav = r['end_nav']
            ret = ((end_nav / start_nav) - 1) * 100 if start_nav and start_nav > 0 else 0

            # Format month label (e.g., "Jan 2026")
            try:
                from datetime import datetime as dt
                month_dt = dt.strptime(r['month'] + '-01', '%Y-%m-%d')
                month_label = month_dt.strftime('%b %Y')
            except (ValueError, TypeError):
                month_label = r['month']

            months.append(MonthlyPerfItem(
                month=r['month'],
                month_label=month_label,
                start_nav=round(start_nav or 0, 4),
                end_nav=round(end_nav or 0, 4),
                return_pct=round(ret, 2),
                min_nav=round(r['min_nav'] or 0, 4),
                max_nav=round(r['max_nav'] or 0, 4),
                trading_days=r['trading_days'] or 0,
            ))

            if ret > best_return:
                best_return = ret
                best_month = month_label
            if ret < worst_return:
                worst_return = ret
                worst_month = month_label

        return MonthlyPerformanceResponse(
            months=months,
            best_month=best_month,
            best_month_return=round(best_return, 2) if best_month else 0,
            worst_month=worst_month,
            worst_month_return=round(worst_return, 2) if worst_month else 0,
        )

    finally:
        conn.close()
