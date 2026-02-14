#!/usr/bin/env python3
"""
Fix Missing Contributions - Ken & Beth
=======================================
This script adds the missing contribution records for Ken and Beth
who each contributed $1,000 when NAV was $1.0000.

The ACH shows a $2,000 deposit but transactions weren't recorded.
"""

import sqlite3
from datetime import datetime
from pathlib import Path


def get_database_path():
    """Find the database file"""
    # Try common locations
    paths = [
        Path("data/tovito.db"),
        Path("../data/tovito.db"),
        Path("C:/tovito-trader/data/tovito.db"),
    ]
    
    for path in paths:
        if path.exists():
            return path
    
    # Ask user
    user_path = input("Enter path to tovito.db: ").strip()
    return Path(user_path)


def show_current_state(cursor):
    """Show current database state"""
    print("\n" + "="*70)
    print("CURRENT DATABASE STATE")
    print("="*70)
    
    # Show investors
    print("\n📊 INVESTORS:")
    print("-" * 70)
    cursor.execute("""
        SELECT investor_id, name, current_shares, net_investment, status
        FROM investors
        ORDER BY investor_id
    """)
    investors = cursor.fetchall()
    for inv in investors:
        print(f"  {inv[0]} | {inv[1][:20]:20} | Shares: {inv[2]:,.4f} | Net: ${inv[3]:,.2f} | {inv[4]}")
    
    # Show transactions
    print("\n📝 TRANSACTIONS:")
    print("-" * 70)
    cursor.execute("""
        SELECT date, investor_id, transaction_type, amount, shares_transacted, nav_per_share
        FROM transactions
        ORDER BY date, investor_id
    """)
    txns = cursor.fetchall()
    for t in txns:
        print(f"  {t[0]} | {t[1]} | {t[2]:12} | ${t[3]:>10,.2f} | {t[4]:>12,.4f} shares | NAV ${t[5]:.4f}")
    
    # Show daily NAV for early dates
    print("\n📈 DAILY NAV (first 5 days):")
    print("-" * 70)
    cursor.execute("""
        SELECT date, total_portfolio_value, total_shares, nav_per_share
        FROM daily_nav
        ORDER BY date
        LIMIT 5
    """)
    navs = cursor.fetchall()
    for n in navs:
        print(f"  {n[0]} | Portfolio: ${n[1]:,.2f} | Shares: {n[2]:,.4f} | NAV: ${n[3]:.4f}")
    
    # Show ACH summary from trades table (if exists)
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='trades'
    """)
    if cursor.fetchone():
        print("\n💰 ACH DEPOSITS (from trades table):")
        print("-" * 70)
        cursor.execute("""
            SELECT date, amount, description
            FROM trades
            WHERE type = 'ach' OR LOWER(description) LIKE '%ach%'
            ORDER BY date
        """)
        achs = cursor.fetchall()
        for a in achs:
            print(f"  {a[0]} | ${a[1]:,.2f} | {a[2][:50] if a[2] else ''}")


def find_ken_and_beth(cursor):
    """Find Ken and Beth's investor IDs"""
    cursor.execute("""
        SELECT investor_id, name
        FROM investors
        WHERE LOWER(name) LIKE '%ken%' OR LOWER(name) LIKE '%beth%' 
           OR LOWER(name) LIKE '%elizabeth%'
        ORDER BY investor_id
    """)
    investors = cursor.fetchall()
    
    ken_id = None
    beth_id = None
    
    for inv_id, name in investors:
        name_lower = name.lower()
        if 'ken' in name_lower:
            ken_id = inv_id
            print(f"  Found Ken: {inv_id} - {name}")
        elif 'beth' in name_lower or 'elizabeth' in name_lower:
            beth_id = inv_id
            print(f"  Found Beth: {inv_id} - {name}")
    
    return ken_id, beth_id


def check_existing_contributions(cursor, investor_id, nav_target=1.0000):
    """Check if investor already has a contribution at the target NAV"""
    cursor.execute("""
        SELECT COUNT(*) 
        FROM transactions 
        WHERE investor_id = ? 
          AND transaction_type IN ('Initial', 'Contribution')
          AND ABS(nav_per_share - ?) < 0.0001
    """, (investor_id, nav_target))
    return cursor.fetchone()[0] > 0


