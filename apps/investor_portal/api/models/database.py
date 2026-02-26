"""
Database Access Module
=======================

All database queries for the Fund API.
Uses the main tovito.db database.

SECURITY: All functions that access investor-specific data
require investor_id as a parameter to prevent data leakage.
"""

import sqlite3
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from pathlib import Path
import hashlib

from ..config import get_database_path, settings


def get_connection():
    """Get database connection"""
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# Authentication
# ============================================================

def verify_investor_credentials(email: str, password: str) -> Optional[Dict]:
    """
    Verify investor login credentials.
    
    NOTE: In production, passwords should be hashed with bcrypt.
    For now, we'll use a simple hash or store in a separate auth table.
    
    For initial implementation, we'll verify email exists and
    use a temporary password system.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get investor by email
        cursor.execute("""
            SELECT investor_id, name, email, status
            FROM investors
            WHERE email = ? AND status = 'Active'
        """, (email,))
        
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        # TODO: In production, verify password hash
        # For now, we'll accept any password for active investors
        # This is a placeholder - implement proper auth before deployment!
        
        # TEMPORARY: Check if password matches investor_id (for testing)
        # In production, use bcrypt hashed passwords stored in a separate table
        expected_password = row["investor_id"]  # Temporary!
        
        if password != expected_password:
            return None
        
        return dict(row)
        
    finally:
        conn.close()


def get_investor_by_id(investor_id: str) -> Optional[Dict]:
    """Get investor by ID"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT investor_id, name, email, phone, join_date, status,
                   current_shares, net_investment, initial_capital
            FROM investors
            WHERE investor_id = ?
        """, (investor_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
        
    finally:
        conn.close()


# ============================================================
# Investor Position
# ============================================================

def get_investor_position(investor_id: str) -> Optional[Dict]:
    """Get current position for an investor"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get investor data
        cursor.execute("""
            SELECT investor_id, name, current_shares, net_investment, initial_capital
            FROM investors
            WHERE investor_id = ? AND status = 'Active'
        """, (investor_id,))
        
        investor = cursor.fetchone()
        if investor is None:
            return None
        
        # Get current NAV
        cursor.execute("""
            SELECT date, nav_per_share, total_shares
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        nav = cursor.fetchone()
        
        if nav is None:
            return None
        
        # Calculate values
        current_shares = investor["current_shares"] or 0
        nav_per_share = nav["nav_per_share"]
        current_value = current_shares * nav_per_share
        net_investment = investor["net_investment"] or 0

        total_return_dollars = current_value - net_investment
        total_return_percent = (total_return_dollars / net_investment * 100) if net_investment > 0 else 0

        total_shares = nav["total_shares"] or 1
        portfolio_percentage = (current_shares / total_shares * 100) if total_shares > 0 else 0

        # Average cost per share
        avg_cost_per_share = round(net_investment / current_shares, 4) if current_shares > 0 else 0.0

        # Tax and eligible withdrawal calculations
        unrealized_gain = max(0, current_value - net_investment)
        estimated_tax_liability = round(unrealized_gain * settings.TAX_RATE, 2)
        eligible_withdrawal = round(current_value - estimated_tax_liability, 2)

        return {
            "investor_id": investor["investor_id"],
            "name": investor["name"],
            "current_shares": round(current_shares, 4),
            "current_nav": round(nav_per_share, 4),
            "current_value": round(current_value, 2),
            "net_investment": round(net_investment, 2),
            "initial_capital": round(investor["initial_capital"] or 0, 2),
            "total_return_dollars": round(total_return_dollars, 2),
            "total_return_percent": round(total_return_percent, 2),
            "portfolio_percentage": round(portfolio_percentage, 2),
            "avg_cost_per_share": avg_cost_per_share,
            "unrealized_gain": round(unrealized_gain, 2),
            "estimated_tax_liability": estimated_tax_liability,
            "eligible_withdrawal": eligible_withdrawal,
            "as_of_date": str(nav["date"])
        }
        
    finally:
        conn.close()


# ============================================================
# Value History (for portfolio value chart)
# ============================================================

def _interpolate_trading_day_gaps(points: List[Dict]) -> List[Dict]:
    """Fill gaps in value history by interpolating missing trading days.

    When the daily_nav table has gaps (e.g., pipeline didn't run for
    several days), the chart shows a misleading straight line. This
    function detects gaps > 1 trading day and inserts linearly
    interpolated points for each missing weekday (Mon-Fri).

    Interpolated points have daily_change_pct=None and are marked with
    is_interpolated=True so the frontend can distinguish them.

    US market holidays are not excluded — a few extra interpolated
    points on holidays are visually harmless.
    """
    if len(points) < 2:
        return points

    filled = [points[0]]

    for i in range(1, len(points)):
        prev = points[i - 1]
        curr = points[i]

        prev_date = datetime.strptime(prev["date"], "%Y-%m-%d")
        curr_date = datetime.strptime(curr["date"], "%Y-%m-%d")
        gap_days = (curr_date - prev_date).days

        # Only interpolate if gap is more than 3 calendar days
        # (normal weekend = 2 days Sat-Sun, so gap of 3 = Fri->Mon is normal)
        if gap_days > 3:
            # Count weekdays in the gap (excluding endpoints)
            weekdays_in_gap = []
            d = prev_date + timedelta(days=1)
            while d < curr_date:
                if d.weekday() < 5:  # Mon-Fri
                    weekdays_in_gap.append(d)
                d += timedelta(days=1)

            if weekdays_in_gap:
                # Linear interpolation of portfolio value and nav_per_share
                total_steps = len(weekdays_in_gap) + 1
                val_start = prev["portfolio_value"]
                val_end = curr["portfolio_value"]
                nav_start = prev["nav_per_share"]
                nav_end = curr["nav_per_share"]

                for step_idx, wd in enumerate(weekdays_in_gap, start=1):
                    fraction = step_idx / total_steps
                    interp_val = round(
                        val_start + (val_end - val_start) * fraction, 2
                    )
                    interp_nav = round(
                        nav_start + (nav_end - nav_start) * fraction, 4
                    )
                    filled.append({
                        "date": wd.strftime("%Y-%m-%d"),
                        "portfolio_value": interp_val,
                        "shares": prev["shares"],
                        "nav_per_share": interp_nav,
                        "daily_change_pct": None,
                        "transaction_type": None,
                        "transaction_amount": None,
                    })

        filled.append(curr)

    return filled


def get_investor_value_history(investor_id: str, days: int = 90) -> List[Dict]:
    """Compute investor's portfolio value for each day in the given range.

    For each day of NAV data, reconstruct the investor's share count
    (running total from transactions) and multiply by that day's NAV.

    Gaps of more than 3 calendar days in the daily_nav table are filled
    with linearly interpolated weekday points so the chart renders
    smoothly instead of showing a misleading straight line.

    Returns list of dicts with: date, portfolio_value, shares,
    nav_per_share, daily_change_pct, transaction_type, transaction_amount.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get all transactions for this investor (oldest first), excluding deleted
        cursor.execute("""
            SELECT date, transaction_type, shares_transacted, amount
            FROM transactions
            WHERE investor_id = ?
              AND (is_deleted IS NULL OR is_deleted = 0)
            ORDER BY date ASC, transaction_id ASC
        """, (investor_id,))
        txns = cursor.fetchall()

        if not txns:
            return []

        # Build a date -> cumulative shares map
        # Also track transactions by date for markers
        cumulative_shares = 0.0
        shares_by_date = {}  # date -> cumulative shares after all txns that day
        txn_by_date = {}     # date -> (type, amount) for the last txn that day

        for t in txns:
            cumulative_shares += t["shares_transacted"]
            shares_by_date[t["date"]] = cumulative_shares
            txn_by_date[t["date"]] = (t["transaction_type"], t["amount"])

        # Get NAV history for the requested range
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT date, nav_per_share, daily_change_percent
            FROM daily_nav
            WHERE date >= ?
            ORDER BY date ASC
        """, (cutoff,))
        nav_rows = cursor.fetchall()

        if not nav_rows:
            return []

        # Walk through NAV dates, carrying forward the latest known share count
        result = []
        current_shares = 0.0

        # Find the share count just before our window starts
        # (investor may have had shares before the cutoff)
        first_nav_date = nav_rows[0]["date"]
        for t_date, s in sorted(shares_by_date.items()):
            if t_date < first_nav_date:
                current_shares = s
            else:
                break

        for nav_row in nav_rows:
            d = nav_row["date"]

            # Update shares if there was a transaction on this date
            if d in shares_by_date:
                current_shares = shares_by_date[d]

            if current_shares <= 0:
                continue

            portfolio_value = round(current_shares * nav_row["nav_per_share"], 2)

            point = {
                "date": d,
                "portfolio_value": portfolio_value,
                "shares": round(current_shares, 4),
                "nav_per_share": round(nav_row["nav_per_share"], 4),
                "daily_change_pct": round(nav_row["daily_change_percent"], 2) if nav_row["daily_change_percent"] is not None else None,
                "transaction_type": None,
                "transaction_amount": None,
            }

            # Add transaction marker if applicable
            if d in txn_by_date:
                t_type, t_amount = txn_by_date[d]
                point["transaction_type"] = t_type
                point["transaction_amount"] = round(abs(t_amount), 2)

            result.append(point)

        # Fill gaps in the data with interpolated trading day points
        result = _interpolate_trading_day_gaps(result)

        return result

    finally:
        conn.close()


# ============================================================
# Transactions
# ============================================================

def get_investor_transactions(
    investor_id: str,
    limit: int = 50,
    offset: int = 0,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    transaction_type: Optional[str] = None
) -> Dict:
    """Get transaction history for an investor"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Build query
        query = """
            SELECT date, transaction_type, amount, shares_transacted, share_price, notes
            FROM transactions
            WHERE investor_id = ? AND (is_deleted IS NULL OR is_deleted = 0)
        """
        params = [investor_id]
        
        if start_date:
            query += " AND date >= ?"
            params.append(str(start_date))
        
        if end_date:
            query += " AND date <= ?"
            params.append(str(end_date))
        
        if transaction_type:
            query += " AND transaction_type = ?"
            params.append(transaction_type)
        
        query += " ORDER BY date DESC, transaction_id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        transactions = [dict(row) for row in cursor.fetchall()]
        
        # Get totals (include 'Initial' deposits in contributions total)
        cursor.execute("""
            SELECT
                SUM(CASE WHEN transaction_type IN ('Contribution', 'Initial') THEN amount ELSE 0 END) as contributions,
                SUM(CASE WHEN transaction_type = 'Withdrawal' THEN ABS(amount) ELSE 0 END) as withdrawals
            FROM transactions
            WHERE investor_id = ? AND (is_deleted IS NULL OR is_deleted = 0)
        """, (investor_id,))
        
        totals = cursor.fetchone()
        
        return {
            "transactions": transactions,
            "total_contributions": totals["contributions"] or 0,
            "total_withdrawals": totals["withdrawals"] or 0,
            "net_investment": (totals["contributions"] or 0) - (totals["withdrawals"] or 0)
        }
        
    finally:
        conn.close()


# ============================================================
# Statements
# ============================================================

def get_available_statements(investor_id: str) -> List[Dict]:
    """Get list of available monthly statements for an investor"""
    # Look for PDF files in reports directory
    reports_dir = Path(__file__).parent.parent.parent.parent.parent / "reports"
    
    if not reports_dir.exists():
        return []
    
    statements = []
    for pdf_file in reports_dir.glob(f"{investor_id}_*_Statement.pdf"):
        # Parse filename: {investor_id}_{year}_{month}_Statement.pdf
        parts = pdf_file.stem.split("_")
        if len(parts) >= 4:
            year = parts[1]
            month = parts[2]
            period = f"{year}-{month}"
            
            statements.append({
                "period": period,
                "filename": pdf_file.name,
                "generated_date": datetime.fromtimestamp(pdf_file.stat().st_mtime).isoformat()
            })
    
    # Sort by period descending
    statements.sort(key=lambda x: x["period"], reverse=True)
    return statements


# ============================================================
# NAV
# ============================================================

def get_current_nav() -> Dict:
    """Get current NAV"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT date, nav_per_share, total_portfolio_value, total_shares,
                   daily_change_dollars, daily_change_percent
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        return dict(row) if row else {}
        
    finally:
        conn.close()


def get_nav_history(
    days: int = 30,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List[Dict]:
    """Get NAV history"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if start_date and end_date:
            cursor.execute("""
                SELECT date, nav_per_share, daily_change_percent
                FROM daily_nav
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC
            """, (str(start_date), str(end_date)))
        else:
            cursor.execute("""
                SELECT date, nav_per_share, daily_change_percent
                FROM daily_nav
                ORDER BY date DESC
                LIMIT ?
            """, (days,))
        
        return [dict(row) for row in cursor.fetchall()]
        
    finally:
        conn.close()


def get_fund_performance() -> Dict:
    """Calculate fund performance metrics"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get current NAV
        cursor.execute("""
            SELECT date, nav_per_share, total_portfolio_value, total_shares,
                   daily_change_percent
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        current = cursor.fetchone()
        
        # Get inception NAV (January 1, 2026)
        cursor.execute("""
            SELECT date, nav_per_share
            FROM daily_nav
            WHERE date = '2026-01-01'
        """)
        inception = cursor.fetchone()
        
        # Get week start NAV
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        cursor.execute("""
            SELECT nav_per_share
            FROM daily_nav
            WHERE date <= ?
            ORDER BY date DESC
            LIMIT 1
        """, (str(week_start),))
        week_start_nav = cursor.fetchone()
        
        # Get month start NAV
        month_start = today.replace(day=1)
        cursor.execute("""
            SELECT nav_per_share
            FROM daily_nav
            WHERE date <= ?
            ORDER BY date DESC
            LIMIT 1
        """, (str(month_start),))
        month_start_nav = cursor.fetchone()
        
        # Get year start NAV
        year_start = today.replace(month=1, day=1)
        cursor.execute("""
            SELECT nav_per_share
            FROM daily_nav
            WHERE date <= ?
            ORDER BY date DESC
            LIMIT 1
        """, (str(year_start),))
        year_start_nav = cursor.fetchone()
        
        # Get investor count
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM investors
            WHERE status = 'Active'
        """)
        investor_count = cursor.fetchone()["count"]
        
        # Calculate returns
        current_nav = current["nav_per_share"] if current else 1.0
        inception_nav = inception["nav_per_share"] if inception else 1.0
        
        def calc_return(start_nav, end_nav):
            if start_nav and start_nav > 0:
                return ((end_nav / start_nav) - 1) * 100
            return 0
        
        return {
            "current_nav": current_nav,
            "current_date": str(current["date"]) if current else str(today),
            "daily_return": current["daily_change_percent"] if current else 0,
            "wtd_return": calc_return(week_start_nav["nav_per_share"] if week_start_nav else None, current_nav),
            "mtd_return": calc_return(month_start_nav["nav_per_share"] if month_start_nav else None, current_nav),
            "ytd_return": calc_return(year_start_nav["nav_per_share"] if year_start_nav else None, current_nav),
            "since_inception": calc_return(inception_nav, current_nav),
            "inception_date": str(inception["date"]) if inception else "2026-01-01",
            "inception_nav": inception_nav,
            "total_portfolio_value": current["total_portfolio_value"] if current else 0,
            "total_investors": investor_count
        }
        
    finally:
        conn.close()


# ============================================================
# Benchmark Data
# ============================================================

def get_cached_benchmark_data(days: int = 90) -> Dict[str, List[Dict]]:
    """Get cached benchmark prices for chart generation."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        tickers = ['SPY', 'QQQ', 'BTC-USD']
        result = {}

        for ticker in tickers:
            cursor.execute("""
                SELECT date, close_price
                FROM benchmark_prices
                WHERE ticker = ? AND date >= ?
                ORDER BY date ASC
            """, (ticker, cutoff))
            result[ticker] = [dict(row) for row in cursor.fetchall()]

        return result

    except Exception:
        # Table may not exist yet
        return {}

    finally:
        conn.close()


# ============================================================
# Fund Flow Requests (unified contribution/withdrawal lifecycle)
# ============================================================

def create_fund_flow_request(
    investor_id: str,
    flow_type: str,
    amount: float,
    method: str = 'portal',
    notes: Optional[str] = None,
) -> int:
    """
    Create a new fund flow request (contribution or withdrawal).

    Args:
        investor_id: Investor who owns the request
        flow_type: 'contribution' or 'withdrawal'
        amount: Requested amount (must be positive)
        method: How the request was submitted ('portal', 'email', etc.)
        notes: Optional notes

    Returns:
        request_id of the newly created request
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO fund_flow_requests (
                investor_id, flow_type, requested_amount, request_date,
                request_method, status, notes, created_at, updated_at
            ) VALUES (?, ?, ?, date('now'), ?, 'pending', ?, datetime('now'), datetime('now'))
        """, (investor_id, flow_type, amount, method, notes))

        conn.commit()
        return cursor.lastrowid

    finally:
        conn.close()


