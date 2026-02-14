"""
Query Trades Table - Interactive Viewer

Replaces sqlite3 command line for Windows users.
Shows trading activity in easy-to-read format.

Usage:
    python scripts/query_trades.py               # Interactive menu
    python scripts/query_trades.py --ach         # Show ACH summary
    python scripts/query_trades.py --symbol SGOV # Show SGOV trades
    python scripts/query_trades.py --summary     # Show overall summary
"""

import sqlite3
import argparse
from pathlib import Path
from datetime import datetime


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def show_ach_summary(cursor):
    """Show ACH deposits/withdrawals summary"""
    print()
    print("=" * 80)
    print("ACH SUMMARY")
    print("=" * 80)
    print()
    
    cursor.execute("""
        SELECT 
            date,
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as deposits,
            SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as withdrawals,
            SUM(amount) as net
        FROM trades
        WHERE type IN ('ach', 'wire', 'journal')
        GROUP BY date
        ORDER BY date
    """)
    
    rows = cursor.fetchall()
    
    if not rows:
        print("No ACH transactions found")
        return
    
    print(f"{'Date':<12} {'Deposits':>15} {'Withdrawals':>15} {'Net':>15}")
    print("-" * 80)
    
    total_deposits = 0
    total_withdrawals = 0
    
    for date, deposits, withdrawals, net in rows:
        print(f"{date:<12} ${deposits:>14,.2f} ${withdrawals:>14,.2f} ${net:>14,.2f}")
        total_deposits += deposits
        total_withdrawals += withdrawals
    
    print("-" * 80)
    print(f"{'TOTAL':<12} ${total_deposits:>14,.2f} ${total_withdrawals:>14,.2f} ${total_deposits - total_withdrawals:>14,.2f}")
    print()


def show_symbol_trades(cursor, symbol):
    """Show all trades for a specific symbol"""
    print()
    print("=" * 80)
    print(f"TRADES FOR {symbol}")
    print("=" * 80)
    print()
    
    cursor.execute("""
        SELECT date, trade_type, quantity, price, amount, commission, description
        FROM trades
        WHERE symbol = ? AND category = 'Trade'
        ORDER BY date
    """, (symbol,))
    
    rows = cursor.fetchall()
    
    if not rows:
        print(f"No trades found for {symbol}")
        return
    
    print(f"{'Date':<12} {'Type':<10} {'Quantity':>10} {'Price':>10} {'Amount':>12} {'Comm':>8}")
    print("-" * 80)
    
    total_amount = 0
    total_commission = 0
    
    for date, trade_type, quantity, price, amount, commission, description in rows:
        qty_str = f"{quantity:.0f}" if quantity else ""
        price_str = f"${price:.2f}" if price else ""
        comm_str = f"${commission:.2f}" if commission else ""
        
        print(f"{date:<12} {trade_type:<10} {qty_str:>10} {price_str:>10} ${amount:>11,.2f} {comm_str:>8}")
        total_amount += amount
        total_commission += commission
    
    print("-" * 80)
    print(f"{'TOTAL':<12} {'':<10} {'':<10} {'':<10} ${total_amount:>11,.2f} ${total_commission:>7,.2f}")
    print()
    print(f"Net P&L: ${total_amount:,.2f}")
    print(f"Total Commission: ${total_commission:,.2f}")
    print()


def show_all_symbols(cursor):
    """Show summary by symbol"""
    print()
    print("=" * 80)
    print("TRADING SUMMARY BY SYMBOL")
    print("=" * 80)
    print()
    
    cursor.execute("""
        SELECT 
            symbol,
            COUNT(*) as trade_count,
            SUM(quantity) as net_quantity,
            SUM(amount) as total_amount,
            SUM(commission) as total_commission
        FROM trades
        WHERE category = 'Trade' AND symbol != ''
        GROUP BY symbol
        ORDER BY total_amount DESC
    """)
    
    rows = cursor.fetchall()
    
    if not rows:
        print("No trades found")
        return
    
    print(f"{'Symbol':<10} {'Trades':>8} {'Net Qty':>12} {'Total Amount':>15} {'Commission':>12}")
    print("-" * 80)
    
    for symbol, count, qty, amount, commission in rows:
        qty_str = f"{qty:.0f}" if qty else ""
        print(f"{symbol:<10} {count:>8} {qty_str:>12} ${amount:>14,.2f} ${commission:>11,.2f}")
    
    print()


