"""
Referral API Routes
====================

Endpoints for investor referral code management.

Endpoints:
    GET  /referral/code   — Get investor's referral code (generate if needed)
    GET  /referral/status — List referral outcomes and incentives
"""

import secrets
import string
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import date

from ..dependencies import get_current_user, CurrentUser
from ..models.database import get_connection

router = APIRouter()


# ============================================================
# MODELS
# ============================================================

class ReferralCodeResponse(BaseModel):
    """Response with the investor's referral code."""
    referral_code: str
    message: str


class ReferralDetail(BaseModel):
    """Detail of a single referral."""
    referral_code: str
    referred_name: Optional[str] = None
    referred_date: str
    status: str
    incentive_type: Optional[str] = None
    incentive_amount: Optional[float] = None
    incentive_paid: bool = False


class ReferralStatusResponse(BaseModel):
    """Response listing all referrals for an investor."""
    referrals: List[ReferralDetail]
    total: int
    total_incentive_earned: float
    total_incentive_paid: float


# ============================================================
# HELPERS
# ============================================================

def generate_unique_code(conn, max_attempts=10) -> str:
    """Generate a unique TOVITO-XXXXXX referral code."""
    chars = string.ascii_uppercase + string.digits
    for _ in range(max_attempts):
        code = 'TOVITO-' + ''.join(secrets.choice(chars) for _ in range(6))
        cursor = conn.execute(
            "SELECT referral_id FROM referrals WHERE referral_code = ?", (code,)
        )
        if not cursor.fetchone():
            return code
    raise RuntimeError("Failed to generate unique referral code")


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/code", response_model=ReferralCodeResponse)
async def get_referral_code(user: CurrentUser = Depends(get_current_user)):
    """
    Get the investor's referral code.

    If the investor doesn't have a code yet, one is generated automatically.
    Each investor gets one primary referral code.
    """
    conn = get_connection()
    try:
        # Check for existing code
        cursor = conn.execute("""
            SELECT referral_code FROM referrals
            WHERE referrer_investor_id = ?
            ORDER BY created_at ASC
            LIMIT 1
        """, (user.investor_id,))

        row = cursor.fetchone()
        if row:
            return ReferralCodeResponse(
                referral_code=row['referral_code'],
                message="Your referral code"
            )

        # Generate a new code
        code = generate_unique_code(conn)
        conn.execute("""
            INSERT INTO referrals (
                referrer_investor_id, referral_code, referred_date,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, 'pending', datetime('now'), datetime('now'))
        """, (user.investor_id, code, date.today().isoformat()))
        conn.commit()

        return ReferralCodeResponse(
            referral_code=code,
            message="New referral code generated"
        )

    finally:
        conn.close()


@router.get("/status", response_model=ReferralStatusResponse)
async def get_referral_status(user: CurrentUser = Depends(get_current_user)):
    """
    List all referrals made by the investor and their outcomes.

    Shows referred person details, status, and any incentives earned.
    """
    conn = get_connection()
    try:
        cursor = conn.execute("""
            SELECT referral_code, referred_name, referred_date,
                   status, incentive_type, incentive_amount, incentive_paid
            FROM referrals
            WHERE referrer_investor_id = ?
            ORDER BY referred_date DESC
        """, (user.investor_id,))

        referrals = []
        total_earned = 0.0
        total_paid = 0.0

        for row in cursor.fetchall():
            r = dict(row)
            referrals.append(ReferralDetail(
                referral_code=r['referral_code'],
                referred_name=r['referred_name'],
                referred_date=r['referred_date'],
                status=r['status'],
                incentive_type=r['incentive_type'],
                incentive_amount=r['incentive_amount'],
                incentive_paid=bool(r['incentive_paid']),
            ))
            if r['incentive_amount']:
                total_earned += r['incentive_amount']
                if r['incentive_paid']:
                    total_paid += r['incentive_amount']

        return ReferralStatusResponse(
            referrals=referrals,
            total=len(referrals),
            total_incentive_earned=round(total_earned, 2),
            total_incentive_paid=round(total_paid, 2),
        )

    finally:
        conn.close()