def get_fund_flow_requests(
    investor_id: str,
    status: Optional[str] = None,
    flow_type: Optional[str] = None,
    limit: int = 50,
) -> List[Dict]:
    """
    Get fund flow requests for an investor.

    Args:
        investor_id: Filter by investor
        status: Optional status filter ('pending', 'approved', etc.)
        flow_type: Optional type filter ('contribution' or 'withdrawal')
        limit: Max results to return

    Returns:
        List of fund flow request dicts
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        query = """
            SELECT request_id, investor_id, flow_type, requested_amount,
                   request_date, request_method, status,
                   approved_date, rejection_reason,
                   matched_trade_id, matched_date,
                   processed_date, actual_amount, shares_transacted,
                   nav_per_share, transaction_id,
                   realized_gain, tax_withheld, net_proceeds,
                   notes, created_at, updated_at
            FROM fund_flow_requests
            WHERE investor_id = ?
        """
        params: list = [investor_id]

        if status:
            query += " AND status = ?"
            params.append(status)

        if flow_type:
            query += " AND flow_type = ?"
            params.append(flow_type)

        query += " ORDER BY request_date DESC, request_id DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    finally:
        conn.close()


def cancel_fund_flow_request(request_id: int, investor_id: str) -> bool:
    """
    Cancel a fund flow request. Only pending/approved requests
    owned by the investor can be cancelled.

    Returns:
        True if a row was updated
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE fund_flow_requests
            SET status = 'cancelled', updated_at = datetime('now')
            WHERE request_id = ? AND investor_id = ?
            AND status IN ('pending', 'approved')
        """, (request_id, investor_id))

        conn.commit()
        return cursor.rowcount > 0

    finally:
        conn.close()


def get_fund_flow_estimate(investor_id: str, flow_type: str, amount: float) -> Dict:
    """
    Calculate estimate for a fund flow request.

    For contributions: shows estimated shares to be purchased.
    For withdrawals: shows estimated tax and net proceeds.

    Returns:
        Dict with estimate fields
    """
    position = get_investor_position(investor_id)

    if position is None:
        raise ValueError("Position not found")

    current_nav = position["current_nav"]
    current_value = position["current_value"]
    net_investment = position["net_investment"]

    if flow_type == 'contribution':
        estimated_shares = round(amount / current_nav, 4) if current_nav > 0 else 0
        return {
            "flow_type": "contribution",
            "amount": round(amount, 2),
            "current_nav": current_nav,
            "estimated_shares": estimated_shares,
            "new_total_shares": round(position["current_shares"] + estimated_shares, 4),
        }
    else:
        # Withdrawal estimate — no tax withheld at withdrawal (settled quarterly)
        proportion = amount / current_value if current_value > 0 else 0
        unrealized_gain = max(0, current_value - net_investment)
        realized_gain = round(unrealized_gain * proportion, 2)
        estimated_shares = round(amount / current_nav, 4) if current_nav > 0 else 0

        # Eligible withdrawal = max amount after accounting for total tax liability
        total_tax_liability = round(unrealized_gain * settings.TAX_RATE, 2)
        eligible_withdrawal = round(current_value - total_tax_liability, 2)

        return {
            "flow_type": "withdrawal",
            "amount": round(amount, 2),
            "current_nav": current_nav,
            "proportion": round(proportion * 100, 2),
            "estimated_shares": estimated_shares,
            "realized_gain": realized_gain,
            "estimated_tax": 0.0,
            "net_proceeds": round(amount, 2),
            "remaining_shares": round(position["current_shares"] - estimated_shares, 4),
            "eligible_withdrawal": eligible_withdrawal,
            "note": "Tax settled quarterly — full withdrawal amount disbursed.",
        }


# ============================================================
# Public / Teaser Stats (no authentication required)
# ============================================================

def get_teaser_stats() -> Dict:
    """Get public-facing teaser stats for the landing page.

    Returns only non-sensitive aggregate data:
    - since_inception_pct: Fund return since inception
    - inception_date: When the fund started
    - total_investors: Number of active investors
    - trading_days: Number of NAV entries
    - as_of_date: Date of the latest NAV

    Does NOT expose portfolio value, NAV per share, or any
    dollar amounts. This function defines the public data boundary.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get inception and latest NAV for return calculation
        cursor.execute("""
            SELECT date, nav_per_share
            FROM daily_nav
            ORDER BY date ASC
            LIMIT 1
        """)
        inception = cursor.fetchone()

        cursor.execute("""
            SELECT date, nav_per_share
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        latest = cursor.fetchone()

        # Trading days count
        cursor.execute("SELECT COUNT(*) as cnt FROM daily_nav")
        trading_days = cursor.fetchone()["cnt"]

        # Active investor count
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM investors WHERE status = 'Active'
        """)
        total_investors = cursor.fetchone()["cnt"]

        # Calculate since-inception return
        if inception and latest and inception["nav_per_share"] > 0:
            since_inception_pct = round(
                ((latest["nav_per_share"] / inception["nav_per_share"]) - 1) * 100,
                2
            )
        else:
            since_inception_pct = 0.0

        return {
            "since_inception_pct": since_inception_pct,
            "inception_date": str(inception["date"]) if inception else "2026-01-01",
            "total_investors": total_investors,
            "trading_days": trading_days,
            "as_of_date": str(latest["date"]) if latest else str(date.today()),
        }

    finally:
        conn.close()


