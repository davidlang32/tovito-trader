"""
Enhanced Validation - Comprehensive System Check

Validates:
- Share totals match
- Percentages = 100%
- NAV calculations correct
- January 1 NAV = $1.00
- Portfolio values consistent
- No data corruption

Usage:
    python scripts/validate_comprehensive.py
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def validate_comprehensive():
    """Comprehensive validation with NAV checks"""
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 80)
        print("COMPREHENSIVE VALIDATION")
        print("=" * 80)
        print()
        
        all_checks_passed = True
        
        # CHECK 1: Share Totals Match
        print("CHECK 1: Share Totals Match")
        print("-" * 40)
        
        cursor.execute("""
            SELECT SUM(current_shares)
            FROM investors
            WHERE status = 'Active'
        """)
        investor_shares = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            SELECT total_shares
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        nav_result = cursor.fetchone()
        nav_shares = nav_result[0] if nav_result else 0
        
        print(f"  Investor shares: {investor_shares:,.4f}")
        print(f"  Daily NAV shares: {nav_shares:,.4f}")
        print(f"  Difference: {abs(investor_shares - nav_shares):.4f}")
        
        if abs(investor_shares - nav_shares) < 0.01:
            print("  ✅ PASS - Shares match")
        else:
            print("  ❌ FAIL - Share mismatch!")
            all_checks_passed = False
        print()
        
        # CHECK 2: Percentages = 100%
        print("CHECK 2: Percentages = 100%")
        print("-" * 40)
        
        cursor.execute("""
            SELECT nav_per_share
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        current_nav = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT investor_id, name, current_shares
            FROM investors
            WHERE status = 'Active'
        """)
        investors = cursor.fetchall()
        
        total_value = 0
        for inv_id, name, shares in investors:
            value = shares * current_nav
            total_value += value
        
        percentages = []
        for inv_id, name, shares in investors:
            value = shares * current_nav
            pct = (value / total_value * 100) if total_value > 0 else 0
            percentages.append(pct)
            print(f"  {name}: {pct:.2f}%")
        
        total_pct = sum(percentages)
        print(f"  Total: {total_pct:.2f}%")
        
        if abs(total_pct - 100.0) < 0.01:
            print("  ✅ PASS - Percentages = 100%")
        else:
            print("  ❌ FAIL - Percentages don't equal 100%!")
            all_checks_passed = False
        print()
        
        # CHECK 3: NAV Calculation Correct
        print("CHECK 3: NAV Calculation Correct")
        print("-" * 40)
        
        cursor.execute("""
            SELECT date, nav_per_share, total_portfolio_value, total_shares
            FROM daily_nav
            ORDER BY date DESC
            LIMIT 1
        """)
        latest = cursor.fetchone()
        
        if latest:
            date, nav, portfolio, shares = latest
            calculated_nav = portfolio / shares if shares > 0 else 0
            
            print(f"  Date: {date}")
            print(f"  Stored NAV: ${nav:.4f}")
            print(f"  Portfolio: ${portfolio:,.2f}")
            print(f"  Shares: {shares:,.4f}")
            print(f"  Calculated NAV: ${calculated_nav:.4f}")
            print(f"  Difference: ${abs(nav - calculated_nav):.4f}")
            
            if abs(nav - calculated_nav) < 0.0001:
                print("  ✅ PASS - NAV calculation correct")
            else:
                print("  ❌ FAIL - NAV calculation mismatch!")
                all_checks_passed = False
        else:
            print("  ⚠️  No NAV data found")
            all_checks_passed = False
        print()
        
        # CHECK 4: January 1 NAV = $1.00
        print("CHECK 4: January 1, 2026 NAV = $1.00")
        print("-" * 40)
        
        cursor.execute("""
            SELECT nav_per_share, total_portfolio_value, total_shares
            FROM daily_nav
            WHERE date = '2026-01-01'
        """)
        jan1 = cursor.fetchone()
        
        if jan1:
            nav, portfolio, shares = jan1
            print(f"  NAV: ${nav:.4f}")
            print(f"  Portfolio: ${portfolio:,.2f}")
            print(f"  Shares: {shares:,.4f}")
            
            if abs(nav - 1.0) < 0.0001:
                print("  ✅ PASS - January 1 NAV = $1.00")
            else:
                print(f"  ❌ FAIL - January 1 NAV should be $1.00, is ${nav:.4f}")
                print(f"     This suggests initial data issues!")
                all_checks_passed = False
        else:
            print("  ⚠️  No January 1, 2026 data found")
        print()
        
        # CHECK 5: Day 1 Investments Match Day 1 Portfolio
        print("CHECK 5: Day 1 Investments Match Day 1 Portfolio")
        print("-" * 40)
        
        # Get initial capital from investors who joined on Day 1
        cursor.execute("""
            SELECT SUM(initial_capital)
            FROM investors
            WHERE join_date = '2026-01-01' AND status = 'Active'
        """)
        day1_investment = cursor.fetchone()[0] or 0
        
        if jan1:
            nav, portfolio, shares = jan1
            print(f"  Day 1 initial capital: ${day1_investment:,.2f}")
            print(f"  Day 1 portfolio value: ${portfolio:,.2f}")
            print(f"  Difference: ${abs(day1_investment - portfolio):,.2f}")
            
            if abs(day1_investment - portfolio) < 1.0:
                print("  ✅ PASS - Day 1 totals match")
            else:
                print("  ❌ FAIL - Day 1 totals don't match!")
                print(f"     Difference: ${day1_investment - portfolio:,.2f}")
                all_checks_passed = False
        print()
        
        # CHECK 6: All NAV Calculations Valid
        print("CHECK 6: All NAV Entries Valid")
        print("-" * 40)
        
        cursor.execute("""
            SELECT date, nav_per_share, total_portfolio_value, total_shares
            FROM daily_nav
            ORDER BY date
        """)
        nav_entries = cursor.fetchall()
        
        invalid_entries = []
        for date, nav, portfolio, shares in nav_entries:
            if shares > 0:
                calc_nav = portfolio / shares
                if abs(nav - calc_nav) > 0.0001:
                    invalid_entries.append((date, nav, calc_nav))
        
        if invalid_entries:
            print(f"  ❌ FAIL - {len(invalid_entries)} invalid NAV entries:")
            for date, stored, calc in invalid_entries[:5]:  # Show first 5
                print(f"     {date}: Stored ${stored:.4f}, Should be ${calc:.4f}")
            if len(invalid_entries) > 5:
                print(f"     ... and {len(invalid_entries) - 5} more")
            all_checks_passed = False
        else:
            print(f"  ✅ PASS - All {len(nav_entries)} NAV entries valid")
        print()
        
        # CHECK 7: No Negative Values
        print("CHECK 7: No Negative Values")
        print("-" * 40)
        
        cursor.execute("""
            SELECT COUNT(*)
            FROM investors
            WHERE current_shares < 0 OR net_investment < 0
        """)
        negative_investors = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*)
            FROM daily_nav
            WHERE total_portfolio_value < 0 OR total_shares < 0 OR nav_per_share < 0
        """)
        negative_nav = cursor.fetchone()[0]
        
        if negative_investors > 0:
            print(f"  ❌ FAIL - {negative_investors} investors with negative values!")
            all_checks_passed = False
        else:
            print("  ✅ PASS - No negative investor values")
        
        if negative_nav > 0:
            print(f"  ❌ FAIL - {negative_nav} NAV entries with negative values!")
            all_checks_passed = False
        else:
            print("  ✅ PASS - No negative NAV values")
        print()
        
        # CHECK 8: Transaction Integrity
        print("CHECK 8: Transaction Sum = Net Investment")
        print("-" * 40)
        
        transaction_check_passed = True
        for inv_id, name, _ in investors:
            cursor.execute("""
                SELECT SUM(amount)
                FROM transactions
                WHERE investor_id = ?
            """, (inv_id,))
            trans_sum = cursor.fetchone()[0] or 0
            
            cursor.execute("""
                SELECT net_investment
                FROM investors
                WHERE investor_id = ?
            """, (inv_id,))
            net_inv = cursor.fetchone()[0] or 0
            
            diff = abs(trans_sum - net_inv)
            if diff > 0.01:
                print(f"  ❌ {name}: Transaction sum ${trans_sum:,.2f} != Net investment ${net_inv:,.2f}")
                transaction_check_passed = False
                all_checks_passed = False
        
        if transaction_check_passed:
            print("  ✅ PASS - All transaction sums match net investments")
        print()
        
        # FINAL RESULT
        print("=" * 80)
        if all_checks_passed:
            print("✅ ALL CHECKS PASSED - System is valid!")
            print("=" * 80)
            conn.close()
            return True
        else:
            print("❌ VALIDATION FAILED - Issues found above")
            print("=" * 80)
            print()
            print("RECOMMENDED ACTIONS:")
            print("  1. Review failed checks above")
            print("  2. Fix issues using appropriate scripts")
            print("  3. Run validation again")
            print()
            conn.close()
            return False
        
    except Exception as e:
        print(f"❌ Error during validation: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = validate_comprehensive()
    sys.exit(0 if success else 1)
