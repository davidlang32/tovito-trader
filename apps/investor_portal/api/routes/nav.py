"""
NAV Routes
===========

GET /nav/current         - Get current NAV
GET /nav/history         - Get NAV history for charts
GET /nav/performance     - Get fund performance metrics
GET /nav/benchmark-chart - Get NAV vs Benchmarks chart (PNG image)
GET /nav/benchmark-data  - Get benchmark comparison data (JSON)
"""

import io
import logging
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import date
from pathlib import Path

from ..dependencies import get_current_user, CurrentUser
from ..config import get_database_path
from ..models.database import (
    get_current_nav,
    get_nav_history,
    get_fund_performance,
    get_cached_benchmark_data,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Response Models
# ============================================================

class CurrentNAVResponse(BaseModel):
    """Current NAV data"""
    date: str
    nav_per_share: float
    total_portfolio_value: float
    total_shares: float
    daily_change_dollars: float
    daily_change_percent: float


class NAVHistoryItem(BaseModel):
    """Single NAV history entry"""
    date: str
    nav_per_share: float
    daily_change_percent: Optional[float]


class NAVHistoryResponse(BaseModel):
    """NAV history for charts"""
    current: CurrentNAVResponse
    history: List[NAVHistoryItem]


class PerformanceResponse(BaseModel):
    """Fund performance metrics"""
    # Current
    current_nav: float
    current_date: str

    # Returns
    daily_return: float
    wtd_return: float  # Week to date
    mtd_return: float  # Month to date
    ytd_return: float  # Year to date
    since_inception: float

    # Inception
    inception_date: str
    inception_nav: float

    # Fund size
    total_portfolio_value: float
    total_investors: int


class BenchmarkSeriesItem(BaseModel):
    """Single data point in a benchmark series"""
    date: str
    pct_change: float


class FundDataItem(BaseModel):
    """Single data point for the fund series (includes raw NAV)"""
    date: str
    nav_per_share: float
    pct_change: float


class BenchmarkDataResponse(BaseModel):
    """Benchmark comparison data for charting"""
    fund: List[FundDataItem]
    benchmarks: Dict[str, List[BenchmarkSeriesItem]]


# ============================================================
# Routes
# ============================================================

@router.get("/current", response_model=CurrentNAVResponse)
async def get_nav_current(user: CurrentUser = Depends(get_current_user)):
    """
    Get current NAV per share.

    Returns the latest NAV and daily change.
    """
    nav = get_current_nav()

    return CurrentNAVResponse(
        date=str(nav["date"]),
        nav_per_share=nav["nav_per_share"],
        total_portfolio_value=nav["total_portfolio_value"],
        total_shares=nav["total_shares"],
        daily_change_dollars=nav.get("daily_change_dollars", 0),
        daily_change_percent=nav.get("daily_change_percent", 0)
    )


@router.get("/history", response_model=NAVHistoryResponse)
async def get_nav_history_route(
    user: CurrentUser = Depends(get_current_user),
    days: int = Query(default=30, le=365, description="Number of days of history"),
    start_date: Optional[date] = Query(default=None, description="Start date"),
    end_date: Optional[date] = Query(default=None, description="End date")
):
    """
    Get NAV history for charts.

    Returns daily NAV values for the specified period.
    Default is last 30 days.
    """
    # Get current NAV
    current = get_current_nav()

    # Get history
    history = get_nav_history(
        days=days,
        start_date=start_date,
        end_date=end_date
    )

    return NAVHistoryResponse(
        current=CurrentNAVResponse(
            date=str(current["date"]),
            nav_per_share=current["nav_per_share"],
            total_portfolio_value=current["total_portfolio_value"],
            total_shares=current["total_shares"],
            daily_change_dollars=current.get("daily_change_dollars", 0),
            daily_change_percent=current.get("daily_change_percent", 0)
        ),
        history=[
            NAVHistoryItem(
                date=str(h["date"]),
                nav_per_share=h["nav_per_share"],
                daily_change_percent=h.get("daily_change_percent")
            )
            for h in history
        ]
    )


@router.get("/performance", response_model=PerformanceResponse)
async def get_performance(user: CurrentUser = Depends(get_current_user)):
    """
    Get fund performance metrics.

    Returns various return calculations and fund statistics.
    """
    perf = get_fund_performance()

    return PerformanceResponse(
        current_nav=perf["current_nav"],
        current_date=str(perf["current_date"]),
        daily_return=perf["daily_return"],
        wtd_return=perf["wtd_return"],
        mtd_return=perf["mtd_return"],
        ytd_return=perf["ytd_return"],
        since_inception=perf["since_inception"],
        inception_date=str(perf["inception_date"]),
        inception_nav=perf["inception_nav"],
        total_portfolio_value=perf["total_portfolio_value"],
        total_investors=perf["total_investors"]
    )


@router.get("/benchmark-chart")
async def get_benchmark_chart(
    user: CurrentUser = Depends(get_current_user),
    days: int = Query(default=90, le=730, description="Days of history"),
):
    """
    Generate NAV vs Benchmarks chart as PNG image.

    Returns a server-rendered chart showing fund performance
    against SPY, QQQ, and BTC with a NAV mountain background.
    """
    try:
        # Get NAV history (oldest first for chart)
        nav_history_raw = get_nav_history(days=days)
        nav_history = [
            {'date': str(h['date']), 'nav_per_share': h['nav_per_share']}
            for h in reversed(nav_history_raw)
        ]

        # Get benchmark data from cache
        benchmark_data = get_cached_benchmark_data(days=days)

        # Generate chart
        from src.reporting.charts import generate_benchmark_chart
        chart_path = generate_benchmark_chart(nav_history, benchmark_data)

        # Read the PNG into memory and clean up temp file
        chart_bytes = chart_path.read_bytes()
        chart_path.unlink(missing_ok=True)

        return StreamingResponse(
            io.BytesIO(chart_bytes),
            media_type="image/png",
            headers={"Cache-Control": "max-age=3600"},
        )

    except Exception as e:
        logger.error(f"Benchmark chart generation failed: {e}")
        # Return a simple error chart
        from src.reporting.charts import _generate_empty_chart
        fallback_path = _generate_empty_chart(
            "Fund vs. Benchmarks",
            "Chart temporarily unavailable"
        )
        fallback_bytes = fallback_path.read_bytes()
        fallback_path.unlink(missing_ok=True)

        return StreamingResponse(
            io.BytesIO(fallback_bytes),
            media_type="image/png",
        )


@router.get("/benchmark-data", response_model=BenchmarkDataResponse)
async def get_benchmark_data_route(
    user: CurrentUser = Depends(get_current_user),
    days: int = Query(default=90, le=730, description="Days of history"),
):
    """
    Get benchmark comparison data as JSON.

    Returns normalized performance data for the fund and each benchmark,
    suitable for building interactive charts on the frontend.
    """
    from src.market_data.benchmarks import normalize_series

    # Get NAV history (oldest first)
    nav_history_raw = get_nav_history(days=days)
    nav_history = list(reversed(nav_history_raw))

    # Normalize fund NAV
    fund_series = normalize_series(
        [{'date': str(h['date']), 'close_price': h['nav_per_share']} for h in nav_history],
        price_key='close_price',
    )

    # Get and normalize benchmark data
    benchmark_data = get_cached_benchmark_data(days=days)
    benchmarks = {}
    for ticker, series in benchmark_data.items():
        if series:
            normalized = normalize_series(series)
            benchmarks[ticker] = [
                BenchmarkSeriesItem(date=p['date'], pct_change=p['pct_change'])
                for p in normalized
            ]
        else:
            benchmarks[ticker] = []

    return BenchmarkDataResponse(
        fund=[
            FundDataItem(
                date=p['date'],
                nav_per_share=h['nav_per_share'],
                pct_change=p['pct_change'],
            )
            for h, p in zip(nav_history, fund_series)
        ],
        benchmarks=benchmarks,
    )
