#!/usr/bin/env python3
"""
Tovito Trader - System Upgrade Script v2.0 (FIXED v2)
=====================================================

Now adapts to your actual database schema!
"""

import os
import sys
import shutil
import sqlite3
import argparse
from datetime import datetime
from pathlib import Path


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║         TOVITO TRADER - SYSTEM UPGRADE v2.0 (FIXED v2)              ║
║                                                                      ║
║   New Features:                                                      ║
║   • Live Tradier Streaming                                          ║
║   • Improved Database Schema                                        ║
║   • Live Dashboard                                                   ║
║   • Data Fixes (Ken & Beth)                                         ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")


def find_database():
    paths = [
        Path("data/tovito.db"),
        Path("../data/tovito.db"),
        Path("C:/tovito-trader/data/tovito.db"),
    ]
    for path in paths:
        if path.exists():
            return path
    return None


def backup_database(db_path: Path, backup_dir: Path = None):
    if backup_dir is None:
        backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_name = f"tovito_backup_{timestamp}_pre_upgrade.db"
    backup_path = backup_dir / backup_name
    shutil.copy2(db_path, backup_path)
    return backup_path


def check_prerequisites():
    issues = []
    if sys.version_info < (3, 8):
        issues.append(f"Python 3.8+ required (found {sys.version})")
    try:
        import requests
    except ImportError:
        issues.append("requests package not installed: pip install requests")
    try:
        import dotenv
    except ImportError:
        issues.append("python-dotenv not installed: pip install python-dotenv")
    
    env_path = Path(".env")
    if not env_path.exists():
        env_path = Path("../.env")
    if env_path.exists():
        with open(env_path) as f:
            content = f.read()
            if 'TRADIER_API_KEY' not in content:
                issues.append("TRADIER_API_KEY not set in .env")
            if 'TRADIER_ACCOUNT_ID' not in content:
                issues.append("TRADIER_ACCOUNT_ID not set in .env")
    
    return issues


def get_table_columns(cursor, table_name):
    """Get list of columns in a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1]: row[2] for row in cursor.fetchall()}  # name: type


def show_table_schema(cursor, table_name):
    """Show the schema of a table"""
    columns = get_table_columns(cursor, table_name)
    print(f"\n  {table_name} columns:")
    for col, col_type in columns.items():
        print(f"    - {col} ({col_type})")
    return columns


def add_column_safe(cursor, table_name, col_name, col_type, default=None):
    """Safely add a column if it doesn't exist"""
    existing = get_table_columns(cursor, table_name)
    if col_name in existing:
        return False
    
    if default is not None:
        sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type} DEFAULT {default}"
    else:
        sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
    
    cursor.execute(sql)
    print(f"    Adding column: {table_name}.{col_name}")
    return True


