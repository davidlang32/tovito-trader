"""
Import Complete Tradier History to Trades Table (FIXED)

Handles:
- Duplicate transaction IDs
- Empty transaction IDs
- Proper error handling

Usage:
    python scripts/import_tradier_history.py --check      # Preview what will be imported
    python scripts/import_tradier_history.py --import     # Actually import
"""

import os
import sqlite3
import requests
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def create_trades_table(cursor):
    """Create trades table and views if they don't exist"""
    
    schema = """
    CREATE TABLE IF NOT EXISTS trades (
        trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
        
        -- Tradier transaction details
        tradier_transaction_id TEXT,
        date DATE NOT NULL,
        type TEXT NOT NULL,
        status TEXT,
        
        -- Financial details
        amount REAL NOT NULL,
        commission REAL DEFAULT 0,
        
        -- Security details
        symbol TEXT,
        quantity REAL,
        price REAL,
        
        -- Option details
        option_type TEXT,
        strike REAL,
        expiration_date DATE,
        
        -- Trade classification
        trade_type TEXT,
        
        -- Description and notes
        description TEXT,
        notes TEXT,
        
        -- Categorization
        category TEXT,
        subcategory TEXT,
        
        -- Metadata
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        UNIQUE(tradier_transaction_id)
    );
    
    CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date);
    CREATE INDEX IF NOT EXISTS idx_trades_type ON trades(type);
    CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
    CREATE INDEX IF NOT EXISTS idx_trades_category ON trades(category);
    
    -- View: ACH Summary
    CREATE VIEW IF NOT EXISTS ach_summary AS
    SELECT 
        date,
        SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total_deposits,
        SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_withdrawals,
        SUM(amount) as net_ach,
        COUNT(*) as ach_count
    FROM trades
    WHERE type IN ('ach', 'wire', 'journal')
    GROUP BY date
    ORDER BY date;
    """
    
    cursor.executescript(schema)


def get_tradier_history(start_date=None, end_date=None):
    """Pull complete transaction history from Tradier API"""
    
    load_dotenv()
    
    api_key = os.getenv('TRADIER_API_KEY')
    account_id = os.getenv('TRADIER_ACCOUNT_ID')
    
    if not api_key or not account_id:
        raise ValueError("TRADIER_API_KEY and TRADIER_ACCOUNT_ID must be set in .env")
    
    url = f"https://api.tradier.com/v1/accounts/{account_id}/history"
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json'
    }
    
    params = {'limit': 10000}
    
    if start_date:
        params['start'] = start_date
    if end_date:
        params['end'] = end_date
    
    print("📡 Fetching transaction history from Tradier...")
    print(f"   Account: {account_id}")
    if start_date:
        print(f"   Start: {start_date}")
    if end_date:
        print(f"   End: {end_date}")
    print()
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        raise Exception(f"Tradier API error: {response.status_code} - {response.text}")
    
    data = response.json()
    
    transactions = []
    
    if 'history' in data and 'event' in data['history']:
        events = data['history']['event']
        
        if not isinstance(events, list):
            events = [events]
        
        print(f"✅ Found {len(events)} transactions in Tradier")
        print()
        
        # Track seen IDs to handle duplicates
        seen_ids = set()
        
        for idx, event in enumerate(events):
            # Get transaction ID or generate unique one if missing
            trans_id = str(event.get('id', ''))
            
            # If ID is empty or duplicate in batch, generate unique one
            if not trans_id or trans_id in seen_ids:
                trans_id = f"GENERATED_{event.get('date', 'unknown')}_{idx}_{event.get('type', 'unknown')}"
            
            seen_ids.add(trans_id)
            
            trans = {
                'tradier_transaction_id': trans_id,
                'date': event.get('date'),
                'type': event.get('type', ''),
                'status': event.get('status', 'completed'),
                'amount': float(event.get('amount', 0)),
                'commission': float(event.get('commission', 0)),
                'symbol': event.get('symbol', ''),
                'quantity': float(event.get('quantity', 0)) if event.get('quantity') else None,
                'price': float(event.get('price', 0)) if event.get('price') else None,
                'option_type': event.get('option_type', ''),
                'strike': float(event.get('strike', 0)) if event.get('strike') else None,
                'expiration_date': event.get('expiration_date', ''),
                'trade_type': event.get('trade_type', ''),
                'description': event.get('description', ''),
                'notes': ''
            }
            
            # Categorize
            trans['category'], trans['subcategory'] = categorize_transaction(trans)
            
            transactions.append(trans)
    else:
        print("⚠️  No transactions found in Tradier")
    
    return transactions


