"""
Admin API Routes
=================

Server-to-server endpoints for production database sync and
prospect access management.

Protected by API key (X-Admin-Key header), not JWT.

Used by the automation laptop to push daily pipeline data
to the Railway production database, and to manage prospect
access tokens for the gated fund preview page.
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..dependencies import verify_admin_key
from ..config import settings
from ..models.database import (
    get_connection,
    upsert_daily_nav,
    upsert_holdings_snapshot,
    upsert_trades,
    upsert_benchmark_prices,
    upsert_reconciliation,
    upsert_plan_performance,
    create_prospect_access_token,
    revoke_prospect_token,
    get_prospect_access_list,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Pydantic Models
# ============================================================

class DailyNavSync(BaseModel):
    """Single daily NAV record to sync."""
    date: str
    nav_per_share: float
    total_portfolio_value: float
    total_shares: float
    daily_change_dollars: float = 0
    daily_change_percent: float = 0


class PositionSync(BaseModel):
    """Single position within a holdings snapshot."""
    symbol: str
    underlying_symbol: Optional[str] = None
    quantity: float
    instrument_type: Optional[str] = None
    average_open_price: Optional[float] = None
    close_price: Optional[float] = None
    market_value: Optional[float] = None
    cost_basis: Optional[float] = None
    unrealized_pl: Optional[float] = None
    option_type: Optional[str] = None
    strike: Optional[float] = None
    expiration_date: Optional[str] = None
    multiplier: Optional[int] = None


class HoldingsSnapshotSync(BaseModel):
    """Holdings snapshot header + positions."""
    date: str
    source: str = "tastytrade"
    snapshot_time: Optional[str] = None
    total_positions: Optional[int] = None
    positions: List[PositionSync] = []


class TradeSync(BaseModel):
    """Single trade record to sync."""
    date: str
    trade_type: str
    symbol: Optional[str] = None
    quantity: Optional[float] = None
    price: Optional[float] = None
    amount: float
    option_type: Optional[str] = None
    strike: Optional[float] = None
    expiration_date: Optional[str] = None
    commission: float = 0
    fees: float = 0
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    source: str = "tastytrade"
    brokerage_transaction_id: Optional[str] = None


class BenchmarkPriceSync(BaseModel):
    """Single benchmark price record to sync."""
    date: str
    ticker: str
    close_price: float


class ReconciliationSync(BaseModel):
    """Single daily reconciliation record to sync."""
    date: str
    tradier_balance: Optional[float] = None
    calculated_portfolio_value: Optional[float] = None
    difference: Optional[float] = None
    total_shares: Optional[float] = None
    nav_per_share: Optional[float] = None
    status: str = "matched"
    notes: Optional[str] = None


class PlanPerformanceSync(BaseModel):
    """Single plan performance record to sync."""
    date: str
    plan_id: str
    market_value: float
    cost_basis: float
    unrealized_pl: float
    allocation_pct: float
    position_count: int


class SyncPayload(BaseModel):
    """Full sync payload from automation laptop.

    All fields are optional — the sync script can push
    a partial payload (e.g., just NAV + benchmarks).
    """
    daily_nav: Optional[DailyNavSync] = None
    holdings_snapshot: Optional[HoldingsSnapshotSync] = None
    trades: List[TradeSync] = Field(default_factory=list)
    benchmark_prices: List[BenchmarkPriceSync] = Field(default_factory=list)
    reconciliation: Optional[ReconciliationSync] = None
    plan_performance: List[PlanPerformanceSync] = Field(default_factory=list)


class SyncResult(BaseModel):
    """Summary of what was synced."""
    success: bool
    nav_synced: bool = False
    holdings_synced: bool = False
    holdings_snapshot_id: Optional[int] = None
    positions_synced: int = 0
    trades_inserted: int = 0
    trades_skipped: int = 0
    benchmarks_inserted: int = 0
    reconciliation_synced: bool = False
    plan_performance_synced: int = 0
    errors: List[str] = Field(default_factory=list)
    synced_at: str = ""


# ============================================================
# Endpoints
# ============================================================

@router.post("/sync", response_model=SyncResult)
async def sync_production_data(
    payload: SyncPayload,
    _admin: bool = Depends(verify_admin_key),
):
    """
    Receive daily pipeline data from the automation laptop
    and upsert into the production database.

    Protected by X-Admin-Key header.
    Idempotent — safe to call multiple times for the same day.
    """
    result = SyncResult(
        success=True,
        synced_at=datetime.utcnow().isoformat(),
    )

    # 1. Daily NAV
    if payload.daily_nav:
        try:
            upsert_daily_nav(payload.daily_nav.model_dump())
            result.nav_synced = True
        except Exception as e:
            error_msg = f"NAV sync failed: {ascii(str(e))}"
            logger.error(error_msg)
            result.errors.append(error_msg)

    # 2. Holdings snapshot + positions
    if payload.holdings_snapshot:
        try:
            header = {
                "date": payload.holdings_snapshot.date,
                "source": payload.holdings_snapshot.source,
                "snapshot_time": payload.holdings_snapshot.snapshot_time,
                "total_positions": payload.holdings_snapshot.total_positions,
            }
            positions = [p.model_dump() for p in payload.holdings_snapshot.positions]
            snapshot_id = upsert_holdings_snapshot(header, positions)
            result.holdings_synced = True
            result.holdings_snapshot_id = snapshot_id
            result.positions_synced = len(positions)
        except Exception as e:
            error_msg = f"Holdings sync failed: {ascii(str(e))}"
            logger.error(error_msg)
            result.errors.append(error_msg)

    # 3. Trades
    if payload.trades:
        try:
            trade_dicts = [t.model_dump() for t in payload.trades]
            trade_result = upsert_trades(trade_dicts)
            result.trades_inserted = trade_result["inserted"]
            result.trades_skipped = trade_result["skipped"]
        except Exception as e:
            error_msg = f"Trades sync failed: {ascii(str(e))}"
            logger.error(error_msg)
            result.errors.append(error_msg)

    # 4. Benchmark prices
    if payload.benchmark_prices:
        try:
            price_dicts = [p.model_dump() for p in payload.benchmark_prices]
            result.benchmarks_inserted = upsert_benchmark_prices(price_dicts)
        except Exception as e:
            error_msg = f"Benchmarks sync failed: {ascii(str(e))}"
            logger.error(error_msg)
            result.errors.append(error_msg)

    # 5. Reconciliation
    if payload.reconciliation:
        try:
            upsert_reconciliation(payload.reconciliation.model_dump())
            result.reconciliation_synced = True
        except Exception as e:
            error_msg = f"Reconciliation sync failed: {ascii(str(e))}"
            logger.error(error_msg)
            result.errors.append(error_msg)

    # 6. Plan daily performance
    if payload.plan_performance:
        try:
            plan_dicts = [p.model_dump() for p in payload.plan_performance]
            result.plan_performance_synced = upsert_plan_performance(plan_dicts)
        except Exception as e:
            error_msg = f"Plan performance sync failed: {ascii(str(e))}"
            logger.error(error_msg)
            result.errors.append(error_msg)

    # Log the sync event
    if result.errors:
        result.success = False

    try:
        _log_sync_event(result)
    except Exception:
        pass  # Don't fail the sync if logging fails

    return result


# ============================================================
# Prospect Access Management
# ============================================================

class GrantAccessResponse(BaseModel):
    """Response after granting prospect access."""
    success: bool
    token: str
    prospect_url: str
    expires_at: str
    prospect_id: int


class ProspectAccessItem(BaseModel):
    """Prospect with access token status."""
    id: int
    name: str
    email: str
    status: Optional[str]
    date_added: Optional[str]
    has_active_token: bool
    token_created: Optional[str]
    expires_at: Optional[str]
    last_accessed_at: Optional[str]
    access_count: Optional[int]


class ProspectListResponse(BaseModel):
    """List of all prospects with access status."""
    prospects: List[ProspectAccessItem]
    total: int


@router.post("/prospect/{prospect_id}/grant-access", response_model=GrantAccessResponse)
async def grant_prospect_access(
    prospect_id: int,
    expiry_days: int = 30,
    _admin: bool = Depends(verify_admin_key),
):
    """
    Generate a unique access token for a prospect.

    Creates a URL-safe token that gives the prospect time-limited
    access to the fund preview page. Revokes any existing tokens.
    """
    # Verify prospect exists
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email FROM prospects WHERE id = ?", (prospect_id,))
        prospect = cursor.fetchone()
    finally:
        conn.close()

    if not prospect:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prospect {prospect_id} not found",
        )

    # Generate token
    token = secrets.token_urlsafe(36)
    expires_at = (datetime.utcnow() + timedelta(days=expiry_days)).isoformat()

    token_id = create_prospect_access_token(
        prospect_id=prospect_id,
        token=token,
        expires_at=expires_at,
    )

    # Build prospect URL
    portal_base = getattr(settings, "PORTAL_BASE_URL", "http://localhost:3000")
    prospect_url = f"{portal_base}/fund-preview?token={token}"

    logger.info(f"Granted access to prospect {prospect_id} (token_id={token_id})")

    return GrantAccessResponse(
        success=True,
        token=token,
        prospect_url=prospect_url,
        expires_at=expires_at,
        prospect_id=prospect_id,
    )


@router.delete("/prospect/{prospect_id}/revoke-access")
async def revoke_prospect_access(
    prospect_id: int,
    _admin: bool = Depends(verify_admin_key),
):
    """Revoke all active access tokens for a prospect."""
    revoked = revoke_prospect_token(prospect_id)

    if not revoked:
        return {"success": True, "message": "No active tokens to revoke"}

    logger.info(f"Revoked access for prospect {prospect_id}")
    return {"success": True, "message": "Access revoked"}


@router.get("/prospects", response_model=ProspectListResponse)
async def list_prospects(
    _admin: bool = Depends(verify_admin_key),
):
    """Get all prospects with their access token status."""
    rows = get_prospect_access_list()

    prospects = []
    for row in rows:
        has_token = row.get("token") is not None and not row.get("is_revoked")
        prospects.append(ProspectAccessItem(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            status=row.get("status"),
            date_added=row.get("date_added"),
            has_active_token=has_token,
            token_created=row.get("token_created"),
            expires_at=row.get("expires_at"),
            last_accessed_at=row.get("last_accessed_at"),
            access_count=row.get("access_count"),
        ))

    return ProspectListResponse(prospects=prospects, total=len(prospects))


# ============================================================
# Internal Helpers
# ============================================================

def _log_sync_event(result: SyncResult) -> None:
    """Log sync event to system_logs table."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        details = (
            f"NAV: {'yes' if result.nav_synced else 'no'}, "
            f"Holdings: {result.positions_synced} positions, "
            f"Trades: {result.trades_inserted} new/{result.trades_skipped} skipped, "
            f"Benchmarks: {result.benchmarks_inserted}, "
            f"Reconciliation: {'yes' if result.reconciliation_synced else 'no'}, "
            f"Plan Performance: {result.plan_performance_synced}"
        )
        if result.errors:
            details += f" | Errors: {'; '.join(result.errors)}"

        cursor.execute("""
            INSERT INTO system_logs (timestamp, log_type, category, message, details)
            VALUES (datetime('now'), ?, 'SYNC', ?, ?)
        """, (
            "SUCCESS" if result.success else "ERROR",
            "Production sync completed" if result.success else "Production sync had errors",
            details,
        ))
        conn.commit()
    finally:
        conn.close()
