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


class RollingReturnPoint(BaseModel):
    """Single data point for rolling returns"""
    date: str
    rolling_30d: Optional[float]
    rolling_90d: Optional[float]


class RollingReturnsResponse(BaseModel):
    """Rolling return series"""
    data: List[RollingReturnPoint]


class BenchmarkComparisonItem(BaseModel):
    """Comparison vs a single benchmark"""
    ticker: str
    label: str
    fund_return: float
    benchmark_return: float
    outperformance: float


class BenchmarkComparisonResponse(BaseModel):
    """Fund vs benchmark comparison for a period"""
    period_days: int
    period_label: str
    comparisons: List[BenchmarkComparisonItem]


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


@router.get("/rolling-returns", response_model=RollingReturnsResponse)
async def get_rolling_returns(
    user: CurrentUser = Depends(get_current_user),
    days: int = Query(default=365, le=730, description="Lookback period in days"),
):
    """
    Calculate rolling 30-day and 90-day return series.

    For each day, computes the percentage return over the trailing
    30 and 90 calendar days respectively.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT date, nav_per_share
            FROM daily_nav
            ORDER BY date DESC
            LIMIT ?
        """, (days,))
        rows = [dict(r) for r in cursor.fetchall()]
        rows.reverse()  # oldest first

        if len(rows) < 2:
            return RollingReturnsResponse(data=[])

        # Build date -> nav lookup
        nav_by_date = {r['date']: r['nav_per_share'] for r in rows}
        dates_list = [r['date'] for r in rows]

        result = []
        for i, r in enumerate(rows):
            current_nav = r['nav_per_share']
            current_date = r['date']

            # Find NAV approximately 30 days ago
            rolling_30d = None
            target_30 = str(date.fromisoformat(current_date) - timedelta(days=30))
            # Find closest date on or before target
            nav_30 = _find_closest_nav(dates_list, nav_by_date, target_30, current_date)
            if nav_30 is not None and nav_30 > 0:
                rolling_30d = round(((current_nav / nav_30) - 1) * 100, 2)

            # Find NAV approximately 90 days ago
            rolling_90d = None
            target_90 = str(date.fromisoformat(current_date) - timedelta(days=90))
            nav_90 = _find_closest_nav(dates_list, nav_by_date, target_90, current_date)
            if nav_90 is not None and nav_90 > 0:
                rolling_90d = round(((current_nav / nav_90) - 1) * 100, 2)

            result.append(RollingReturnPoint(
                date=current_date,
                rolling_30d=rolling_30d,
                rolling_90d=rolling_90d,
            ))

        return RollingReturnsResponse(data=result)

    finally:
        conn.close()


def _find_closest_nav(dates_list, nav_by_date, target_date, current_date):
    """Find the NAV value for the date closest to (but not after) target_date.

    Returns None if no suitable date found.
    """
    best_date = None
    for d in dates_list:
        if d > current_date:
            break
        if d <= target_date:
            best_date = d
    return nav_by_date.get(best_date) if best_date else None