def categorize_transaction(trans):
    """Categorize transaction for analysis"""
    
    trans_type = trans['type'].lower()
    description = trans['description'].lower()
    
    # Trade
    if trans_type in ['trade', 'option']:
        category = 'Trade'
        if trans['option_type']:
            subcategory = f"Option {trans['option_type'].title()}"
        elif 'buy' in description or trans['amount'] < 0:
            subcategory = 'Stock Buy'
        elif 'sell' in description or trans['amount'] > 0:
            subcategory = 'Stock Sell'
        else:
            subcategory = 'Trade'
    
    # Transfer (ACH, wire, journal)
    elif trans_type in ['ach', 'wire', 'journal']:
        category = 'Transfer'
        if trans['amount'] > 0:
            subcategory = 'Deposit'
        else:
            subcategory = 'Withdrawal'
    
    # Income
    elif 'dividend' in trans_type:
        category = 'Income'
        subcategory = 'Dividend'
    elif 'interest' in trans_type:
        category = 'Income'
        subcategory = 'Interest'
    
    # Fees
    elif 'fee' in trans_type or 'commission' in trans_type:
        category = 'Fee'
        subcategory = trans_type.title()
    
    # Other
    else:
        category = 'Other'
        subcategory = trans_type.title()
    
    return category, subcategory


def get_existing_trades(cursor):
    """Get existing trades from database"""
    cursor.execute("SELECT tradier_transaction_id FROM trades")
    return set(row[0] for row in cursor.fetchall())


