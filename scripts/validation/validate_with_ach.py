#!/usr/bin/env python3
"""
Validate with ACH Reconciliation
================================

Validates investor data AND reconciles ACH deposits with investor contributions.

Usage:
    python scripts/05_validation/validate_with_ach.py
    python scripts/validate_with_ach.py
    python validate_with_ach.py --db path/to/tovito.db
"""

import sqlite3
import argparse
from datetime import datetime
from pathlib import Path


def find_database():
    """Find the database file - checks multiple common locations"""
    # Get the script's directory and work upward
    script_dir = Path(__file__).parent.resolve()
    
    # Possible locations relative to script
    possible_paths = [
        script_dir / "data" / "tovito.db",           # scripts/data/tovito.db
        script_dir.parent / "data" / "tovito.db",    # scripts/../data/tovito.db (project root)
        script_dir.parent.parent / "data" / "tovito.db",  # scripts/05_validation/../../data/tovito.db
        Path("data/tovito.db"),                       # Current working directory
        Path("C:/tovito-trader/data/tovito.db"),     # Absolute path
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None


def validate_basic_accounting(cursor):
    """Basic investor accounting checks"""
    print("\n" + "="*60)
    print("BASIC ACCOUNTING CHECKS")
    print("="*60)
    
    all_passed = True
    
    # Check 1: Share totals match
    print("\n✓ Check 1: Share totals match")
    cursor.execute("""
        SELECT COALESCE(SUM(current_shares), 0) FROM investors WHERE status = 'Active'
    """)
    investor_shares = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT total_shares FROM daily_nav ORDER BY date DESC LIMIT 1
    """)
    row = cursor.fetchone()
    nav_shares = row[0] if row else 0
    
    if abs(investor_shares - nav_shares) < 0.01:
        print(f"  ✅ Investors: {investor_shares:,.4f} | Daily NAV: {nav_shares:,.4f}")
    else:
        print(f"  ❌ MISMATCH! Investors: {investor_shares:,.4f} | Daily NAV: {nav_shares:,.4f}")
        all_passed = False
    
    # Check 2: Percentages = 100%
    print("\n✓ Check 2: Portfolio percentages = 100%")
    cursor.execute("""
        SELECT SUM(current_shares) FROM investors WHERE status = 'Active' AND current_shares > 0
    """)
    total = cursor.fetchone()[0] or 0
    
    cursor.execute("""
        SELECT investor_id, name, current_shares FROM investors 
        WHERE status = 'Active' AND current_shares > 0
    """)
    
    pct_sum = 0
    for inv_id, name, shares in cursor.fetchall():
        pct = (shares / total * 100) if total > 0 else 0
        pct_sum += pct
    
    if abs(pct_sum - 100.0) < 0.01:
        print(f"  ✅ Total: {pct_sum:.2f}%")
    else:
        print(f"  ❌ MISMATCH! Total: {pct_sum:.2f}% (should be 100%)")
        all_passed = False
    
    # Check 3: NAV calculation
    print("\n✓ Check 3: NAV calculation correct")
    cursor.execute("""
        SELECT total_portfolio_value, total_shares, nav_per_share
        FROM daily_nav ORDER BY date DESC LIMIT 1
    """)
    row = cursor.fetchone()
    if row:
        value, shares, nav = row
        calculated_nav = value / shares if shares > 0 else 0
        if abs(calculated_nav - nav) < 0.0001:
            print(f"  ✅ NAV: ${nav:.4f} (${value:,.2f} / {shares:,.4f})")
        else:
            print(f"  ❌ MISMATCH! Stored: ${nav:.4f} | Calculated: ${calculated_nav:.4f}")
            all_passed = False
    
    # Check 4: Transaction totals
    print("\n✓ Check 4: Transaction totals match net investments")
    cursor.execute("""
        SELECT i.investor_id, i.name, i.net_investment,
               COALESCE(SUM(t.amount), 0) as txn_total
        FROM investors i
        LEFT JOIN transactions t ON i.investor_id = t.investor_id
        WHERE i.status = 'Active'
        GROUP BY i.investor_id
    """)
    
    for inv_id, name, net, txn_total in cursor.fetchall():
        if abs(net - txn_total) < 0.01:
            print(f"  ✅ {name[:20]:<20} Net: ${net:>10,.2f} | Txns: ${txn_total:>10,.2f}")
        else:
            if txn_total == 0 and net == 0:
                print(f"  ✅ {name[:20]:<20} Net: ${net:>10,.2f} | Txns: ${txn_total:>10,.2f} (no activity)")
            else:
                print(f"  ❌ {name[:20]:<20} Net: ${net:>10,.2f} | Txns: ${txn_total:>10,.2f} MISMATCH!")
                all_passed = False
    
    return all_passed


def validate_ach_reconciliation(cursor):
    """Validate ACH deposits match investor contributions"""
    print("\n" + "="*60)
    print("ACH RECONCILIATION CHECK")
    print("="*60)
    
    # Check if trades table exists
    cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='table' AND name='trades'
    """)
    if not cursor.fetchone():
        print("\n  ⚠️ No 'trades' table found - skipping ACH reconciliation")
        print("     Run: python scripts/import_tradier_history.py --import")
        return True  # Not a failure, just not available
    
    # Get ACH deposits by date
    cursor.execute("""
        SELECT date, SUM(amount) as ach_total
        FROM trades
        WHERE LOWER(trade_type) = 'ach' AND amount > 0
        GROUP BY date
        ORDER BY date
    """)
    ach_by_date = {row[0]: row[1] for row in cursor.fetchall()}
    
    if not ach_by_date:
        print("\n  ⚠️ No ACH deposits found in trades table")
        return True
    
    # Get investor contributions by date (Initial + Contribution, positive amounts)
    cursor.execute("""
        SELECT date, SUM(amount) as inv_total, COUNT(*) as inv_count
        FROM transactions
        WHERE transaction_type IN ('Initial', 'Contribution') AND amount > 0
        GROUP BY date
        ORDER BY date
    """)
    inv_by_date = {row[0]: {'total': row[1], 'count': row[2]} for row in cursor.fetchall()}
    
    # Compare
    all_dates = sorted(set(list(ach_by_date.keys()) + list(inv_by_date.keys())))
    
    print(f"\n  Found {len(ach_by_date)} ACH deposit date(s)")
    print(f"  Found {len(inv_by_date)} investor contribution date(s)")
    
    print("\n  " + "-"*70)
    print(f"  {'Date':<12} {'ACH (Tradier)':<18} {'Investor Txns':<18} {'Status':<20}")
    print("  " + "-"*70)
    
    all_passed = True
    total_ach = 0
    total_inv = 0
    
    for date in all_dates:
        ach = ach_by_date.get(date, 0)
        inv_data = inv_by_date.get(date, {'total': 0, 'count': 0})
        inv = inv_data['total']
        inv_count = inv_data['count']
        
        total_ach += ach
        total_inv += inv
        
        diff = abs(ach - inv)
        
        if diff < 0.01:
            if inv_count > 1 and ach > 0:
                status = f"✅ Match ({inv_count} investors, 1 ACH)"
            else:
                status = "✅ Match"
        elif ach > 0 and inv == 0:
            status = "❌ ACH not attributed!"
            all_passed = False
        elif inv > 0 and ach == 0:
            status = "⚠️ No ACH record"
        else:
            status = f"❌ Diff: ${diff:,.2f}"
            all_passed = False
        
        ach_str = f"${ach:,.2f}" if ach > 0 else "-"
        inv_str = f"${inv:,.2f}" if inv > 0 else "-"
        
        print(f"  {date:<12} {ach_str:<18} {inv_str:<18} {status}")
    
    print("  " + "-"*70)
    print(f"  {'TOTAL':<12} ${total_ach:<17,.2f} ${total_inv:<17,.2f}")
    
    if abs(total_ach - total_inv) < 0.01:
        print(f"\n  ✅ ACH and Investor totals match!")
    else:
        print(f"\n  ❌ TOTALS DON'T MATCH!")
        print(f"     ACH Total: ${total_ach:,.2f}")
        print(f"     Investor Total: ${total_inv:,.2f}")
        print(f"     Difference: ${abs(total_ach - total_inv):,.2f}")
        all_passed = False
    
    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Validate investor data with ACH reconciliation")
    parser.add_argument('--db', help='Path to database file')
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("TOVITO TRADER - DATA VALIDATION")
    print("="*60)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Find database
    if args.db:
        db_path = Path(args.db)
    else:
        db_path = find_database()
    
    if not db_path or not db_path.exists():
        print(f"\n❌ Database not found!")
        print(f"   Searched locations:")
        print(f"   - data/tovito.db (from current directory)")
        print(f"   - C:/tovito-trader/data/tovito.db")
        print(f"\n   Use --db flag to specify path:")
        print(f"   python validate_with_ach.py --db C:\\tovito-trader\\data\\tovito.db")
        return 1
    
    print(f"  Database: {db_path}")
    
    # Connect
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Run validations
        basic_passed = validate_basic_accounting(cursor)
        ach_passed = validate_ach_reconciliation(cursor)
        
        # Summary
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)
        
        if basic_passed and ach_passed:
            print("\n  ✅ ALL CHECKS PASSED!")
            return 0
        else:
            print("\n  ❌ SOME CHECKS FAILED!")
            if not basic_passed:
                print("     - Basic accounting issues detected")
            if not ach_passed:
                print("     - ACH reconciliation issues detected")
            return 1
    
    finally:
        conn.close()


if __name__ == "__main__":
    exit(main())