def migrate_database_schema(cursor):
    """Migrate database to v2 schema"""
    print("\n📊 Migrating database schema...")
    
    # Show current schema
    print("\n  Current table schemas:")
    investors_cols = show_table_schema(cursor, 'investors')
    txn_cols = show_table_schema(cursor, 'transactions')
    nav_cols = show_table_schema(cursor, 'daily_nav')
    
    # INVESTORS TABLE
    add_column_safe(cursor, 'investors', 'email', 'TEXT')
    add_column_safe(cursor, 'investors', 'phone', 'TEXT')
    add_column_safe(cursor, 'investors', 'created_at', 'TEXT')
    add_column_safe(cursor, 'investors', 'updated_at', 'TEXT')
    add_column_safe(cursor, 'investors', 'is_deleted', 'INTEGER', '0')
    
    cursor.execute("""
        UPDATE investors 
        SET created_at = datetime('now'), updated_at = datetime('now')
        WHERE created_at IS NULL
    """)
    
    # TRANSACTIONS TABLE - add columns that might be missing
    add_column_safe(cursor, 'transactions', 'nav_per_share', 'REAL')
    add_column_safe(cursor, 'transactions', 'description', 'TEXT')
    add_column_safe(cursor, 'transactions', 'reference_id', 'TEXT')
    add_column_safe(cursor, 'transactions', 'created_at', 'TEXT')
    add_column_safe(cursor, 'transactions', 'updated_at', 'TEXT')
    add_column_safe(cursor, 'transactions', 'is_deleted', 'INTEGER', '0')
    
    cursor.execute("""
        UPDATE transactions 
        SET created_at = datetime('now'), updated_at = datetime('now')
        WHERE created_at IS NULL
    """)
    
    # DAILY_NAV TABLE
    add_column_safe(cursor, 'daily_nav', 'daily_change_value', 'REAL')
    add_column_safe(cursor, 'daily_nav', 'daily_change_percent', 'REAL')
    add_column_safe(cursor, 'daily_nav', 'tradier_balance', 'REAL')
    add_column_safe(cursor, 'daily_nav', 'created_at', 'TEXT')
    add_column_safe(cursor, 'daily_nav', 'updated_at', 'TEXT')
    
    cursor.execute("""
        UPDATE daily_nav 
        SET created_at = datetime('now'), updated_at = datetime('now')
        WHERE created_at IS NULL
    """)
    
    # AUDIT_LOG TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            table_name TEXT NOT NULL,
            record_id TEXT NOT NULL,
            action TEXT NOT NULL,
            old_values TEXT,
            new_values TEXT,
            performed_by TEXT DEFAULT 'system'
        )
    """)
    print("    Created table: audit_log (if not exists)")
    
    # SYSTEM_CONFIG TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TEXT
        )
    """)
    print("    Created table: system_config (if not exists)")
    
    # Insert default config
    config = [
        ('schema_version', '2.0.0', 'Database schema version'),
        ('tax_rate', '0.37', 'Federal tax rate'),
        ('fund_name', 'Tovito Trader', 'Fund display name'),
    ]
    for key, value, desc in config:
        cursor.execute("""
            INSERT OR REPLACE INTO system_config (key, value, description, updated_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (key, value, desc))
    
    # INDEXES
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date)",
        "CREATE INDEX IF NOT EXISTS idx_transactions_investor ON transactions(investor_id)",
        "CREATE INDEX IF NOT EXISTS idx_daily_nav_date ON daily_nav(date)",
    ]
    for idx in indexes:
        try:
            cursor.execute(idx)
        except sqlite3.OperationalError:
            pass
    
    print("    ✅ Schema migration complete")


def check_missing_contributions(cursor) -> list:
    """Check for missing Ken and Beth contributions"""
    cursor.execute("""
        SELECT investor_id, name, current_shares, net_investment
        FROM investors
        WHERE (LOWER(name) LIKE '%ken%' OR LOWER(name) LIKE '%beth%' OR LOWER(name) LIKE '%elizabeth%')
          AND status = 'Active'
    """)
    
    investors = cursor.fetchall()
    missing = []
    
    for inv_id, name, shares, net in investors:
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE investor_id = ?
        """, (inv_id,))
        
        row = cursor.fetchone()
        txn_count = row[0] if row else 0
        txn_total = row[1] if row else 0
        
        if shares > 0 and txn_count == 0:
            missing.append({
                'id': inv_id,
                'name': name,
                'shares': shares,
                'net_investment': net,
                'txn_count': 0,
                'txn_total': 0,
                'reason': 'No transactions found'
            })
        elif txn_total is not None and abs(txn_total - net) > 0.01:
            missing.append({
                'id': inv_id,
                'name': name,
                'shares': shares,
                'net_investment': net,
                'txn_count': txn_count,
                'txn_total': txn_total,
                'reason': f'Mismatch: txns=${txn_total:.2f} vs net=${net:.2f}'
            })
    
    return missing