# ============================================================
# Prospect Management (landing page inquiries)
# ============================================================

def create_prospect(
    name: str,
    email: str,
    phone: Optional[str] = None,
    message: Optional[str] = None,
    source: str = 'landing_page',
) -> Dict:
    """Insert a prospect into the prospects table.

    Handles duplicate emails gracefully (UNIQUE constraint on email).

    Args:
        name: Prospect's full name
        email: Prospect's email address
        phone: Optional phone number
        message: Optional message / investment goals
        source: How the prospect was acquired (default: 'landing_page')

    Returns:
        Dict with keys: success, prospect_id, is_duplicate, message
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO prospects (name, email, phone, date_added, status, source, notes,
                                   created_at, updated_at)
            VALUES (?, ?, ?, date('now'), 'Active', ?, ?, datetime('now'), datetime('now'))
        """, (name, email, phone, source, message))

        conn.commit()
        return {
            "success": True,
            "prospect_id": cursor.lastrowid,
            "is_duplicate": False,
            "message": "Inquiry received successfully.",
        }

    except sqlite3.IntegrityError:
        # Duplicate email — look up existing prospect for verification status
        cursor.execute("""
            SELECT id, email_verified FROM prospects WHERE email = ?
        """, (email,))
        existing = cursor.fetchone()
        return {
            "success": True,
            "prospect_id": existing["id"] if existing else None,
            "is_duplicate": True,
            "email_verified": existing["email_verified"] if existing else 0,
            "message": "Inquiry received successfully.",
        }

    finally:
        conn.close()