def add_contribution(cursor, investor_id, investor_name, amount, nav, date_str):
    """Add a contribution transaction and update investor shares"""
    
    shares = amount / nav
    
    # Check if transaction already exists
    if check_existing_contributions(cursor, investor_id, nav):
        print(f"  ⚠️  {investor_name} already has a contribution at NAV ${nav:.4f}")
        return False
    
    # Determine transaction type
    cursor.execute("""
        SELECT COUNT(*) FROM transactions 
        WHERE investor_id = ? AND transaction_type = 'Initial'
    """, (investor_id,))
    has_initial = cursor.fetchone()[0] > 0
    
    txn_type = 'Contribution' if has_initial else 'Initial'
    
    # Add transaction
    cursor.execute("""
        INSERT INTO transactions 
        (date, investor_id, transaction_type, amount, shares_transacted, nav_per_share, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        date_str,
        investor_id,
        txn_type,
        amount,
        shares,
        nav,
        f"Fixed missing {txn_type.lower()} - added {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    ))
    
    # Update investor shares and net investment
    cursor.execute("""
        UPDATE investors
        SET current_shares = current_shares + ?,
            net_investment = net_investment + ?
        WHERE investor_id = ?
    """, (shares, amount, investor_id))
    
    print(f"  ✅ Added {txn_type} for {investor_name}:")
    print(f"      Amount: ${amount:,.2f}")
    print(f"      Shares: {shares:,.4f}")
    print(f"      NAV: ${nav:.4f}")
    print(f"      Date: {date_str}")
    
    return True


def update_daily_nav(cursor, date_str, additional_value, additional_shares):
    """Update daily NAV for the contribution date"""
    cursor.execute("""
        SELECT total_portfolio_value, total_shares
        FROM daily_nav
        WHERE date = ?
    """, (date_str,))
    
    row = cursor.fetchone()
    if row:
        new_value = row[0] + additional_value
        new_shares = row[1] + additional_shares
        new_nav = new_value / new_shares if new_shares > 0 else 1.0
        
        cursor.execute("""
            UPDATE daily_nav
            SET total_portfolio_value = ?,
                total_shares = ?,
                nav_per_share = ?
            WHERE date = ?
        """, (new_value, new_shares, new_nav, date_str))
        
        print(f"  ✅ Updated daily_nav for {date_str}:")
        print(f"      New portfolio value: ${new_value:,.2f}")
        print(f"      New total shares: {new_shares:,.4f}")
        print(f"      NAV: ${new_nav:.4f}")
    else:
        # Create new daily NAV entry
        print(f"  ⚠️  No daily_nav entry for {date_str} - may need to add manually")


def main():
    print("\n" + "="*70)
    print("FIX MISSING CONTRIBUTIONS - Ken & Beth")
    print("="*70)
    print("\nThis script will add the missing $1,000 contributions for Ken and Beth")
    print("who contributed when NAV was $1.0000.\n")
    
    # Find database
    db_path = get_database_path()
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    print(f"📂 Database: {db_path}")
    
    # Connect
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Show current state
    show_current_state(cursor)
    
    # Find Ken and Beth
    print("\n🔍 Finding Ken and Beth...")
    ken_id, beth_id = find_ken_and_beth(cursor)
    
    if not ken_id:
        print("❌ Could not find Ken in investors table!")
        ken_id = input("Enter Ken's investor_id manually (e.g., 20260101-03A): ").strip()
        if not ken_id:
            return
    
    if not beth_id:
        print("❌ Could not find Beth/Elizabeth in investors table!")
        beth_id = input("Enter Beth's investor_id manually (e.g., 20260101-02A): ").strip()
        if not beth_id:
            return
    
    # Get contribution details
    print("\n📝 CONTRIBUTION DETAILS:")
    print("-" * 40)
    
    # Default values based on the known scenario
    default_date = "2026-01-02"  # When Ken and Beth likely contributed
    default_nav = 1.0000
    default_amount = 1000.00
    
    date_str = input(f"  Date of contribution [{default_date}]: ").strip() or default_date
    nav = float(input(f"  NAV at contribution [{default_nav}]: ").strip() or default_nav)
    ken_amount = float(input(f"  Ken's contribution amount [{default_amount}]: ").strip() or default_amount)
    beth_amount = float(input(f"  Beth's contribution amount [{default_amount}]: ").strip() or default_amount)
    
    # Summary and confirmation
    print("\n" + "="*70)
    print("SUMMARY - WILL ADD:")
    print("="*70)
    print(f"\n  Ken ({ken_id}):")
    print(f"    Amount: ${ken_amount:,.2f}")
    print(f"    Shares: {ken_amount/nav:,.4f}")
    print(f"    Date: {date_str}")
    print(f"    NAV: ${nav:.4f}")
    
    print(f"\n  Beth ({beth_id}):")
    print(f"    Amount: ${beth_amount:,.2f}")
    print(f"    Shares: {beth_amount/nav:,.4f}")
    print(f"    Date: {date_str}")
    print(f"    NAV: ${nav:.4f}")
    
    total_amount = ken_amount + beth_amount
    total_shares = total_amount / nav
    print(f"\n  TOTAL: ${total_amount:,.2f} / {total_shares:,.4f} shares")
    
    confirm = input("\n⚠️  Proceed with these changes? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Cancelled")
        conn.close()
        return
    
    # Execute changes
    print("\n🔧 PROCESSING CHANGES...")
    print("-" * 40)
    
    try:
        # Add Ken's contribution
        cursor.execute("SELECT name FROM investors WHERE investor_id = ?", (ken_id,))
        ken_name = cursor.fetchone()[0] if cursor.fetchone else "Ken"
        cursor.execute("SELECT name FROM investors WHERE investor_id = ?", (ken_id,))
        row = cursor.fetchone()
        ken_name = row[0] if row else "Ken"
        add_contribution(cursor, ken_id, ken_name, ken_amount, nav, date_str)
        
        # Add Beth's contribution
        cursor.execute("SELECT name FROM investors WHERE investor_id = ?", (beth_id,))
        row = cursor.fetchone()
        beth_name = row[0] if row else "Beth"
        add_contribution(cursor, beth_id, beth_name, beth_amount, nav, date_str)
        
        # Update daily NAV
        print("\n📈 UPDATING DAILY NAV...")
        update_daily_nav(cursor, date_str, total_amount, total_shares)
        
        # Commit
        conn.commit()
        print("\n✅ Changes committed successfully!")
        
        # Show updated state
        print("\n" + "="*70)
        print("UPDATED DATABASE STATE")
        print("="*70)
        show_current_state(cursor)
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        print("Changes rolled back.")
    
    conn.close()
    
    print("\n" + "="*70)
    print("NEXT STEPS:")
    print("="*70)
    print("""
1. Run validation to verify:
   python scripts/validate_with_ach.py
   
2. If validation passes, create a backup:
   python run.py backup
   
3. Verify ACH reconciliation:
   - ACH deposit: $2,000
   - Ken contribution: $1,000
   - Beth contribution: $1,000
   - Total: $2,000 ✓
""")


if __name__ == "__main__":
    main()
