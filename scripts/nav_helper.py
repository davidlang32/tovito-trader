"""
NAV Helper Module - Single Source of Truth

All scripts should import and use these functions to get NAV.
NAV is ALWAYS read from the daily_nav table, never calculated in scripts.

Usage:
    from nav_helper import get_current_nav, get_nav_for_date
    
    nav, date = get_current_nav(cursor)
    nav = get_nav_for_date(cursor, '2026-01-25')
"""

from datetime import datetime
from typing import Tuple, Optional


def get_current_nav(cursor) -> Tuple[float, str]:
    """
    Get current NAV from daily_nav table (single source of truth).
    
    Returns:
        Tuple of (nav_per_share, date)
    
    Raises:
        ValueError: If no NAV data found
    """
    cursor.execute("""
        SELECT nav_per_share, date
        FROM daily_nav
        ORDER BY date DESC
        LIMIT 1
    """)
    
    result = cursor.fetchone()
    if not result:
        raise ValueError("No NAV data found in daily_nav table")
    
    nav_per_share, date = result
    return nav_per_share, date


def get_nav_for_date(cursor, date: str) -> Optional[float]:
    """
    Get NAV for a specific date from daily_nav table.
    
    Args:
        date: Date string in format 'YYYY-MM-DD'
    
    Returns:
        NAV per share for that date, or None if not found
    """
    cursor.execute("""
        SELECT nav_per_share
        FROM daily_nav
        WHERE date = ?
    """, (date,))
    
    result = cursor.fetchone()
    return result[0] if result else None


def get_nav_history(cursor, start_date: Optional[str] = None, 
                    end_date: Optional[str] = None) -> list:
    """
    Get NAV history from daily_nav table.
    
    Args:
        start_date: Optional start date (inclusive)
        end_date: Optional end date (inclusive)
    
    Returns:
        List of tuples: (date, nav_per_share, total_portfolio_value, total_shares)
    """
    query = "SELECT date, nav_per_share, total_portfolio_value, total_shares FROM daily_nav"
    params = []
    
    conditions = []
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY date"
    
    cursor.execute(query, params)
    return cursor.fetchall()


def validate_nav_consistency(cursor, date: str = None) -> Tuple[bool, str]:
    """
    Validate that NAV calculation is consistent for a given date.
    
    Args:
        date: Date to check (defaults to latest)
    
    Returns:
        Tuple of (is_valid, message)
    """
    if date is None:
        # Get latest date
        cursor.execute("SELECT date FROM daily_nav ORDER BY date DESC LIMIT 1")
        result = cursor.fetchone()
        if not result:
            return False, "No NAV data found"
        date = result[0]
    
    cursor.execute("""
        SELECT nav_per_share, total_portfolio_value, total_shares
        FROM daily_nav
        WHERE date = ?
    """, (date,))
    
    result = cursor.fetchone()
    if not result:
        return False, f"No NAV data for date {date}"
    
    stored_nav, portfolio, shares = result
    
    if shares == 0:
        return False, "Total shares is zero"
    
    calculated_nav = portfolio / shares
    difference = abs(stored_nav - calculated_nav)
    
    if difference < 0.0001:  # Allow for floating point precision
        return True, f"NAV is consistent: ${stored_nav:.4f}"
    else:
        return False, f"NAV mismatch: Stored ${stored_nav:.4f}, Calculated ${calculated_nav:.4f}, Diff ${difference:.4f}"


def get_nav_change(cursor, start_date: str, end_date: str) -> Tuple[float, float, float]:
    """
    Calculate NAV change between two dates.
    
    Returns:
        Tuple of (start_nav, end_nav, percent_change)
    """
    start_nav = get_nav_for_date(cursor, start_date)
    end_nav = get_nav_for_date(cursor, end_date)
    
    if start_nav is None or end_nav is None:
        raise ValueError("NAV data not found for one or both dates")
    
    change = end_nav - start_nav
    percent_change = (change / start_nav * 100) if start_nav != 0 else 0
    
    return start_nav, end_nav, percent_change


# CRITICAL: Scripts should NEVER calculate NAV directly.
# Always use get_current_nav() or get_nav_for_date() instead.

__all__ = [
    'get_current_nav',
    'get_nav_for_date',
    'get_nav_history',
    'validate_nav_consistency',
    'get_nav_change'
]