# ============================================================
# Prospect Email Verification
# ============================================================

def store_prospect_verification_token(
    prospect_id: int, token: str, expires_at: str
) -> bool:
    """Store a verification token for a prospect.

    Args:
        prospect_id: ID of the prospect
        token: URL-safe verification token
        expires_at: ISO timestamp when the token expires

    Returns:
        True if stored successfully
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE prospects
            SET verification_token = ?,
                verification_token_expires = ?,
                updated_at = datetime('now')
            WHERE id = ?
        """, (token, expires_at, prospect_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def verify_prospect_email(token: str) -> Optional[Dict]:
    """Verify a prospect's email using their verification token.

    Validates the token, checks expiration, marks email_verified=1,
    and clears the token. Returns prospect info if valid.

    Args:
        token: The verification token from the URL

    Returns:
        Dict with prospect info (id, name, email, phone, notes) if valid.
        None if token is invalid, expired, or already used.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, email, phone, notes,
                   verification_token_expires, email_verified
            FROM prospects
            WHERE verification_token = ?
        """, (token,))

        row = cursor.fetchone()
        if not row:
            return None

        prospect_id = row["id"]
        name = row["name"]
        email = row["email"]
        phone = row["phone"]
        notes = row["notes"]
        expires_str = row["verification_token_expires"]
        already_verified = row["email_verified"]

        # Already verified — idempotent success
        if already_verified:
            return {
                "id": prospect_id, "name": name, "email": email,
                "phone": phone, "notes": notes,
            }

        # Check expiration
        if expires_str:
            expires = datetime.fromisoformat(expires_str)
            if datetime.utcnow() > expires:
                return None

        # Mark verified and clear token
        cursor.execute("""
            UPDATE prospects
            SET email_verified = 1,
                verification_token = NULL,
                verification_token_expires = NULL,
                updated_at = datetime('now')
            WHERE id = ?
        """, (prospect_id,))
        conn.commit()

        return {
            "id": prospect_id, "name": name, "email": email,
            "phone": phone, "notes": notes,
        }
    finally:
        conn.close()