def import_transactions(cursor, transactions, existing_ids):
    """Import new transactions to database"""
    
    imported = 0
    skipped = 0
    errors = []
    
    for trans in transactions:
        # Skip if already exists
        if trans['tradier_transaction_id'] in existing_ids:
            skipped += 1
            continue
        
        try:
            cursor.execute("""
                INSERT INTO trades (
                    tradier_transaction_id, date, type, status, amount, commission,
                    symbol, quantity, price, option_type, strike, expiration_date,
                    trade_type, description, notes, category, subcategory
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trans['tradier_transaction_id'],
                trans['date'],
                trans['type'],
                trans['status'],
                trans['amount'],
                trans['commission'],
                trans['symbol'],
                trans['quantity'],
                trans['price'],
                trans['option_type'],
                trans['strike'],
                trans['expiration_date'],
                trans['trade_type'],
                trans['description'],
                trans['notes'],
                trans['category'],
                trans['subcategory']
            ))
            
            imported += 1
            
        except sqlite3.IntegrityError as e:
            # This transaction already exists or has duplicate ID
            skipped += 1
            errors.append(f"Skipped duplicate: {trans['date']} {trans['type']} ${trans['amount']:.2f}")
    
    if errors:
        print()
        print("⚠️  Some transactions were skipped due to duplicates:")
        for err in errors[:5]:  # Show first 5
            print(f"   {err}")
        if len(errors) > 5:
            print(f"   ... and {len(errors) - 5} more")
        print()
    
    return imported, skipped


def display_summary(transactions):
    """Display summary of transactions"""
    
    if not transactions:
        return
    
    print("=" * 80)
    print("TRANSACTION SUMMARY")
    print("=" * 80)
    print()
    
    # By category
    categories = {}
    for trans in transactions:
        cat = trans['category']
        categories[cat] = categories.get(cat, 0) + 1
    
    print("By Category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count} transactions")
    print()
    
    # By type
    types = {}
    for trans in transactions:
        t = trans['type']
        types[t] = types.get(t, 0) + 1
    
    print("By Type:")
    for t, count in sorted(types.items()):
        print(f"  {t}: {count} transactions")
    print()
    
    # ACH summary
    ach_deposits = sum(t['amount'] for t in transactions if t['type'] in ['ach', 'wire'] and t['amount'] > 0)
    ach_withdrawals = sum(abs(t['amount']) for t in transactions if t['type'] in ['ach', 'wire'] and t['amount'] < 0)
    
    print("ACH Summary:")
    print(f"  Deposits: ${ach_deposits:,.2f}")
    print(f"  Withdrawals: ${ach_withdrawals:,.2f}")
    print(f"  Net: ${ach_deposits - ach_withdrawals:,.2f}")
    print()
    
    # Symbols
    symbols = set(t['symbol'] for t in transactions if t['symbol'])
    if symbols:
        print(f"Symbols Traded: {len(symbols)}")
        print(f"  {', '.join(sorted(symbols)[:10])}")
        if len(symbols) > 10:
            print(f"  ... and {len(symbols) - 10} more")
        print()
    
    # Date range
    dates = [t['date'] for t in transactions if t['date']]
    if dates:
        print(f"Date Range: {min(dates)} to {max(dates)}")
        print()


def main():
    parser = argparse.ArgumentParser(description='Import Tradier history to trades table')
    parser.add_argument('--check', action='store_true', help='Preview what will be imported')
    parser.add_argument('--import', dest='do_import', action='store_true', help='Actually import')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    if not args.check and not args.do_import:
        print("❌ Must specify --check or --import")
        return
    
    try:
        db_path = get_database_path()
        
        if not db_path.exists():
            print(f"❌ Database not found: {db_path}")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create trades table if needed
        print("📊 Setting up trades table...")
        create_trades_table(cursor)
        conn.commit()
        print("✅ Trades table ready")
        print()
        
        # Get existing trades
        existing_ids = get_existing_trades(cursor)
        if existing_ids:
            print(f"ℹ️  Database already has {len(existing_ids)} trades")
            print()
        
        # Get Tradier history
        transactions = get_tradier_history(args.start_date, args.end_date)
        
        if not transactions:
            print("⚠️  No transactions to import")
            conn.close()
            return
        
        # Display summary
        display_summary(transactions)
        
        # Check mode - show what would be imported
        if args.check:
            new_trans = [t for t in transactions if t['tradier_transaction_id'] not in existing_ids]
            
            print("=" * 80)
            print("IMPORT PREVIEW")
            print("=" * 80)
            print(f"Total in Tradier: {len(transactions)}")
            print(f"Already in database: {len(existing_ids)}")
            print(f"New to import: {len(new_trans)}")
            print()
            
            if new_trans:
                print("Sample of new transactions (first 10):")
                print("-" * 80)
                for trans in new_trans[:10]:
                    print(f"  {trans['date']}: {trans['type']:10} {trans['category']:10} ${trans['amount']:>10,.2f} {trans['symbol']}")
                if len(new_trans) > 10:
                    print(f"  ... and {len(new_trans) - 10} more")
                print()
                print("💡 To import these transactions, run:")
                print("   python scripts/import_tradier_history.py --import")
            else:
                print("✅ No new transactions to import - database is up to date!")
        
        # Import mode
        elif args.do_import:
            new_trans = [t for t in transactions if t['tradier_transaction_id'] not in existing_ids]
            
            if not new_trans:
                print("✅ No new transactions to import - database is up to date!")
                conn.close()
                return
            
            print("=" * 80)
            print(f"IMPORTING {len(new_trans)} NEW TRANSACTIONS")
            print("=" * 80)
            print()
            
            confirm = input(f"Import {len(new_trans)} transactions? (yes/no): ").strip().lower()
            
            if confirm in ['yes', 'y']:
                imported, skipped = import_transactions(cursor, new_trans, existing_ids)
                conn.commit()
                
                print()
                print("=" * 80)
                print("✅ IMPORT COMPLETE!")
                print("=" * 80)
                print(f"Imported: {imported} transactions")
                if skipped > 0:
                    print(f"Skipped (duplicates): {skipped} transactions")
                print()
                
                # Show updated totals
                cursor.execute("SELECT COUNT(*) FROM trades")
                total = cursor.fetchone()[0]
                print(f"Total trades in database: {total}")
                print()
            else:
                print("Import cancelled")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
