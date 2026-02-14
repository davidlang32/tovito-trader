"""
Reconciliation Validator

Comprehensive validation tool to ensure all numbers add up correctly.
Run this anytime to verify data integrity.

Usage:
    python scripts/validate_reconciliation.py
    python scripts/validate_reconciliation.py --date 2026-01-23
    python scripts/validate_reconciliation.py --verbose
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import requests
import os
from pathlib import Path
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

# Configuration
TRADIER_API_KEY = os.getenv('TRADIER_API_KEY')
TRADIER_ACCOUNT_ID = os.getenv('TRADIER_ACCOUNT_ID')
TRADIER_BASE_URL = os.getenv('TRADIER_BASE_URL', 'https://api.tradier.com')


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def fetch_tradier_balance():
    """Fetch current Tradier balance"""
    
    if not TRADIER_API_KEY or not TRADIER_ACCOUNT_ID:
        return None
    
    url = f"{TRADIER_BASE_URL}/v1/accounts/{TRADIER_ACCOUNT_ID}/balances"
    
    headers = {
        'Authorization': f'Bearer {TRADIER_API_KEY}',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if 'balances' in data:
            return float(data['balances'].get('total_equity', 0))
    except:
        pass
    
    return None


def check_investor_shares(conn, verbose=False):
    """Verify investor shares sum to total shares"""
    cursor = conn.cursor()
    
    # Get sum of investor shares
    cursor.execute("""
        SELECT SUM(current_shares) FROM investors WHERE status = 'Active'
    """)
    investor_total = cursor.fetchone()[0] or 0.0
    
    # Get total shares from latest NAV
    cursor.execute("""
        SELECT total_shares, date FROM daily_nav
        ORDER BY date DESC LIMIT 1
    """)
    
    nav_data = cursor.fetchone()
    if not nav_data:
        return {'status': 'error', 'message': 'No NAV data found'}
    
    nav_total, nav_date = nav_data
    
    difference = investor_total - nav_total
    
    if verbose:
        print(f"   Investor shares: {investor_total:,.4f}")
        print(f"   NAV total shares: {nav_total:,.4f}")
        print(f"   Difference: {difference:+,.4f}")
    
    if abs(difference) < 0.0001:
        return {'status': 'pass', 'difference': difference}
    else:
        return {'status': 'fail', 'difference': difference, 'investor_total': investor_total, 'nav_total': nav_total}


def check_portfolio_value(conn, tradier_balance, verbose=False):
    """Verify portfolio value matches NAV calculation"""
    cursor = conn.cursor()
    
    # Get latest NAV
    cursor.execute("""
        SELECT nav_per_share, total_shares, total_portfolio_value, date
        FROM daily_nav
        ORDER BY date DESC LIMIT 1
    """)
    
    nav_data = cursor.fetchone()
    if not nav_data:
        return {'status': 'error', 'message': 'No NAV data found'}
    
    nav, shares, portfolio_value, nav_date = nav_data
    
    # Calculate what portfolio should be
    calculated = nav * shares
    
    # Check against recorded value
    db_difference = portfolio_value - calculated
    
    if verbose:
        print(f"   Recorded portfolio: ${portfolio_value:,.2f}")
        print(f"   Calculated (NAV × Shares): ${calculated:,.2f}")
        print(f"   Database difference: ${db_difference:+,.2f}")
    
    result = {
        'portfolio_value': portfolio_value,
        'calculated_value': calculated,
        'db_difference': db_difference
    }
    
    # If Tradier balance available, check against it
    if tradier_balance:
        tradier_difference = tradier_balance - portfolio_value
        
        if verbose:
            print(f"   Tradier balance: ${tradier_balance:,.2f}")
            print(f"   Tradier difference: ${tradier_difference:+,.2f}")
        
        result['tradier_balance'] = tradier_balance
        result['tradier_difference'] = tradier_difference
        
        if abs(tradier_difference) < 0.01:
            result['status'] = 'pass'
        elif abs(tradier_difference) < 1.00:
            result['status'] = 'minor_diff'
        else:
            result['status'] = 'fail'
    else:
        if abs(db_difference) < 0.01:
            result['status'] = 'pass'
        else:
            result['status'] = 'fail'
    
    return result


def check_individual_positions(conn, verbose=False):
    """Verify each investor's position calculates correctly"""
    cursor = conn.cursor()
    
    # Get latest NAV
    cursor.execute("""
        SELECT nav_per_share FROM daily_nav
        ORDER BY date DESC LIMIT 1
    """)
    
    nav_data = cursor.fetchone()
    if not nav_data:
        return {'status': 'error', 'message': 'No NAV data found'}
    
    nav = nav_data[0]
    
    # Get all active investors
    cursor.execute("""
        SELECT investor_id, name, current_shares, net_investment
        FROM investors
        WHERE status = 'Active'
        ORDER BY investor_id
    """)
    
    investors = cursor.fetchall()
    
    total_value = 0
    issues = []
    
    for inv_id, name, shares, net_inv in investors:
        calculated_value = shares * nav
        total_value += calculated_value
        
        unrealized_gain = calculated_value - net_inv
        
        if verbose:
            print(f"   {name} ({inv_id}):")
            print(f"     Shares: {shares:,.4f}")
            print(f"     Value: ${calculated_value:,.2f}")
            print(f"     Investment: ${net_inv:,.2f}")
            print(f"     Gain: ${unrealized_gain:+,.2f}")
    
    return {
        'status': 'pass',
        'total_value': total_value,
        'investor_count': len(investors)
    }