# ============================================================
# Admin Sync (Production Database Updates)
# ============================================================

def upsert_daily_nav(row: Dict) -> bool:
    """Insert or replace a daily NAV record. Used by production sync.

    Args:
        row: Dict with keys: date, nav_per_share, total_portfolio_value,
             total_shares, daily_change_dollars, daily_change_percent
    Returns:
        True if successful
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO daily_nav (
                date, nav_per_share, total_portfolio_value, total_shares,
                daily_change_dollars, daily_change_percent, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(date) DO UPDATE SET
                nav_per_share = excluded.nav_per_share,
                total_portfolio_value = excluded.total_portfolio_value,
                total_shares = excluded.total_shares,
                daily_change_dollars = excluded.daily_change_dollars,
                daily_change_percent = excluded.daily_change_percent
        """, (
            row["date"], row["nav_per_share"], row["total_portfolio_value"],
            row["total_shares"], row.get("daily_change_dollars", 0),
            row.get("daily_change_percent", 0),
        ))
        conn.commit()
        return True
    finally:
        conn.close()


def upsert_holdings_snapshot(header: Dict, positions: List[Dict]) -> int:
    """Insert or replace a holdings snapshot with positions. Used by production sync.

    Args:
        header: Dict with keys: date, source, snapshot_time, total_positions
        positions: List of dicts with position data (symbol, quantity, etc.)
    Returns:
        snapshot_id of the upserted snapshot
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Upsert snapshot header
        cursor.execute("""
            INSERT INTO holdings_snapshots (date, source, snapshot_time, total_positions)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date, source) DO UPDATE SET
                snapshot_time = excluded.snapshot_time,
                total_positions = excluded.total_positions
        """, (
            header["date"], header["source"],
            header.get("snapshot_time", datetime.now().isoformat()),
            header.get("total_positions", len(positions)),
        ))

        # Get the snapshot_id (whether inserted or updated)
        cursor.execute("""
            SELECT snapshot_id FROM holdings_snapshots
            WHERE date = ? AND source = ?
        """, (header["date"], header["source"]))
        snapshot_id = cursor.fetchone()["snapshot_id"]

        # Delete existing positions for this snapshot and re-insert
        cursor.execute(
            "DELETE FROM position_snapshots WHERE snapshot_id = ?",
            (snapshot_id,)
        )

        for pos in positions:
            cursor.execute("""
                INSERT INTO position_snapshots (
                    snapshot_id, symbol, underlying_symbol, quantity,
                    instrument_type, average_open_price, close_price,
                    market_value, cost_basis, unrealized_pl,
                    option_type, strike, expiration_date, multiplier
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot_id, pos["symbol"], pos.get("underlying_symbol"),
                pos["quantity"], pos.get("instrument_type"),
                pos.get("average_open_price"), pos.get("close_price"),
                pos.get("market_value"), pos.get("cost_basis"),
                pos.get("unrealized_pl"), pos.get("option_type"),
                pos.get("strike"), pos.get("expiration_date"),
                pos.get("multiplier"),
            ))

        conn.commit()
        return snapshot_id
    finally:
        conn.close()