@router.get("/benchmark-comparison", response_model=BenchmarkComparisonResponse)
async def get_benchmark_comparison(
    user: CurrentUser = Depends(get_current_user),
    days: int = Query(default=90, le=730, description="Comparison period in days"),
):
    """
    Compare fund performance vs SPY, QQQ, and BTC-USD.

    Returns the fund return, each benchmark return, and the
    outperformance (fund - benchmark) for the given period.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cutoff = str(date.today() - timedelta(days=days))

        # Fund return
        cursor.execute("""
            SELECT nav_per_share FROM daily_nav
            WHERE date >= ? ORDER BY date ASC LIMIT 1
        """, (cutoff,))
        start_row = cursor.fetchone()

        cursor.execute("""
            SELECT nav_per_share FROM daily_nav
            ORDER BY date DESC LIMIT 1
        """)
        end_row = cursor.fetchone()

        if not start_row or not end_row:
            return BenchmarkComparisonResponse(
                period_days=days, period_label=_period_label(days),
                comparisons=[],
            )

        fund_start = start_row['nav_per_share']
        fund_end = end_row['nav_per_share']
        fund_return = ((fund_end / fund_start) - 1) * 100 if fund_start > 0 else 0

        # Benchmark returns
        benchmarks = [
            ('SPY', 'S&P 500'),
            ('QQQ', 'Nasdaq 100'),
            ('BTC-USD', 'Bitcoin'),
        ]

        comparisons = []
        for ticker, label in benchmarks:
            cursor.execute("""
                SELECT close_price FROM benchmark_prices
                WHERE ticker = ? AND date >= ?
                ORDER BY date ASC LIMIT 1
            """, (ticker, cutoff))
            b_start = cursor.fetchone()

            cursor.execute("""
                SELECT close_price FROM benchmark_prices
                WHERE ticker = ?
                ORDER BY date DESC LIMIT 1
            """, (ticker,))
            b_end = cursor.fetchone()

            if b_start and b_end and b_start['close_price'] > 0:
                b_return = ((b_end['close_price'] / b_start['close_price']) - 1) * 100
            else:
                b_return = 0.0

            comparisons.append(BenchmarkComparisonItem(
                ticker=ticker,
                label=label,
                fund_return=round(fund_return, 2),
                benchmark_return=round(b_return, 2),
                outperformance=round(fund_return - b_return, 2),
            ))

        return BenchmarkComparisonResponse(
            period_days=days,
            period_label=_period_label(days),
            comparisons=comparisons,
        )

    finally:
        conn.close()


class HistoricalPerformerItem(BaseModel):
    """A ticker's historical P&L from position snapshots."""
    symbol: str
    best_unrealized_pl: Optional[float]
    best_unrealized_pl_pct: Optional[float]
    worst_unrealized_pl: Optional[float]
    worst_unrealized_pl_pct: Optional[float]
    latest_unrealized_pl: Optional[float]
    latest_unrealized_pl_pct: Optional[float]
    first_seen: Optional[str]
    last_seen: Optional[str]


class HistoricalPerformersResponse(BaseModel):
    """Top and bottom performers from historical position snapshots."""
    top_performers: List[HistoricalPerformerItem]
    bottom_performers: List[HistoricalPerformerItem]
    period_start: Optional[str]
    period_end: Optional[str]


