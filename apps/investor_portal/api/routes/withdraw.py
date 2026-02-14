"""
Withdrawal Routes
==================

GET  /withdraw/estimate      - Calculate tax estimate for withdrawal
POST /withdraw/request       - Submit withdrawal request
GET  /withdraw/pending       - View pending requests
DELETE /withdraw/cancel/{id} - Cancel pending request
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from ..dependencies import get_current_user, CurrentUser
from ..config import settings
from ..models.database import (
    get_investor_position,
    calculate_withdrawal_estimate,
    create_withdrawal_request,
    get_pending_withdrawals,
    cancel_withdrawal_request
)


router = APIRouter()


# ============================================================
# Request/Response Models
# ============================================================

class WithdrawEstimateRequest(BaseModel):
    """Request for withdrawal estimate"""
    amount: float = Field(..., gt=0, description="Withdrawal amount in dollars")


class WithdrawEstimateResponse(BaseModel):
    """Estimated withdrawal breakdown"""
    requested_amount: float
    current_value: float
    proportion_of_account: float  # percentage
    
    # Breakdown
    principal_portion: float
    gain_portion: float
    
    # Tax calculation
    estimated_realized_gain: float
    estimated_tax: float
    estimated_net_proceeds: float
    
    # Rate used
    tax_rate: float
    
    # Disclaimer
    note: str = "Estimates based on current values. Actual amounts calculated at time of processing."


class WithdrawRequestInput(BaseModel):
    """Withdrawal request submission"""
    amount: float = Field(..., gt=0, description="Withdrawal amount")
    method: str = Field(..., description="Payment method: ACH, Wire, Check")
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes")


class WithdrawRequestResponse(BaseModel):
    """Withdrawal request confirmation"""
    request_id: int
    status: str
    requested_amount: float
    estimated_net_proceeds: float
    message: str


class PendingWithdrawal(BaseModel):
    """Pending withdrawal request"""
    id: int
    request_date: str
    requested_amount: float
    method: str
    status: str
    estimated_tax: float
    estimated_net: float
    notes: Optional[str]


class PendingWithdrawalsResponse(BaseModel):
    """List of pending withdrawals"""
    pending: List[PendingWithdrawal]
    total_pending_amount: float


# ============================================================
# Routes
# ============================================================

@router.get("/estimate", response_model=WithdrawEstimateResponse)
async def get_withdrawal_estimate(
    amount: float,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Calculate estimated tax and net proceeds for a withdrawal.
    
    This shows the investor what they would receive after tax withholding.
    Uses the proportional tax calculation (average cost method).
    """
    # Get current position
    position = get_investor_position(user.investor_id)
    
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    
    current_value = position["current_value"]
    
    # Validate amount
    if amount > current_value:
        raise HTTPException(
            status_code=400,
            detail=f"Withdrawal amount ${amount:,.2f} exceeds account value ${current_value:,.2f}"
        )
    
    if amount < 10:
        raise HTTPException(
            status_code=400,
            detail="Minimum withdrawal is $10.00"
        )
    
    # Calculate estimate
    estimate = calculate_withdrawal_estimate(
        investor_id=user.investor_id,
        amount=amount,
        tax_rate=settings.TAX_RATE
    )
    
    return WithdrawEstimateResponse(
        requested_amount=amount,
        current_value=current_value,
        proportion_of_account=estimate["proportion"] * 100,
        principal_portion=estimate["principal_portion"],
        gain_portion=estimate["gain_portion"],
        estimated_realized_gain=estimate["realized_gain"],
        estimated_tax=estimate["tax"],
        estimated_net_proceeds=estimate["net_proceeds"],
        tax_rate=settings.TAX_RATE
    )


@router.post("/request", response_model=WithdrawRequestResponse)
async def submit_withdrawal_request(
    request: WithdrawRequestInput,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Submit a withdrawal request.
    
    The request will be reviewed by the fund administrator.
    You will receive email confirmation when submitted and when processed.
    """
    # Validate method
    valid_methods = ["ACH", "Wire", "Check"]
    if request.method not in valid_methods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid method. Must be one of: {', '.join(valid_methods)}"
        )
    
    # Get current position for validation
    position = get_investor_position(user.investor_id)
    
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    
    if request.amount > position["current_value"]:
        raise HTTPException(
            status_code=400,
            detail=f"Withdrawal amount exceeds account value"
        )
    
    if request.amount < 10:
        raise HTTPException(
            status_code=400,
            detail="Minimum withdrawal is $10.00"
        )
    
    # Calculate estimate for response
    estimate = calculate_withdrawal_estimate(
        investor_id=user.investor_id,
        amount=request.amount,
        tax_rate=settings.TAX_RATE
    )
    
    # Create the request
    try:
        request_id = create_withdrawal_request(
            investor_id=user.investor_id,
            amount=request.amount,
            method=request.method,
            notes=request.notes,
            estimated_tax=estimate["tax"],
            estimated_net=estimate["net_proceeds"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create withdrawal request: {str(e)}"
        )
    
    return WithdrawRequestResponse(
        request_id=request_id,
        status="PENDING",
        requested_amount=request.amount,
        estimated_net_proceeds=estimate["net_proceeds"],
        message="Withdrawal request submitted successfully. You will receive an email confirmation."
    )


@router.get("/pending", response_model=PendingWithdrawalsResponse)
async def get_pending_requests(user: CurrentUser = Depends(get_current_user)):
    """
    Get list of pending withdrawal requests.
    
    Shows all requests that have not yet been processed.
    """
    pending = get_pending_withdrawals(user.investor_id)
    
    total = sum(p["requested_amount"] for p in pending)
    
    return PendingWithdrawalsResponse(
        pending=[
            PendingWithdrawal(
                id=p["id"],
                request_date=str(p["request_date"]),
                requested_amount=p["requested_amount"],
                method=p["method"],
                status=p["status"],
                estimated_tax=p.get("estimated_tax", 0),
                estimated_net=p.get("estimated_net", 0),
                notes=p.get("notes")
            )
            for p in pending
        ],
        total_pending_amount=total
    )


@router.delete("/cancel/{request_id}")
async def cancel_request(
    request_id: int,
    user: CurrentUser = Depends(get_current_user)
):
    """
    Cancel a pending withdrawal request.
    
    Only requests with status PENDING can be cancelled.
    """
    success = cancel_withdrawal_request(
        request_id=request_id,
        investor_id=user.investor_id  # Ensure user owns this request
    )
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Request not found or cannot be cancelled"
        )
    
    return {"message": "Withdrawal request cancelled successfully"}
