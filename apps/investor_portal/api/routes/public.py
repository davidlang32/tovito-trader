"""
Public Routes (No Authentication Required)
============================================

GET  /public/teaser-stats  - Fund teaser stats for landing page
POST /public/inquiry       - Submit prospect inquiry from landing page

These endpoints are intentionally public and expose only
non-sensitive aggregate data. No dollar amounts, no NAV prices,
no individual investor data.
"""

import os
import secrets
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, EmailStr, Field

# Add project root for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ..models.database import (
    get_teaser_stats,
    create_prospect,
    store_prospect_verification_token,
    verify_prospect_email,
    validate_prospect_token,
    get_prospect_performance_data,
)
from ..config import settings


router = APIRouter()


# ============================================================
# Pydantic Models
# ============================================================

class TeaserStatsResponse(BaseModel):
    """Public-facing teaser stats (no sensitive data)."""
    since_inception_pct: float
    inception_date: str
    total_investors: int
    trading_days: int
    as_of_date: str


class InquiryRequest(BaseModel):
    """Prospect inquiry submission from landing page."""
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    message: Optional[str] = Field(None, max_length=1000)


class InquiryResponse(BaseModel):
    """Inquiry submission result."""
    message: str
    success: bool


# ============================================================
# Rate Limiting (simple in-memory per-IP)
# ============================================================

# Track inquiry submissions: {ip: [timestamp, timestamp, ...]}
_inquiry_rate_limit: dict = defaultdict(list)
_RATE_LIMIT_MAX = 5        # Max inquiries per IP
_RATE_LIMIT_WINDOW = 3600  # Per hour (seconds)
_VERIFICATION_TOKEN_HOURS = 24  # Verification link expiry


def _check_rate_limit(ip: str) -> bool:
    """Check if the IP has exceeded the inquiry rate limit.

    Returns True if the request is allowed, False if rate-limited.
    Cleans up expired entries as a side effect.
    """
    now = time.time()
    cutoff = now - _RATE_LIMIT_WINDOW

    # Clean up old entries for this IP
    _inquiry_rate_limit[ip] = [
        ts for ts in _inquiry_rate_limit[ip] if ts > cutoff
    ]

    if len(_inquiry_rate_limit[ip]) >= _RATE_LIMIT_MAX:
        return False

    _inquiry_rate_limit[ip].append(now)
    return True


# ============================================================
# Email Functions (Background Tasks)
# ============================================================

def send_prospect_verification_email(name: str, email: str, token: str):
    """Send email verification link to prospect (runs in background)."""
    try:
        from src.automation.email_service import send_email

        verify_url = f"{settings.PORTAL_BASE_URL}/verify-prospect?token={token}"

        subject = "Tovito Trader - Verify Your Email"
        message = f"""Hello {name},

Thank you for your interest in Tovito Trader.

Please click the link below to verify your email address:

{verify_url}

This link expires in 24 hours.

Once verified, a member of our team will reach out to discuss how our fund can help you achieve your investment goals.

Best regards,
Tovito Trader
"""

        send_email(
            to_email=email,
            subject=subject,
            message=message,
            email_type='ProspectVerification'
        )

    except Exception as e:
        try:
            print(f"[WARN] Failed to send prospect verification email: {e}")
        except UnicodeEncodeError:
            print(f"[WARN] Failed to send prospect verification email: {ascii(str(e))}")


def send_prospect_verified_confirmation(name: str, email: str):
    """Send confirmation to prospect after email verification (runs in background)."""
    try:
        from src.automation.email_service import send_email

        subject = "Tovito Trader - Email Verified"
        message = f"""Hello {name},

Thank you for verifying your email address.

A member of our team will be in touch shortly to discuss how Tovito Trader can help you achieve your investment goals.

In the meantime, if you have any questions, feel free to reply to this email.

Best regards,
Tovito Trader
"""

        send_email(
            to_email=email,
            subject=subject,
            message=message,
            email_type='ProspectConfirmation'
        )

    except Exception as e:
        try:
            print(f"[WARN] Failed to send prospect verified confirmation: {e}")
        except UnicodeEncodeError:
            print(f"[WARN] Failed to send prospect verified confirmation: {ascii(str(e))}")


def send_admin_notification_email(name: str, email: str, phone: Optional[str], message: Optional[str]):
    """Notify admin of new prospect inquiry (runs in background)."""
    try:
        from src.automation.email_service import send_email

        admin_email = settings.ADMIN_EMAIL
        if not admin_email:
            # Fall back to ALERT_EMAIL env var
            admin_email = os.getenv("ALERT_EMAIL", "")
        if not admin_email:
            return

        from datetime import date as date_type
        today = date_type.today().isoformat()

        subject = f"New Prospect Inquiry: {name}"
        body = f"""New prospect inquiry received from the landing page:

Name:    {name}
Email:   {email}
Phone:   {phone or '(not provided)'}
Message: {message or '(none)'}

Date: {today}
Source: Landing Page

To manage this prospect:
  python scripts/prospects/list_prospects.py

---
Tovito Trader - Automated Notification
"""

        send_email(
            to_email=admin_email,
            subject=subject,
            message=body,
            email_type='AdminNotification'
        )

    except Exception as e:
        try:
            print(f"[WARN] Failed to send admin notification email: {e}")
        except UnicodeEncodeError:
            print(f"[WARN] Failed to send admin notification email: {ascii(str(e))}")


# ============================================================
# Endpoints
# ============================================================