def upsert_trades(trades: List[Dict]) -> Dict:
    """Insert trades, skipping duplicates by source + brokerage_transaction_id.

    Args:
        trades: List of trade dicts from ETL
    Returns:
        Dict with inserted and skipped counts
    """
    conn = get_connection()
    inserted = 0
    skipped = 0
    try:
        cursor = conn.cursor()
        for trade in trades:
            # Check for existing trade by source + brokerage_transaction_id
            brokerage_txn_id = trade.get("brokerage_transaction_id")
            source = trade.get("source", "tastytrade")
            if brokerage_txn_id:
                cursor.execute("""
                    SELECT trade_id FROM trades
                    WHERE source = ? AND brokerage_transaction_id = ?
                    AND is_deleted = 0
                """, (source, brokerage_txn_id))
                if cursor.fetchone():
                    skipped += 1
                    continue

            cursor.execute("""
                INSERT INTO trades (
                    date, trade_type, symbol, quantity, price, amount,
                    option_type, strike, expiration_date,
                    commission, fees, category, subcategory,
                    description, notes, source, brokerage_transaction_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          datetime('now'), datetime('now'))
            """, (
                trade["date"], trade["trade_type"], trade.get("symbol"),
                trade.get("quantity"), trade.get("price"), trade["amount"],
                trade.get("option_type"), trade.get("strike"),
                trade.get("expiration_date"),
                trade.get("commission", 0), trade.get("fees", 0),
                trade.get("category"), trade.get("subcategory"),
                trade.get("description"), trade.get("notes"),
                source, brokerage_txn_id,
            ))
            inserted += 1

        conn.commit()
        return {"inserted": inserted, "skipped": skipped}
    finally:
        conn.close()


