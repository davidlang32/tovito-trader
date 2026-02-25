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
import sys
import time
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

def send_prospect_confirmation_email(name: str, email: str):
    """Send confirmation email to prospect (runs in background)."""
    try:
        from src.automation.email_service import send_email

        subject = "Tovito Trader - We Received Your Inquiry"
        message = f"""Hello {name},

Thank you for your interest in Tovito Trader.

We have received your inquiry and a member of our team will be in touch shortly to discuss how our fund can help you achieve your investment goals.

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
            print(f"[WARN] Failed to send prospect confirmation email: {e}")
        except UnicodeEncodeError:
            print(f"[WARN] Failed to send prospect confirmation email: {ascii(str(e))}")


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

    Returns the same success message for both new and duplicate
    emails to prevent email enumeration.
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

    # Send emails in background (only for new prospects, not duplicates)
    if not result["is_duplicate"]:
        background_tasks.add_task(
            send_prospect_confirmation_email,
            inquiry.name,
            inquiry.email,
        )
        background_tasks.add_task(
            send_admin_notification_email,
            inquiry.name,
            inquiry.email,
            inquiry.phone,
            inquiry.message,
        )

    # Same response regardless of duplicate status (email enumeration safe)
    return InquiryResponse(
        message="Thank you for your interest! A member of our team will be in touch shortly.",
        success=True,
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