@router.get("/teaser-stats", response_model=TeaserStatsResponse)
async def teaser_stats():
    """Get public teaser stats for the landing page.

    Returns aggregate fund metrics only. No dollar amounts,
    no NAV prices, no individual investor data.
    """
    try:
        stats = get_teaser_stats()
        return TeaserStatsResponse(**stats)
    except Exception:
        # Return safe defaults if anything goes wrong
        return TeaserStatsResponse(
            since_inception_pct=0.0,
            inception_date="2026-01-01",
            total_investors=0,
            trading_days=0,
            as_of_date="2026-01-01",
        )


@router.post("/inquiry", response_model=InquiryResponse)
async def submit_inquiry(
    inquiry: InquiryRequest,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Submit a prospect inquiry from the landing page.

    Generates a verification token and sends a verification email.
    Admin notification is deferred until after the prospect verifies
    their email address. Returns the same success message for both
    new and duplicate emails to prevent email enumeration.
    """
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later."
        )

    # Insert prospect
    result = create_prospect(
        name=inquiry.name,
        email=inquiry.email,
        phone=inquiry.phone,
        message=inquiry.message,
        source='landing_page',
    )

    # Generate verification token and send verification email
    # For new prospects: always send verification email
    # For duplicates: resend verification if not yet verified
    should_send_verification = False

    if not result["is_duplicate"]:
        should_send_verification = True
    elif not result.get("email_verified"):
        should_send_verification = True

    if should_send_verification and result["prospect_id"]:
        token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(hours=_VERIFICATION_TOKEN_HOURS)
        store_prospect_verification_token(
            prospect_id=result["prospect_id"],
            token=token,
            expires_at=expires.isoformat(),
        )
        background_tasks.add_task(
            send_prospect_verification_email,
            inquiry.name,
            inquiry.email,
            token,
        )

    # Same response regardless of duplicate status (email enumeration safe)
    return InquiryResponse(
        message="Thank you for your interest! Please check your email to verify your address.",
        success=True,
    )


# ============================================================
# Prospect Email Verification
# ============================================================

class VerifyProspectResponse(BaseModel):
    """Prospect email verification result."""
    verified: bool
    message: str


@router.get("/verify-prospect", response_model=VerifyProspectResponse)
async def verify_prospect(
    token: str,
    background_tasks: BackgroundTasks,
):
    """Verify a prospect's email address using the token from the verification link.

    On successful verification:
    - Marks prospect email_verified=1
    - Sends confirmation email to prospect
    - Sends admin notification email
    """
    if not token or len(token) < 10:
        raise HTTPException(status_code=400, detail="Invalid verification link.")

    result = verify_prospect_email(token)

    if result is None:
        raise HTTPException(
            status_code=400,
            detail="This verification link is invalid or has expired. Please submit a new inquiry."
        )

    # Send post-verification emails in background
    background_tasks.add_task(
        send_prospect_verified_confirmation,
        result["name"],
        result["email"],
    )
    background_tasks.add_task(
        send_admin_notification_email,
        result["name"],
        result["email"],
        result.get("phone"),
        result.get("notes"),
    )

    return VerifyProspectResponse(
        verified=True,
        message="Your email has been verified. A member of our team will be in touch shortly."
    )


# ============================================================
# Prospect Fund Preview (Token-Authenticated)
# ============================================================

class MonthlyReturnItem(BaseModel):
    """Single month return (percentage only)."""
    month: str
    month_label: str
    return_pct: float
    trading_days: int


class PlanAllocationPreview(BaseModel):
    """Plan allocation for prospect view."""
    plan_id: str
    allocation_pct: float
    position_count: int


class BenchmarkComparisonPreview(BaseModel):
    """Fund vs benchmark comparison (percentages only)."""
    ticker: str
    label: str
    fund_return_pct: float
    benchmark_return_pct: float
    outperformance_pct: float


class ProspectPerformanceResponse(BaseModel):
    """Fund performance data for prospect preview.

    Percentage-only — no dollar amounts, no NAV prices.
    """
    valid: bool
    since_inception_pct: float = 0.0
    inception_date: str = ""
    as_of_date: str = ""
    trading_days: int = 0
    investor_count: int = 0
    monthly_returns: List[MonthlyReturnItem] = []
    plan_allocation: List[PlanAllocationPreview] = []
    benchmark_comparison: List[BenchmarkComparisonPreview] = []


@router.get("/prospect-performance", response_model=ProspectPerformanceResponse)
async def prospect_performance(
    token: str,
    days: int = 90,
):
    """
    Get fund performance data for a prospect with a valid access token.

    Returns percentage-only data — NO dollar amounts, NO nav_per_share.
    Token is validated on every request (checks expiry and revocation).
    """
    if not token or len(token) < 10:
        return ProspectPerformanceResponse(valid=False)

    # Validate token
    result = validate_prospect_token(token)
    if not result:
        return ProspectPerformanceResponse(valid=False)

    # Get performance data
    try:
        data = get_prospect_performance_data(days=days)
    except Exception:
        # Return valid=True but empty data if query fails
        return ProspectPerformanceResponse(valid=True)

    monthly_returns = [
        MonthlyReturnItem(**mr)
        for mr in data.get("monthly_returns", [])
    ]

    plan_allocation = [
        PlanAllocationPreview(**pa)
        for pa in data.get("plan_allocation", [])
    ]

    benchmark_comparison = [
        BenchmarkComparisonPreview(**bc)
        for bc in data.get("benchmark_comparison", [])
    ]

    return ProspectPerformanceResponse(
        valid=True,
        since_inception_pct=data.get("since_inception_pct", 0.0),
        inception_date=data.get("inception_date", ""),
        as_of_date=data.get("as_of_date", ""),
        trading_days=data.get("trading_days", 0),
        investor_count=data.get("investor_count", 0),
        monthly_returns=monthly_returns,
        plan_allocation=plan_allocation,
        benchmark_comparison=benchmark_comparison,
    )