@router.get("/historical-performers", response_model=HistoricalPerformersResponse)
async def get_historical_performers(
    user: CurrentUser = Depends(get_current_user),
    days: int = Query(default=730, ge=1, le=730, description="Lookback period in days"),
):
    """
    Get best and worst performing positions from historical snapshots.

    Queries position_snapshots across all historical holdings_snapshots
    to find tickers with the best and worst unrealized P&L percentages.
    Includes both current and past positions.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cutoff = str(date.today() - timedelta(days=days))

        # Get all position snapshots within the date range, aggregate by symbol
        cursor.execute("""
            SELECT
                ps.symbol,
                MIN(hs.date) as first_seen,
                MAX(hs.date) as last_seen,
                MAX(ps.unrealized_pl) as best_unrealized_pl,
                MIN(ps.unrealized_pl) as worst_unrealized_pl,
                SUM(CASE WHEN hs.date = (
                    SELECT MAX(hs2.date)
                    FROM holdings_snapshots hs2
                    JOIN position_snapshots ps2 ON ps2.snapshot_id = hs2.snapshot_id
                    WHERE ps2.symbol = ps.symbol AND hs2.date >= ?
                ) THEN ps.unrealized_pl ELSE NULL END) as latest_pl,
                SUM(CASE WHEN hs.date = (
                    SELECT MAX(hs2.date)
                    FROM holdings_snapshots hs2
                    JOIN position_snapshots ps2 ON ps2.snapshot_id = hs2.snapshot_id
                    WHERE ps2.symbol = ps.symbol AND hs2.date >= ?
                ) THEN ps.cost_basis ELSE NULL END) as latest_cost_basis,
                MAX(CASE WHEN ps.cost_basis > 0
                    THEN (ps.unrealized_pl / ps.cost_basis * 100)
                    ELSE NULL END) as best_pl_pct,
                MIN(CASE WHEN ps.cost_basis > 0
                    THEN (ps.unrealized_pl / ps.cost_basis * 100)
                    ELSE NULL END) as worst_pl_pct
            FROM position_snapshots ps
            JOIN holdings_snapshots hs ON hs.snapshot_id = ps.snapshot_id
            WHERE hs.date >= ?
              AND ps.symbol NOT IN ('Cash', 'CASH')
              AND ps.instrument_type NOT LIKE '%%Cash%%'
            GROUP BY ps.symbol
            HAVING MAX(ABS(ps.cost_basis)) > 0
            ORDER BY best_pl_pct DESC
        """, (cutoff, cutoff, cutoff))

        rows = [dict(r) for r in cursor.fetchall()]

        # Build top performers (best unrealized P&L %)
        top_performers = []
        for row in rows[:5]:
            latest_pct = None
            if row.get('latest_cost_basis') and row['latest_cost_basis'] > 0 and row.get('latest_pl') is not None:
                latest_pct = round(row['latest_pl'] / row['latest_cost_basis'] * 100, 2)

            top_performers.append(HistoricalPerformerItem(
                symbol=row['symbol'].split(' ')[0] if ' ' in row['symbol'] else row['symbol'],
                best_unrealized_pl=round(row['best_unrealized_pl'], 2) if row.get('best_unrealized_pl') is not None else None,
                best_unrealized_pl_pct=round(row['best_pl_pct'], 2) if row.get('best_pl_pct') is not None else None,
                worst_unrealized_pl=round(row['worst_unrealized_pl'], 2) if row.get('worst_unrealized_pl') is not None else None,
                worst_unrealized_pl_pct=round(row['worst_pl_pct'], 2) if row.get('worst_pl_pct') is not None else None,
                latest_unrealized_pl=round(row['latest_pl'], 2) if row.get('latest_pl') is not None else None,
                latest_unrealized_pl_pct=latest_pct,
                first_seen=row.get('first_seen'),
                last_seen=row.get('last_seen'),
            ))

        # Bottom performers (worst unrealized P&L %) — sort ascending
        sorted_worst = sorted(rows, key=lambda r: r.get('worst_pl_pct') or 0)
        bottom_performers = []
        for row in sorted_worst[:5]:
            latest_pct = None
            if row.get('latest_cost_basis') and row['latest_cost_basis'] > 0 and row.get('latest_pl') is not None:
                latest_pct = round(row['latest_pl'] / row['latest_cost_basis'] * 100, 2)

            bottom_performers.append(HistoricalPerformerItem(
                symbol=row['symbol'].split(' ')[0] if ' ' in row['symbol'] else row['symbol'],
                best_unrealized_pl=round(row['best_unrealized_pl'], 2) if row.get('best_unrealized_pl') is not None else None,
                best_unrealized_pl_pct=round(row['best_pl_pct'], 2) if row.get('best_pl_pct') is not None else None,
                worst_unrealized_pl=round(row['worst_unrealized_pl'], 2) if row.get('worst_unrealized_pl') is not None else None,
                worst_unrealized_pl_pct=round(row['worst_pl_pct'], 2) if row.get('worst_pl_pct') is not None else None,
                latest_unrealized_pl=round(row['latest_pl'], 2) if row.get('latest_pl') is not None else None,
                latest_unrealized_pl_pct=latest_pct,
                first_seen=row.get('first_seen'),
                last_seen=row.get('last_seen'),
            ))

        # Date range
        cursor.execute("SELECT MIN(date) as start_date, MAX(date) as end_date FROM holdings_snapshots WHERE date >= ?", (cutoff,))
        date_range = cursor.fetchone()

        return HistoricalPerformersResponse(
            top_performers=top_performers,
            bottom_performers=bottom_performers,
            period_start=str(date_range['start_date']) if date_range and date_range['start_date'] else None,
            period_end=str(date_range['end_date']) if date_range and date_range['end_date'] else None,
        )

    finally:
        conn.close()


def _period_label(days: int) -> str:
    """Human-readable period label."""
    if days <= 30:
        return "Last 30 Days"
    elif days <= 90:
        return "Last 90 Days"
    elif days <= 180:
        return "Last 6 Months"
    elif days <= 365:
        return "Last Year"
    else:
        return "Since Inception"


# ============================================================
# Plan Allocation & Performance
# ============================================================

class PlanMetadata(BaseModel):
    """Plan display information."""
    plan_id: str
    name: str
    description: str
    strategy: str
    risk_level: str


class PlanAllocationItem(BaseModel):
    """Single plan in the allocation breakdown."""
    plan_id: str
    name: str
    description: str
    risk_level: str
    market_value: float
    cost_basis: float
    unrealized_pl: float
    allocation_pct: float
    position_count: int


class PlanAllocationResponse(BaseModel):
    """Current plan allocation breakdown."""
    as_of_date: str
    plans: List[PlanAllocationItem]
    total_market_value: float


class PlanPerformancePoint(BaseModel):
    """Single day of plan performance history."""
    date: str
    plan_id: str
    allocation_pct: float
    market_value: float


class PlanPerformanceResponse(BaseModel):
    """Plan performance time series."""
    days: int
    series: Dict[str, List[PlanPerformancePoint]]


@router.get("/plan-allocation", response_model=PlanAllocationResponse)
async def get_plan_allocation(
    user: CurrentUser = Depends(get_current_user),
):
    """
    Get the current plan allocation breakdown.

    Returns the latest per-plan market_value, cost_basis, unrealized_pl,
    allocation_pct, and position_count along with plan metadata.
    """
    try:
        from src.plans.classification import get_plan_metadata

        conn = get_connection()
        cursor = conn.cursor()

        # Get the latest date with plan data
        cursor.execute("""
            SELECT date FROM plan_daily_performance
            ORDER BY date DESC LIMIT 1
        """)
        row = cursor.fetchone()
        if not row:
            conn.close()
            return PlanAllocationResponse(
                as_of_date="",
                plans=[],
                total_market_value=0.0,
            )

        latest_date = row["date"]

        # Get all plans for that date
        cursor.execute("""
            SELECT plan_id, market_value, cost_basis, unrealized_pl,
                   allocation_pct, position_count
            FROM plan_daily_performance
            WHERE date = ?
            ORDER BY allocation_pct DESC
        """, (latest_date,))
        rows = cursor.fetchall()
        conn.close()

        plans = []
        total_mv = 0.0
        for r in rows:
            meta = get_plan_metadata(r["plan_id"])
            plans.append(PlanAllocationItem(
                plan_id=r["plan_id"],
                name=meta["name"],
                description=meta["description"],
                risk_level=meta["risk_level"],
                market_value=round(r["market_value"], 2),
                cost_basis=round(r["cost_basis"], 2),
                unrealized_pl=round(r["unrealized_pl"], 2),
                allocation_pct=round(r["allocation_pct"], 2),
                position_count=r["position_count"],
            ))
            total_mv += r["market_value"]

        return PlanAllocationResponse(
            as_of_date=latest_date,
            plans=plans,
            total_market_value=round(total_mv, 2),
        )

    except Exception as e:
        logger.error(f"Plan allocation error: {ascii(str(e))}")
        return PlanAllocationResponse(
            as_of_date="",
            plans=[],
            total_market_value=0.0,
        )


@router.get("/plan-performance", response_model=PlanPerformanceResponse)
async def get_plan_performance(
    user: CurrentUser = Depends(get_current_user),
    days: int = Query(default=90, ge=7, le=730),
):
    """
    Get plan performance time series.

    Returns allocation_pct and market_value per plan per day,
    grouped by plan_id for easy charting.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        since_date = (date.today() - timedelta(days=days)).isoformat()

        cursor.execute("""
            SELECT date, plan_id, allocation_pct, market_value
            FROM plan_daily_performance
            WHERE date >= ?
            ORDER BY date ASC
        """, (since_date,))
        rows = cursor.fetchall()
        conn.close()

        series: Dict[str, List[PlanPerformancePoint]] = {}
        for r in rows:
            pid = r["plan_id"]
            if pid not in series:
                series[pid] = []
            series[pid].append(PlanPerformancePoint(
                date=r["date"],
                plan_id=pid,
                allocation_pct=round(r["allocation_pct"], 2),
                market_value=round(r["market_value"], 2),
            ))

        return PlanPerformanceResponse(days=days, series=series)

    except Exception as e:
        logger.error(f"Plan performance error: {ascii(str(e))}")
        return PlanPerformanceResponse(days=days, series={})