def check_pending_contributions(conn, verbose=False):
    """Check for pending contributions"""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COUNT(*), SUM(amount)
        FROM pending_contributions
        WHERE status = 'pending'
    """)
    
    count, total = cursor.fetchone()
    total = total or 0
    
    if verbose and count > 0:
        print(f"   Pending contributions: {count}")
        print(f"   Total amount: ${total:,.2f}")
    
    return {
        'status': 'warning' if count > 0 else 'pass',
        'count': count,
        'total': total
    }


def check_transaction_sync(conn, verbose=False):
    """Check when transactions were last synced"""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT sync_date, last_sync_time, status
        FROM transaction_sync_status
        ORDER BY sync_date DESC LIMIT 1
    """)
    
    sync = cursor.fetchone()
    
    if not sync:
        return {'status': 'warning', 'message': 'No transaction sync records'}
    
    sync_date, sync_time, status = sync
    
    if verbose:
        print(f"   Last sync: {sync_date} at {sync_time}")
        print(f"   Status: {status}")
    
    # Check if sync is recent
    if sync_date == str(date.today() - timedelta(days=1)):
        return {'status': 'pass', 'last_sync': sync_date}
    else:
        return {'status': 'warning', 'last_sync': sync_date, 'message': 'Sync may be outdated'}


def main():
    import argparse
    from datetime import timedelta
    
    parser = argparse.ArgumentParser(description='Validate data reconciliation')
    parser.add_argument('--date', help='Specific date (YYYY-MM-DD)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("RECONCILIATION VALIDATOR")
    print("=" * 70)
    print()
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return
    
    # Fetch Tradier balance if available
    print("📡 Fetching Tradier balance...")
    tradier_balance = fetch_tradier_balance()
    if tradier_balance:
        print(f"   Tradier balance: ${tradier_balance:,.2f}")
    else:
        print(f"     Could not fetch Tradier balance (will use database only)")
    print()
    
    try:
        conn = sqlite3.connect(db_path)
        
        all_passed = True
        
        # Check 1: Investor shares sum
        print("1️⃣  INVESTOR SHARES VALIDATION")
        print("-" * 70)
        result = check_investor_shares(conn, args.verbose)
        
        if result['status'] == 'pass':
            print("   PASS - Investor shares match NAV total")
        elif result['status'] == 'fail':
            print(f"   FAIL - Mismatch: {result['difference']:+,.4f} shares")
            print(f"      Investor total: {result['investor_total']:,.4f}")
            print(f"      NAV total: {result['nav_total']:,.4f}")
            all_passed = False
        else:
            print(f"     ERROR - {result.get('message')}")
            all_passed = False
        
        print()
        
        # Check 2: Portfolio value
        print("2️⃣  PORTFOLIO VALUE VALIDATION")
        print("-" * 70)
        result = check_portfolio_value(conn, tradier_balance, args.verbose)
        
        if result['status'] == 'pass':
            print("   PASS - Portfolio value matches")
        elif result['status'] == 'minor_diff':
            print(f"     MINOR DIFFERENCE - ${result.get('tradier_difference', 0):+,.2f}")
        elif result['status'] == 'fail':
            print(f"   FAIL - Mismatch detected")
            if 'tradier_difference' in result:
                print(f"      Tradier difference: ${result['tradier_difference']:+,.2f}")
            all_passed = False
        
        print()
        
        # Check 3: Individual positions
        print("3️⃣  INDIVIDUAL POSITION VALIDATION")
        print("-" * 70)
        result = check_individual_positions(conn, args.verbose)
        
        if result['status'] == 'pass':
            print(f"   PASS - All {result['investor_count']} investor positions calculated correctly")
            print(f"      Total value: ${result['total_value']:,.2f}")
        
        print()
        
        # Check 4: Pending contributions
        print("4️⃣  PENDING CONTRIBUTIONS CHECK")
        print("-" * 70)
        result = check_pending_contributions(conn, args.verbose)
        
        if result['status'] == 'pass':
            print("   No pending contributions")
        else:
            print(f"     {result['count']} pending contribution(s) - ${result['total']:,.2f}")
            print(f"      Run: python scripts/assign_pending_contribution.py")
        
        print()
        
        # Check 5: Transaction sync status
        print("5️⃣  TRANSACTION SYNC STATUS")
        print("-" * 70)
        result = check_transaction_sync(conn, args.verbose)
        
        if result['status'] == 'pass':
            print(f"   Transactions synced: {result['last_sync']}")
        else:
            print(f"     {result.get('message', 'Unknown status')}")
        
        print()
        
        # Final summary
        print("=" * 70)
        if all_passed:
            print(" ALL VALIDATION CHECKS PASSED!")
        else:
            print(" SOME VALIDATION CHECKS FAILED")
            print("   Review issues above and investigate")
        print("=" * 70)
        print()
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"\n Database error: {e}")
    except Exception as e:
        print(f"\n Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
