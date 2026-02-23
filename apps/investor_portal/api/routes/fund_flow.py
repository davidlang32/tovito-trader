"""
Fund Flow API Routes
====================

Unified contribution/withdrawal request lifecycle endpoints.
All endpoints require authentication.

Endpoints:
    POST   /fund-flow/request     — Submit a new contribution or withdrawal request
    GET    /fund-flow/requests    — List investor's requests (all statuses)
    GET    /fund-flow/estimate    — Get tax/share estimate before submitting
    DELETE /fund-flow/cancel/{id} — Cancel a pending/approved request
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional

from ..dependencies import get_current_user, CurrentUser
from ..models.database import (
    create_fund_flow_request,
    get_fund_flow_requests,
    cancel_fund_flow_request,
    get_fund_flow_estimate,
    get_investor_position,
)

router = APIRouter()


# ============================================================
# REQUEST / RESPONSE MODELS
# ============================================================

class FundFlowRequestInput(BaseModel):
    """Input for submitting a fund flow request."""
    flow_type: str = Field(
        ...,
        description="Type of request: 'contribution' or 'withdrawal'"
    )
    amount: float = Field(
        ...,
        gt=0,
        description="Requested amount in dollars (must be positive)"
    )
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional notes for the fund manager"
    )


class FundFlowRequestResponse(BaseModel):
    """Response after submitting a fund flow request."""
    request_id: int
    flow_type: str
    requested_amount: float
    status: str
    message: str


class FundFlowRequestDetail(BaseModel):
    """Detailed fund flow request for listing."""
    request_id: int
    flow_type: str
    requested_amount: float
    request_date: str
    request_method: str
    status: str
    approved_date: Optional[str] = None
    rejection_reason: Optional[str] = None
    matched_date: Optional[str] = None
    processed_date: Optional[str] = None
    actual_amount: Optional[float] = None
    shares_transacted: Optional[float] = None
    nav_per_share: Optional[float] = None
    realized_gain: Optional[float] = None
    tax_withheld: Optional[float] = None
    net_proceeds: Optional[float] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str


class FundFlowListResponse(BaseModel):
    """Response for listing fund flow requests."""
    requests: List[FundFlowRequestDetail]
    total: int


class FundFlowEstimateResponse(BaseModel):
    """Response for fund flow estimate."""
    flow_type: str
    amount: float
    current_nav: float
    estimated_shares: float
    # Contribution fields
    new_total_shares: Optional[float] = None
    # Withdrawal fields
    proportion: Optional[float] = None
    realized_gain: Optional[float] = None
    estimated_tax: Optional[float] = None
    net_proceeds: Optional[float] = None
    remaining_shares: Optional[float] = None
    eligible_withdrawal: Optional[float] = None
    note: Optional[str] = None


# ============================================================
# ENDPOINTS
# ============================================================

@router.post("/request", response_model=FundFlowRequestResponse, status_code=201)
async def submit_fund_flow_request(
    request: FundFlowRequestInput,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Submit a new contribution or withdrawal request.

    The request enters 'pending' status and awaits fund manager approval.
    For withdrawals, use the /estimate endpoint first to preview tax impact.
    """
    # Validate flow type
    if request.flow_type not in ('contribution', 'withdrawal'):
        raise HTTPException(
            status_code=400,
            detail="flow_type must be 'contribution' or 'withdrawal'"
        )

    # For withdrawals, validate against current position
    if request.flow_type == 'withdrawal':
        position = get_investor_position(user.investor_id)
        if position is None:
            raise HTTPException(
                status_code=404,
                detail="Investor position not found"
            )
        if request.amount > position["current_value"]:
            raise HTTPException(
                status_code=400,
                detail=f"Requested amount exceeds current value of "
                       f"${position['current_value']:,.2f}"
            )

    try:
        request_id = create_fund_flow_request(
            investor_id=user.investor_id,
            flow_type=request.flow_type,
            amount=request.amount,
            method='portal',
            notes=request.notes,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create request: {str(e)}"
        )

    return FundFlowRequestResponse(
        request_id=request_id,
        flow_type=request.flow_type,
        requested_amount=request.amount,
        status="pending",
        message=f"{request.flow_type.title()} request submitted successfully. "
                f"Awaiting fund manager approval."
    )


@router.get("/requests", response_model=FundFlowListResponse)
async def list_fund_flow_requests(
    status: Optional[str] = Query(None, description="Filter by status"),
    flow_type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
):
    """
    List the authenticated investor's fund flow requests.

    Optionally filter by status or flow_type. Returns most recent first.
    """
    # Validate filters
    valid_statuses = ('pending', 'approved', 'awaiting_funds', 'matched',
                      'processed', 'rejected', 'cancelled')
    if status and status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )

    if flow_type and flow_type not in ('contribution', 'withdrawal'):
        raise HTTPException(
            status_code=400,
            detail="flow_type must be 'contribution' or 'withdrawal'"
        )

    requests = get_fund_flow_requests(
        investor_id=user.investor_id,
        status=status,
        flow_type=flow_type,
        limit=limit,
    )

    return FundFlowListResponse(
        requests=[FundFlowRequestDetail(**r) for r in requests],
        total=len(requests),
    )


@router.get("/estimate", response_model=FundFlowEstimateResponse)
async def get_estimate(
    flow_type: str = Query(..., description="'contribution' or 'withdrawal'"),
    amount: float = Query(..., gt=0, description="Amount in dollars"),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Get a tax/share estimate for a proposed contribution or withdrawal.

    For contributions: shows estimated shares to purchase at current NAV.
    For withdrawals: shows estimated realized gain, tax, and net proceeds.

    This is an estimate only — actual values calculated at processing time.
    """
    if flow_type not in ('contribution', 'withdrawal'):
        raise HTTPException(
            status_code=400,
            detail="flow_type must be 'contribution' or 'withdrawal'"
        )

    try:
        estimate = get_fund_flow_estimate(
            investor_id=user.investor_id,
            flow_type=flow_type,
            amount=amount,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return FundFlowEstimateResponse(**estimate)


@router.delete("/cancel/{request_id}")
async def cancel_request(
    request_id: int,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Cancel a pending or approved fund flow request.

    Only requests in 'pending' or 'approved' status can be cancelled.
    The request must belong to the authenticated investor.
    """
    success = cancel_fund_flow_request(
        request_id=request_id,
        investor_id=user.investor_id,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Request not found, already processed, or not owned by you"
        )

    return {
        "message": f"Request #{request_id} has been cancelled",
        "request_id": request_id,
        "status": "cancelled",
    }
