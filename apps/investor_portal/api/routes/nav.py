"""
NAV Routes
===========

GET /nav/current     - Get current NAV
GET /nav/history     - Get NAV history for charts
GET /nav/performance - Get fund performance metrics
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import date

from ..dependencies import get_current_user, CurrentUser
from ..models.database import (
    get_current_nav,
    get_nav_history,
    get_fund_performance
)


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