def show_monthly_activity(cursor):
    """Show monthly trading activity"""
    print()
    print("=" * 80)
    print("MONTHLY TRADING ACTIVITY")
    print("=" * 80)
    print()
    
    cursor.execute("""
        SELECT 
            strftime('%Y-%m', date) as month,
            category,
            COUNT(*) as count,
            SUM(amount) as total_amount
        FROM trades
        GROUP BY month, category
        ORDER BY month DESC, category
    """)
    
    rows = cursor.fetchall()
    
    if not rows:
        print("No transactions found")
        return
    
    current_month = None
    
    for month, category, count, amount in rows:
        if month != current_month:
            if current_month:
                print()
            print(f"Month: {month}")
            print("-" * 40)
            current_month = month
        
        print(f"  {category:<12} {count:>5} transactions  ${amount:>12,.2f}")
    
    print()


def show_overall_summary(cursor):
    """Show overall summary"""
    print()
    print("=" * 80)
    print("OVERALL SUMMARY")
    print("=" * 80)
    print()
    
    # Total trades
    cursor.execute("SELECT COUNT(*) FROM trades WHERE category = 'Trade'")
    total_trades = cursor.fetchone()[0]
    
    # Unique symbols
    cursor.execute("SELECT COUNT(DISTINCT symbol) FROM trades WHERE symbol != ''")
    unique_symbols = cursor.fetchone()[0]
    
    # ACH totals
    cursor.execute("""
        SELECT 
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as deposits,
            SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as withdrawals
        FROM trades
        WHERE type IN ('ach', 'wire', 'journal')
    """)
    deposits, withdrawals = cursor.fetchone()
    
    # Date range
    cursor.execute("SELECT MIN(date), MAX(date) FROM trades")
    first_date, last_date = cursor.fetchone()
    
    # Total commission
    cursor.execute("SELECT SUM(commission) FROM trades")
    total_commission = cursor.fetchone()[0] or 0
    
    print(f"Total Trades: {total_trades}")
    print(f"Unique Symbols: {unique_symbols}")
    print(f"Date Range: {first_date} to {last_date}")
    print()
    print(f"Total Deposits: ${deposits or 0:,.2f}")
    print(f"Total Withdrawals: ${withdrawals or 0:,.2f}")
    print(f"Net Cash Flow: ${(deposits or 0) - (withdrawals or 0):,.2f}")
    print()
    print(f"Total Commissions: ${total_commission:,.2f}")
    print()


def interactive_menu(cursor):
    """Interactive menu"""
    
    while True:
        print()
        print("=" * 80)
        print("TRADES TABLE VIEWER")
        print("=" * 80)
        print()
        print("1. Show ACH Summary")
        print("2. Show Trades by Symbol")
        print("3. Show All Symbols Summary")
        print("4. Show Monthly Activity")
        print("5. Show Overall Summary")
        print("6. Exit")
        print()
        
        choice = input("Enter choice (1-6): ").strip()
        
        if choice == '1':
            show_ach_summary(cursor)
        elif choice == '2':
            symbol = input("Enter symbol (e.g., SGOV, TQQQ): ").strip().upper()
            if symbol:
                show_symbol_trades(cursor, symbol)
        elif choice == '3':
            show_all_symbols(cursor)
        elif choice == '4':
            show_monthly_activity(cursor)
        elif choice == '5':
            show_overall_summary(cursor)
        elif choice == '6':
            print("Goodbye!")
            break
        else:
            print("Invalid choice")


def main():
    parser = argparse.ArgumentParser(description='Query trades table')
    parser.add_argument('--ach', action='store_true', help='Show ACH summary')
    parser.add_argument('--symbol', type=str, help='Show trades for specific symbol')
    parser.add_argument('--summary', action='store_true', help='Show overall summary')
    parser.add_argument('--monthly', action='store_true', help='Show monthly activity')
    parser.add_argument('--symbols', action='store_true', help='Show all symbols')
    
    args = parser.parse_args()
    
    try:
        db_path = get_database_path()
        
        if not db_path.exists():
            print(f"❌ Database not found: {db_path}")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if trades table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='trades'
        """)
        if not cursor.fetchone():
            print("⚠️  Trades table doesn't exist yet")
            print("   Run: python scripts/import_tradier_history.py --import")
            conn.close()
            return
        
        # Handle command line options
        if args.ach:
            show_ach_summary(cursor)
        elif args.symbol:
            show_symbol_trades(cursor, args.symbol.upper())
        elif args.summary:
            show_overall_summary(cursor)
        elif args.monthly:
            show_monthly_activity(cursor)
        elif args.symbols:
            show_all_symbols(cursor)
        else:
            # Interactive menu
            interactive_menu(cursor)
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