def upsert_benchmark_prices(prices: List[Dict]) -> int:
    """Insert benchmark prices, ignoring duplicates. Used by production sync.

    Args:
        prices: List of dicts with keys: date, ticker, close_price
    Returns:
        Number of rows inserted
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        inserted = 0
        for price in prices:
            cursor.execute("""
                INSERT OR IGNORE INTO benchmark_prices (date, ticker, close_price)
                VALUES (?, ?, ?)
            """, (price["date"], price["ticker"], price["close_price"]))
            inserted += cursor.rowcount
        conn.commit()
        return inserted
    finally:
        conn.close()


def upsert_reconciliation(row: Dict) -> bool:
    """Insert or replace a daily reconciliation record. Used by production sync.

    Args:
        row: Dict with keys: date, tradier_balance, calculated_portfolio_value,
             difference, total_shares, nav_per_share, status, notes
    Returns:
        True if successful
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO daily_reconciliation (
                date, tradier_balance, calculated_portfolio_value,
                difference, total_shares, nav_per_share, status, notes,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            row["date"], row.get("tradier_balance"),
            row.get("calculated_portfolio_value"), row.get("difference"),
            row.get("total_shares"), row.get("nav_per_share"),
            row.get("status", "matched"), row.get("notes"),
        ))
        conn.commit()
        return True
    finally:
        conn.close()


def upsert_plan_performance(rows: List[Dict]) -> int:
    """Insert or replace plan daily performance records. Used by production sync.

    Args:
        rows: List of dicts with keys: date, plan_id, market_value,
              cost_basis, unrealized_pl, allocation_pct, position_count
    Returns:
        Number of rows written
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        count = 0
        for row in rows:
            cursor.execute("""
                INSERT OR REPLACE INTO plan_daily_performance
                    (date, plan_id, market_value, cost_basis, unrealized_pl,
                     allocation_pct, position_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                row["date"], row["plan_id"],
                row.get("market_value", 0),
                row.get("cost_basis", 0),
                row.get("unrealized_pl", 0),
                row.get("allocation_pct", 0),
                row.get("position_count", 0),
            ))
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()


# ============================================================
# Prospect Access Token Functions
# ============================================================

def create_prospect_access_token(prospect_id: int, token: str,
                                  expires_at: str, created_by: str = "admin") -> int:
    """Create a new prospect access token. Revokes any existing active tokens first.

    Args:
        prospect_id: ID of the prospect in the prospects table
        token: URL-safe unique token string
        expires_at: ISO format datetime when the token expires
        created_by: Who created the token (default: 'admin')
    Returns:
        token_id of the created token
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Revoke any existing active tokens for this prospect
        cursor.execute("""
            UPDATE prospect_access_tokens
            SET is_revoked = 1
            WHERE prospect_id = ? AND is_revoked = 0
        """, (prospect_id,))

        # Insert new token
        cursor.execute("""
            INSERT INTO prospect_access_tokens
                (prospect_id, token, expires_at, created_by)
            VALUES (?, ?, ?, ?)
        """, (prospect_id, token, expires_at, created_by))

        token_id = cursor.lastrowid
        conn.commit()
        return token_id
    finally:
        conn.close()


def validate_prospect_token(token: str) -> Optional[Dict]:
    """Validate a prospect access token and update access tracking.

    Args:
        token: The token string from the URL
    Returns:
        Dict with prospect_id, prospect_name, prospect_email if valid.
        None if token is invalid, expired, or revoked.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Look up the token with prospect info
        cursor.execute("""
            SELECT t.token_id, t.prospect_id, t.expires_at, t.is_revoked,
                   p.name as prospect_name, p.email as prospect_email
            FROM prospect_access_tokens t
            JOIN prospects p ON p.id = t.prospect_id
            WHERE t.token = ?
        """, (token,))
        row = cursor.fetchone()

        if not row:
            return None

        # Check if revoked
        if row["is_revoked"]:
            return None

        # Check if expired
        from datetime import datetime
        try:
            expires = datetime.fromisoformat(row["expires_at"])
            if datetime.utcnow() > expires:
                return None
        except (ValueError, TypeError):
            return None

        # Update access tracking
        cursor.execute("""
            UPDATE prospect_access_tokens
            SET last_accessed_at = datetime('now'),
                access_count = access_count + 1
            WHERE token_id = ?
        """, (row["token_id"],))
        conn.commit()

        return {
            "prospect_id": row["prospect_id"],
            "prospect_name": row["prospect_name"],
            "prospect_email": row["prospect_email"],
        }
    finally:
        conn.close()


def revoke_prospect_token(prospect_id: int) -> bool:
    """Revoke all active tokens for a prospect.

    Args:
        prospect_id: ID of the prospect
    Returns:
        True if any tokens were revoked
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE prospect_access_tokens
            SET is_revoked = 1
            WHERE prospect_id = ? AND is_revoked = 0
        """, (prospect_id,))
        revoked = cursor.rowcount > 0
        conn.commit()
        return revoked
    finally:
        conn.close()


