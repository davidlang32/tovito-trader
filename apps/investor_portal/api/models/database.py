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
            "as_of_date": str(nav["date"])
        }
        
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
        
        # Get totals
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN transaction_type = 'Contribution' THEN amount ELSE 0 END) as contributions,
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
# Withdrawals
# ============================================================

def calculate_withdrawal_estimate(investor_id: str, amount: float, tax_rate: float) -> Dict:
    """Calculate estimated tax and proceeds for a withdrawal"""
    position = get_investor_position(investor_id)
    
    if position is None:
        raise ValueError("Position not found")
    
    current_value = position["current_value"]
    net_investment = position["net_investment"]
    
    # Calculate unrealized gain
    unrealized_gain = current_value - net_investment
    
    # Proportion of account being withdrawn
    proportion = amount / current_value if current_value > 0 else 0
    
    # Principal and gain portions
    principal_portion = net_investment * proportion
    gain_portion = unrealized_gain * proportion
    
    # Realized gain (only positive gains are taxed)
    realized_gain = max(0, gain_portion)
    
    # Tax
    tax = realized_gain * tax_rate
    
    # Net proceeds
    net_proceeds = amount - tax
    
    return {
        "proportion": proportion,
        "principal_portion": round(principal_portion, 2),
        "gain_portion": round(gain_portion, 2),
        "realized_gain": round(realized_gain, 2),
        "tax": round(tax, 2),
        "net_proceeds": round(net_proceeds, 2)
    }


def create_withdrawal_request(
    investor_id: str,
    amount: float,
    method: str,
    notes: Optional[str],
    estimated_tax: float,
    estimated_net: float
) -> int:
    """Create a withdrawal request"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO withdrawal_requests (
                investor_id, request_date, requested_amount,
                request_method, notes, status, created_at
            ) VALUES (?, date('now'), ?, ?, ?, 'PENDING', datetime('now'))
        """, (investor_id, amount, method, notes))
        
        conn.commit()
        return cursor.lastrowid
        
    finally:
        conn.close()


def get_pending_withdrawals(investor_id: str) -> List[Dict]:
    """Get pending withdrawal requests for an investor"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, request_date, requested_amount, request_method as method,
                   status, notes
            FROM withdrawal_requests
            WHERE investor_id = ? AND status = 'PENDING'
            ORDER BY request_date DESC
        """, (investor_id,))
        
        results = []
        for row in cursor.fetchall():
            r = dict(row)
            # Calculate estimates
            estimate = calculate_withdrawal_estimate(
                investor_id, r["requested_amount"], settings.TAX_RATE
            )
            r["estimated_tax"] = estimate["tax"]
            r["estimated_net"] = estimate["net_proceeds"]
            results.append(r)
        
        return results
        
    finally:
        conn.close()


def cancel_withdrawal_request(request_id: int, investor_id: str) -> bool:
    """Cancel a withdrawal request (only if PENDING and owned by investor)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE withdrawal_requests
            SET status = 'CANCELLED', updated_at = datetime('now')
            WHERE id = ? AND investor_id = ? AND status = 'PENDING'
        """, (request_id, investor_id))
        
        conn.commit()
        return cursor.rowcount > 0
        
    finally:
        conn.close()
