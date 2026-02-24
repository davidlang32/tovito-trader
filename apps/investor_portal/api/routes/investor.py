"""
Investor Routes
================

GET /investor/profile       - Get investor profile
GET /investor/position      - Get current position and returns
GET /investor/transactions  - Get transaction history
GET /investor/statements    - List available statements
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import date

from ..dependencies import get_current_user, CurrentUser
from ..models.database import (
    get_investor_by_id,
    get_investor_position,
    get_investor_transactions,
    get_available_statements
)


router = APIRouter()


# ============================================================
# Response Models
# ============================================================

class ProfileResponse(BaseModel):
    """Investor profile"""
    investor_id: str
    name: str
    email: str
    phone: Optional[str]
    join_date: str
    status: str


class PositionResponse(BaseModel):
    """Current position and returns"""
    investor_id: str
    name: str
    
    # Position
    current_shares: float
    current_nav: float
    current_value: float
    
    # Investment
    net_investment: float
    initial_capital: float
    
    # Returns
    total_return_dollars: float
    total_return_percent: float
    
    # Fund share
    portfolio_percentage: float

    # Cost basis
    avg_cost_per_share: float

    # Metadata
    as_of_date: str


class TransactionItem(BaseModel):
    """Single transaction"""
    date: str
    type: str
    amount: float
    shares: float
    nav_at_transaction: float
    notes: Optional[str]


class TransactionsResponse(BaseModel):
    """Transaction history"""
    transactions: List[TransactionItem]
    total_contributions: float
    total_withdrawals: float
    net_investment: float


class StatementItem(BaseModel):
    """Available statement"""
    period: str  # e.g., "2026-01"
    filename: str
    generated_date: str


class StatementsResponse(BaseModel):
    """List of available statements"""
    statements: List[StatementItem]


# ============================================================
# Routes
# ============================================================

@router.get("/profile", response_model=ProfileResponse)
async def get_profile(user: CurrentUser = Depends(get_current_user)):
    """
    Get investor profile information.
    
    Returns basic profile data for the logged-in investor.
    """
    investor = get_investor_by_id(user.investor_id)
    
    if investor is None:
        raise HTTPException(status_code=404, detail="Investor not found")
    
    return ProfileResponse(
        investor_id=investor["investor_id"],
        name=investor["name"],
        email=investor.get("email", ""),
        phone=investor.get("phone"),
        join_date=str(investor.get("join_date", "")),
        status=investor.get("status", "Unknown")
    )


@router.get("/position", response_model=PositionResponse)
async def get_position(user: CurrentUser = Depends(get_current_user)):
    """
    Get current position and investment returns.
    
    Returns:
    - Current shares and value
    - Total return (dollars and percent)
    - Portfolio percentage
    """
    position = get_investor_position(user.investor_id)
    
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    
    return PositionResponse(**position)


@router.get("/transactions", response_model=TransactionsResponse)
async def get_transactions(
    user: CurrentUser = Depends(get_current_user),
    limit: int = Query(default=50, le=200, description="Max transactions to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    start_date: Optional[date] = Query(default=None, description="Filter from date"),
    end_date: Optional[date] = Query(default=None, description="Filter to date"),
    transaction_type: Optional[str] = Query(default=None, description="Filter by type")
):
    """
    Get transaction history.
    
    Supports pagination and filtering by date range and type.
    """
    result = get_investor_transactions(
        investor_id=user.investor_id,
        limit=limit,
        offset=offset,
        start_date=start_date,
        end_date=end_date,
        transaction_type=transaction_type
    )
    
    transactions = [
        TransactionItem(
            date=str(t["date"]),
            type=t["transaction_type"],
            amount=t["amount"],
            shares=t["shares_transacted"],
            nav_at_transaction=t["share_price"],
            notes=t.get("notes")
        )
        for t in result["transactions"]
    ]
    
    return TransactionsResponse(
        transactions=transactions,
        total_contributions=result["total_contributions"],
        total_withdrawals=result["total_withdrawals"],
        net_investment=result["net_investment"]
    )


@router.get("/statements", response_model=StatementsResponse)
async def get_statements(user: CurrentUser = Depends(get_current_user)):
    """
    Get list of available monthly statements.
    
    Returns periods for which statements can be downloaded.
    """
    statements = get_available_statements(user.investor_id)
    
    return StatementsResponse(
        statements=[
            StatementItem(
                period=s["period"],
                filename=s["filename"],
                generated_date=s["generated_date"]
            )
            for s in statements
        ]
    )


@router.get("/statements/{period}")
async def download_statement(
    period: str,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Download a monthly statement PDF.
    
    Period format: YYYY-MM (e.g., 2026-01)
    """
    from fastapi.responses import FileResponse
    from pathlib import Path
    
    # Validate period format
    try:
        year, month = period.split("-")
        int(year)
        int(month)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid period format. Use YYYY-MM")
    
    # Find statement file
    # Filename pattern: {investor_id}_{year}_{month}_Statement.pdf
    reports_dir = Path(__file__).parent.parent.parent.parent.parent / "reports"
    filename = f"{user.investor_id}_{year}_{month}_Statement.pdf"
    filepath = reports_dir / filename
    
    if not filepath.exists():
        raise HTTPException(
            status_code=404, 
            detail=f"Statement not found for period {period}"
        )
    
    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/pdf"
    )