def get_prospect_access_list() -> List[Dict]:
    """Get all prospects with their access token status.

    Returns:
        List of dicts with prospect info and token status.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.name, p.email, p.status, p.date_added,
                   t.token, t.created_at as token_created,
                   t.expires_at, t.last_accessed_at,
                   t.access_count, t.is_revoked
            FROM prospects p
            LEFT JOIN prospect_access_tokens t ON t.prospect_id = p.id
                AND t.is_revoked = 0
            ORDER BY p.date_added DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_prospect_performance_data(days: int = 90) -> Dict:
    """Get fund performance data formatted for prospect view.

    Returns percentage-only data — NO dollar amounts, NO nav_per_share.

    Args:
        days: Number of days of data to return
    Returns:
        Dict with since_inception_pct, monthly_returns, plan_allocation,
        benchmark_comparison data.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Since-inception return
        cursor.execute("""
            SELECT nav_per_share FROM daily_nav
            ORDER BY date ASC LIMIT 1
        """)
        inception_row = cursor.fetchone()

        cursor.execute("""
            SELECT nav_per_share, date FROM daily_nav
            ORDER BY date DESC LIMIT 1
        """)
        latest_row = cursor.fetchone()

        since_inception_pct = 0.0
        inception_date = "2026-01-01"
        as_of_date = "2026-01-01"
        trading_days = 0

        if inception_row and latest_row:
            inception_nav = inception_row["nav_per_share"]
            latest_nav = latest_row["nav_per_share"]
            as_of_date = str(latest_row["date"])
            if inception_nav and inception_nav > 0:
                since_inception_pct = round(
                    ((latest_nav / inception_nav) - 1) * 100, 2
                )

        cursor.execute("SELECT MIN(date) as d FROM daily_nav")
        inception_row2 = cursor.fetchone()
        if inception_row2 and inception_row2["d"]:
            inception_date = str(inception_row2["d"])

        cursor.execute("SELECT COUNT(*) as cnt FROM daily_nav")
        td_row = cursor.fetchone()
        if td_row:
            trading_days = td_row["cnt"]

        # Monthly returns (percentage only)
        try:
            cursor.execute("""
                SELECT month, start_nav, end_nav, trading_days
                FROM v_monthly_performance
                ORDER BY month ASC
            """)
            monthly_rows = cursor.fetchall()
        except Exception:
            monthly_rows = []

        monthly_returns = []
        for mr in monthly_rows:
            start_nav = mr["start_nav"]
            end_nav = mr["end_nav"]
            ret_pct = 0.0
            if start_nav and start_nav > 0:
                ret_pct = round(((end_nav / start_nav) - 1) * 100, 2)

            # Format month label
            try:
                from datetime import datetime as dt
                month_dt = dt.strptime(mr["month"] + "-01", "%Y-%m-%d")
                month_label = month_dt.strftime("%b %Y")
            except (ValueError, TypeError):
                month_label = mr["month"]

            monthly_returns.append({
                "month": mr["month"],
                "month_label": month_label,
                "return_pct": ret_pct,
                "trading_days": mr["trading_days"] or 0,
            })

        # Plan allocation (latest)
        plan_allocation = []
        try:
            cursor.execute("""
                SELECT plan_id, allocation_pct, position_count
                FROM plan_daily_performance
                WHERE date = (SELECT MAX(date) FROM plan_daily_performance)
                ORDER BY allocation_pct DESC
            """)
            plan_rows = cursor.fetchall()
            for pr in plan_rows:
                plan_allocation.append({
                    "plan_id": pr["plan_id"],
                    "allocation_pct": round(pr["allocation_pct"], 1),
                    "position_count": pr["position_count"],
                })
        except Exception:
            pass

        # Benchmark comparison (fund vs SPY/QQQ)
        from datetime import date, timedelta
        cutoff = str(date.today() - timedelta(days=days))

        benchmark_comparison = []
        # Fund return for the period
        cursor.execute("""
            SELECT nav_per_share FROM daily_nav
            WHERE date >= ? ORDER BY date ASC LIMIT 1
        """, (cutoff,))
        fund_start = cursor.fetchone()
        cursor.execute("""
            SELECT nav_per_share FROM daily_nav
            ORDER BY date DESC LIMIT 1
        """)
        fund_end = cursor.fetchone()

        fund_return = 0.0
        if fund_start and fund_end and fund_start["nav_per_share"] > 0:
            fund_return = round(
                ((fund_end["nav_per_share"] / fund_start["nav_per_share"]) - 1) * 100, 2
            )

        for ticker, label in [("SPY", "S&P 500"), ("QQQ", "Nasdaq 100")]:
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

            b_return = 0.0
            if b_start and b_end and b_start["close_price"] > 0:
                b_return = round(
                    ((b_end["close_price"] / b_start["close_price"]) - 1) * 100, 2
                )

            benchmark_comparison.append({
                "ticker": ticker,
                "label": label,
                "fund_return_pct": fund_return,
                "benchmark_return_pct": b_return,
                "outperformance_pct": round(fund_return - b_return, 2),
            })

        # Investor count
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM investors WHERE status = 'Active'
        """)
        inv_row = cursor.fetchone()
        investor_count = inv_row["cnt"] if inv_row else 0

        return {
            "since_inception_pct": since_inception_pct,
            "inception_date": inception_date,
            "as_of_date": as_of_date,
            "trading_days": trading_days,
            "investor_count": investor_count,
            "monthly_returns": monthly_returns,
            "plan_allocation": plan_allocation,
            "benchmark_comparison": benchmark_comparison,
        }
    finally:
        conn.close()