def fix_missing_contribution(cursor, investor_id: str, investor_name: str, amount: float, nav: float, date: str):
    """Add a missing contribution - adapts to actual schema"""
    shares = amount / nav
    
    # Get actual columns in transactions table
    columns = get_table_columns(cursor, 'transactions')
    print(f"    Transactions table columns: {list(columns.keys())}")
    
    # Build INSERT statement based on available columns
    insert_cols = ['date', 'investor_id', 'transaction_type', 'amount', 'shares_transacted']
    insert_vals = [date, investor_id, 'Initial', amount, shares]
    
    # Handle NAV/share_price - check which column exists
    # Your schema uses 'share_price' (NOT NULL), not 'nav_per_share'
    if 'share_price' in columns:
        insert_cols.append('share_price')
        insert_vals.append(nav)
    elif 'nav_per_share' in columns:
        insert_cols.append('nav_per_share')
        insert_vals.append(nav)
    
    if 'notes' in columns:
        insert_cols.append('notes')
        insert_vals.append(f"Fixed via upgrade script - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    if 'created_at' in columns:
        insert_cols.append('created_at')
        insert_vals.append(datetime.now().isoformat())
    
    if 'updated_at' in columns:
        insert_cols.append('updated_at')
        insert_vals.append(datetime.now().isoformat())
    
    # Build and execute query
    placeholders = ', '.join(['?' for _ in insert_vals])
    col_names = ', '.join(insert_cols)
    
    sql = f"INSERT INTO transactions ({col_names}) VALUES ({placeholders})"
    print(f"    SQL: {sql}")
    print(f"    Values: {insert_vals}")
    
    cursor.execute(sql, insert_vals)
    
    print(f"    ✅ Added Initial for {investor_name}: ${amount:,.2f} = {shares:,.4f} shares at NAV ${nav:.4f}")
    return True


def show_current_state(cursor):
    """Show current database state"""
    print("\n📊 CURRENT DATABASE STATE:")
    print("-" * 60)
    
    cursor.execute("""
        SELECT investor_id, name, current_shares, net_investment, status
        FROM investors
        WHERE status = 'Active'
        ORDER BY current_shares DESC
    """)
    
    print("\nInvestors:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1][:20]:<20} | Shares: {row[2]:>12,.4f} | Net: ${row[3]:>10,.2f}")
    
    cursor.execute("SELECT COUNT(*) FROM transactions")
    txn_count = cursor.fetchone()[0]
    print(f"\nTotal transactions: {txn_count}")
    
    # Show transactions
    cursor.execute("SELECT * FROM transactions ORDER BY date LIMIT 10")
    rows = cursor.fetchall()
    if rows:
        # Get column names
        col_names = [desc[0] for desc in cursor.description]
        print(f"\nTransaction columns: {col_names}")
        print("\nRecent transactions:")
        for row in rows:
            print(f"  {row}")
    
    cursor.execute("""
        SELECT date, nav_per_share, total_portfolio_value
        FROM daily_nav
        ORDER BY date DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    if row:
        print(f"\nLatest NAV: ${row[1]:.4f} on {row[0]} (Portfolio: ${row[2]:,.2f})")


def main():
    parser = argparse.ArgumentParser(description="Tovito Trader System Upgrade")
    parser.add_argument('--skip-backup', action='store_true', help='Skip backup')
    parser.add_argument('--skip-migration', action='store_true', help='Skip schema migration')
    parser.add_argument('--skip-fix', action='store_true', help='Skip contribution fix')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    parser.add_argument('--db', help='Database path')
    
    args = parser.parse_args()
    
    print_banner()
    
    # Check prerequisites
    print("🔍 Checking prerequisites...")
    issues = check_prerequisites()
    if issues:
        print("\n⚠️  Prerequisites not met:")
        for issue in issues:
            print(f"    • {issue}")
        print("\nPlease fix these issues and try again.")
        return 1
    print("    ✅ All prerequisites met")
    
    # Find database
    print("\n📂 Finding database...")
    db_path = Path(args.db) if args.db else find_database()
    
    if not db_path or not db_path.exists():
        print("    ❌ Database not found!")
        return 1
    
    print(f"    Found: {db_path}")
    
    # Backup
    if not args.skip_backup:
        print("\n💾 Creating backup...")
        if args.dry_run:
            print("    [DRY RUN] Would create backup")
        else:
            backup_path = backup_database(db_path)
            print(f"    ✅ Backup created: {backup_path}")
    
    # Connect
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Show current state
        show_current_state(cursor)
        
        # Schema migration
        if not args.skip_migration:
            if args.dry_run:
                print("\n📊 [DRY RUN] Would migrate database schema")
            else:
                migrate_database_schema(cursor)
        
        # Check for missing contributions
        if not args.skip_fix:
            print("\n🔍 Checking for missing contributions...")
            missing = check_missing_contributions(cursor)
            
            if missing:
                print(f"\n⚠️  Found {len(missing)} investor(s) with potential issues:")
                for inv in missing:
                    print(f"\n    {inv['name']} ({inv['id']}):")
                    print(f"      Shares: {inv['shares']:,.4f}")
                    print(f"      Net Investment: ${inv['net_investment']:,.2f}")
                    print(f"      Transactions: {inv['txn_count']} (total: ${inv.get('txn_total', 0):,.2f})")
                    print(f"      Issue: {inv.get('reason', 'Unknown')}")
                
                print("\n" + "="*60)
                print("  FIX MISSING CONTRIBUTIONS")
                print("="*60)
                
                if not args.dry_run:
                    fix = input("\n  Add missing contributions? (yes/no): ").strip().lower()
                    
                    if fix == 'yes':
                        date = input("  Date of contributions [2026-01-02]: ").strip() or "2026-01-02"
                        nav = float(input("  NAV at contribution [1.0000]: ").strip() or "1.0000")
                        
                        for inv in missing:
                            name_lower = inv['name'].lower()
                            if 'ken' in name_lower or 'beth' in name_lower or 'elizabeth' in name_lower:
                                amount = float(input(f"  {inv['name']} contribution amount [1000]: ").strip() or "1000")
                                print(f"\n    Processing {inv['name']}...")
                                fix_missing_contribution(cursor, inv['id'], inv['name'], amount, nav, date)
            else:
                print("    ✅ No missing contributions detected")
        
        # Commit
        if not args.dry_run:
            conn.commit()
            print("\n✅ All changes committed successfully!")
            show_current_state(cursor)
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        print("Changes rolled back")
        return 1
    finally:
        conn.close()
    
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                         UPGRADE COMPLETE!                            ║
╚══════════════════════════════════════════════════════════════════════╝

📋 NEXT STEPS:
1. python run.py validate
2. python scripts/validate_with_ach.py (if available)

Enjoy your upgraded system! 🚀
""")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
