"""
TOVITO DASHBOARD - Database Diagnostic
Run this to check your database schema and data
"""

import sqlite3
import sys
from pathlib import Path

def diagnose_database(db_path):
    """Diagnose database structure and data"""
    print(f"\n{'='*60}")
    print(f"TOVITO DATABASE DIAGNOSTIC")
    print(f"{'='*60}")
    print(f"Database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"\n📋 TABLES FOUND: {len(tables)}")
        for t in tables:
            print(f"   - {t}")
        
        # Check each important table
        important_tables = ['investors', 'daily_nav', 'transactions', 'trades', 'tax_events']
        
        for table in important_tables:
            print(f"\n{'─'*60}")
            if table not in tables:
                print(f"❌ TABLE '{table}' NOT FOUND")
                continue
            
            print(f"✅ TABLE: {table}")
            
            # Get columns
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            print(f"   Columns ({len(columns)}):")
            for col in columns:
                print(f"      {col[1]:20} {col[2]:15} {'NOT NULL' if col[3] else ''}")
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"   Row count: {count}")
            
            # Show sample data
            if count > 0:
                cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                rows = cursor.fetchall()
                col_names = [col[1] for col in columns]
                print(f"   Sample data:")
                for row in rows:
                    print(f"      {dict(zip(col_names, row))}")
        
        # Check specific queries used by dashboard
        print(f"\n{'='*60}")
        print("🔍 TESTING DASHBOARD QUERIES")
        print(f"{'='*60}")
        
        # Test 1: Portfolio Summary
        print("\n1. Portfolio Summary (latest NAV):")
        try:
            cursor.execute("""
                SELECT total_portfolio_value, total_shares, nav_per_share, date
                FROM daily_nav ORDER BY date DESC LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                print(f"   ✅ Portfolio Value: ${row[0]:,.2f}")
                print(f"   ✅ Total Shares: {row[1]:,.2f}")
                print(f"   ✅ NAV per Share: ${row[2]:.4f}")
                print(f"   ✅ Date: {row[3]}")
            else:
                print("   ❌ No data returned")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 2: Yesterday's NAV (for comparison)
        print("\n2. Previous NAV (for change calculation):")
        try:
            cursor.execute("""
                SELECT nav_per_share, date FROM daily_nav 
                ORDER BY date DESC LIMIT 2
            """)
            rows = cursor.fetchall()
            if len(rows) >= 2:
                print(f"   ✅ Latest: ${rows[0][0]:.4f} ({rows[0][1]})")
                print(f"   ✅ Previous: ${rows[1][0]:.4f} ({rows[1][1]})")
                change = rows[0][0] - rows[1][0]
                change_pct = (change / rows[1][0]) * 100 if rows[1][0] else 0
                print(f"   ✅ Change: ${change:.4f} ({change_pct:+.2f}%)")
            elif len(rows) == 1:
                print(f"   ⚠️ Only 1 NAV record: {rows[0]}")
            else:
                print("   ❌ No NAV records")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 3: Active Investors
        print("\n3. Active Investors:")
        try:
            # First try with status column
            cursor.execute("""
                SELECT investor_id, name, shares, net_investment, status
                FROM investors
                WHERE status = 'Active' OR status IS NULL OR status = ''
            """)
            rows = cursor.fetchall()
            print(f"   ✅ Found {len(rows)} active investors")
            for row in rows:
                print(f"      {row[0]}: {row[1]} - {row[2]:,.2f} shares, ${row[3]:,.2f} invested, status='{row[4]}'")
        except Exception as e:
            print(f"   ⚠️ Status column issue: {e}")
            # Try without status filter
            try:
                cursor.execute("SELECT investor_id, name, shares, net_investment FROM investors")
                rows = cursor.fetchall()
                print(f"   ✅ Found {len(rows)} total investors (no status filter)")
                for row in rows:
                    print(f"      {row[0]}: {row[1]} - {row[2]:,.2f} shares, ${row[3]:,.2f} invested")
            except Exception as e2:
                print(f"   ❌ Error: {e2}")
        
        # Test 4: Recent Transactions
        print("\n4. Recent Transactions:")
        try:
            cursor.execute("""
                SELECT t.date, t.investor_id, t.type, t.amount, t.shares, t.nav_per_share
                FROM transactions t
                ORDER BY t.date DESC LIMIT 5
            """)
            rows = cursor.fetchall()
            print(f"   ✅ Found {len(rows)} transactions")
            for row in rows:
                print(f"      {row[0]}: {row[1]} - {row[2]} ${row[3]:,.2f}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 5: Check all NAV dates
        print("\n5. NAV Date Range:")
        try:
            cursor.execute("""
                SELECT MIN(date) as earliest, MAX(date) as latest, COUNT(*) as count
                FROM daily_nav
            """)
            row = cursor.fetchone()
            print(f"   ✅ Earliest: {row[0]}")
            print(f"   ✅ Latest: {row[1]}")
            print(f"   ✅ Total records: {row[2]}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        conn.close()
        
        print(f"\n{'='*60}")
        print("DIAGNOSTIC COMPLETE")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")

if __name__ == "__main__":
    # Try common paths
    paths_to_try = [
        "data/tovito.db",
        "../data/tovito.db",
        "C:/tovito-trader/data/tovito.db",
    ]
    
    # Check command line argument
    if len(sys.argv) > 1:
        paths_to_try.insert(0, sys.argv[1])
    
    for path in paths_to_try:
        if Path(path).exists():
            diagnose_database(path)
            break
    else:
        print("❌ Could not find database!")
        print("Usage: python diagnose_db.py [path_to_tovito.db]")
        print(f"Tried: {paths_to_try}")
