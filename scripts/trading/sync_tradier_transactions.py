"""
Tradier Transaction Sync

Fetches transaction history from Tradier API and stores in database.
Run this BEFORE daily NAV update to ensure all deposits/withdrawals are tracked.

Usage:
    python scripts/sync_tradier_transactions.py
    python scripts/sync_tradier_transactions.py --date 2026-01-21
    python scripts/sync_tradier_transactions.py --range 2026-01-01 2026-01-31
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import requests
import os
import sys
from pathlib import Path
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from src.automation.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Tradier API configuration
TRADIER_API_KEY = os.getenv('TRADIER_API_KEY')
TRADIER_ACCOUNT_ID = os.getenv('TRADIER_ACCOUNT_ID')
TRADIER_BASE_URL = os.getenv('TRADIER_BASE_URL', 'https://api.tradier.com')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'dlang32@gmail.com')


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def fetch_tradier_history(start_date, end_date=None):
    """Fetch transaction history from Tradier API"""
    
    if not TRADIER_API_KEY or not TRADIER_ACCOUNT_ID:
        raise ValueError("Tradier API credentials not configured in .env")
    
    # Format dates
    if end_date is None:
        end_date = start_date
    
    url = f"{TRADIER_BASE_URL}/v1/accounts/{TRADIER_ACCOUNT_ID}/history"
    
    headers = {
        'Authorization': f'Bearer {TRADIER_API_KEY}',
        'Accept': 'application/json'
    }
    
    params = {
        'start': start_date.strftime('%Y-%m-%d'),
        'end': end_date.strftime('%Y-%m-%d')
    }
    
    print(f"📡 Fetching Tradier transactions: {start_date} to {end_date}")
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Parse response
        if 'history' not in data or data['history'] is None:
            print("   No transactions found for this period")
            return []
        
        events = data['history'].get('event', [])
        
        # Handle single event (not in array)
        if isinstance(events, dict):
            events = [events]
        
        print(f"   Found {len(events)} transaction(s)")
        
        return events
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API Error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error parsing response: {e}")
        return None


def categorize_transaction(event):
    """Categorize transaction type"""
    
    event_type = event.get('type', '').lower()
    description = event.get('description', '').lower()
    
    # Map Tradier types to our categories
    if event_type in ['ach', 'wire'] and event.get('amount', 0) > 0:
        return 'deposit'
    elif event_type in ['ach', 'wire'] and event.get('amount', 0) < 0:
        return 'withdrawal'
    elif event_type == 'trade':
        return 'trade'
    elif event_type == 'dividend':
        return 'dividend'
    elif event_type == 'interest':
        return 'interest'
    elif event_type == 'fee':
        return 'fee'
    elif event_type == 'journal':
        return 'transfer'
    else:
        return event_type


def store_transactions(conn, transactions, sync_date):
    """Store transactions in database"""
    
    cursor = conn.cursor()
    
    new_count = 0
    duplicate_count = 0
    deposits = []
    withdrawals = []
    
    for trans in transactions:
        # Extract data
        trans_date = trans.get('date', '').split('T')[0]  # Get date part only
        trans_type = categorize_transaction(trans)
        amount = float(trans.get('amount', 0))
        description = trans.get('description', '')
        trans_id = trans.get('id') or f"{trans_date}_{description}_{amount}"
        timestamp = trans.get('date')
        
        try:
            # Try to insert
            cursor.execute("""
                INSERT INTO tradier_transactions (
                    date, transaction_type, amount, description,
                    tradier_transaction_id, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (trans_date, trans_type, amount, description, trans_id, timestamp))
            
            new_count += 1
            
            # Track deposits and withdrawals
            if trans_type == 'deposit':
                deposits.append({
                    'date': trans_date,
                    'amount': amount,
                    'trans_id': trans_id,
                    'description': description
                })
            elif trans_type == 'withdrawal':
                withdrawals.append({
                    'date': trans_date,
                    'amount': amount,
                    'trans_id': trans_id,
                    'description': description
                })
            
        except sqlite3.IntegrityError:
            # Duplicate transaction ID
            duplicate_count += 1
    
    conn.commit()
    
    # Update sync status
    cursor.execute("""
        INSERT OR REPLACE INTO transaction_sync_status (
            sync_date, last_sync_time, transactions_found,
            deposits_count, withdrawals_count, status
        ) VALUES (?, ?, ?, ?, ?, 'synced')
    """, (
        sync_date,
        datetime.now(),
        len(transactions),
        len(deposits),
        len(withdrawals)
    ))
    
    conn.commit()
    
    return {
        'new': new_count,
        'duplicates': duplicate_count,
        'deposits': deposits,
        'withdrawals': withdrawals
    }


def create_pending_contributions(conn, deposits):
    """Create pending contribution records for unallocated deposits"""
    
    cursor = conn.cursor()
    pending_created = 0
    
    for deposit in deposits:
        # Check if already exists
        cursor.execute("""
            SELECT id FROM pending_contributions
            WHERE tradier_transaction_id = ?
        """, (deposit['trans_id'],))
        
        if cursor.fetchone():
            continue  # Already tracked
        
        # Create pending contribution
        cursor.execute("""
            INSERT INTO pending_contributions (
                transaction_date, amount, tradier_transaction_id,
                status, notes
            ) VALUES (?, ?, ?, 'pending', ?)
        """, (
            deposit['date'],
            deposit['amount'],
            deposit['trans_id'],
            f"Auto-detected deposit: {deposit['description']}"
        ))
        
        pending_created += 1
    
    conn.commit()
    
    return pending_created


def send_admin_alert(deposits, withdrawals, sync_date):
    """Send email alert to admin about new deposits/withdrawals"""
    
    if not EMAIL_AVAILABLE or not ADMIN_EMAIL:
        return
    
    if not deposits and not withdrawals:
        return  # Nothing to report
    
    subject = f"⚠️ UNALLOCATED TRANSACTIONS DETECTED - {sync_date}"
    
    message = f"""Hi David,

New deposits and/or withdrawals detected in the Tradier account that need attention.

SYNC DATE: {sync_date}
{'='*60}

"""
    
    if deposits:
        message += f"""
DEPOSITS DETECTED ({len(deposits)}):
{'-'*60}
"""
        for dep in deposits:
            message += f"""
Date: {dep['date']}
Amount: ${dep['amount']:,.2f}
Description: {dep['description']}
Transaction ID: {dep['trans_id']}
"""
    
    if withdrawals:
        message += f"""
WITHDRAWALS DETECTED ({len(withdrawals)}):
{'-'*60}
"""
        for wd in withdrawals:
            message += f"""
Date: {wd['date']}
Amount: ${wd['amount']:,.2f}
Description: {wd['description']}
Transaction ID: {wd['trans_id']}
"""
    
    message += f"""
{'='*60}

ACTION REQUIRED:
Assign these transactions to investors by running:

  python scripts/assign_pending_contribution.py

Or they will be flagged during the next NAV update.

IMPORTANT: The NAV calculation will EXCLUDE unallocated deposits
to ensure accurate share pricing.

---
Tovito Trader Automated System
Sent: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    try:
        send_email(
            to_email=ADMIN_EMAIL,
            subject=subject,
            message=message
        )
        print(f"✅ Admin alert sent to {ADMIN_EMAIL}")
        return True
    except Exception as e:
        print(f"⚠️  Could not send admin alert: {e}")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync Tradier transactions')
    parser.add_argument('--date', help='Specific date (YYYY-MM-DD)')
    parser.add_argument('--range', nargs=2, help='Date range: start end')
    parser.add_argument('--yesterday', action='store_true', help='Sync yesterday only')
    
    args = parser.parse_args()
    
    # Determine date range
    if args.date:
        start_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        end_date = start_date
    elif args.range:
        start_date = datetime.strptime(args.range[0], '%Y-%m-%d').date()
        end_date = datetime.strptime(args.range[1], '%Y-%m-%d').date()
    elif args.yesterday:
        start_date = date.today() - timedelta(days=1)
        end_date = start_date
    else:
        # Default: yesterday (for daily automation)
        start_date = date.today() - timedelta(days=1)
        end_date = start_date
    
    print("=" * 70)
    print("TRADIER TRANSACTION SYNC")
    print("=" * 70)
    print()
    print(f"Date Range: {start_date} to {end_date}")
    print()
    
    # Fetch transactions
    transactions = fetch_tradier_history(start_date, end_date)
    
    if transactions is None:
        print("\n❌ Failed to fetch transactions from Tradier")
        return
    
    print()
    
    # Store in database
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("Run migration first: python scripts/migrate_enhanced_nav_system.py")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        
        if not transactions:
            # No transactions - still record sync status
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO transaction_sync_status (
                    sync_date, last_sync_time, transactions_found,
                    deposits_count, withdrawals_count, status
                ) VALUES (?, ?, 0, 0, 0, 'synced')
            """, (start_date, datetime.now()))
            conn.commit()
            
            print("✅ Sync completed - No transactions found")
            conn.close()
            return
        
        # Store transactions
        result = store_transactions(conn, transactions, start_date)
        
        print("=" * 70)
        print("SYNC RESULTS")
        print("=" * 70)
        print()
        print(f"New transactions:   {result['new']}")
        print(f"Duplicates skipped: {result['duplicates']}")
        print(f"Deposits found:     {len(result['deposits'])}")
        print(f"Withdrawals found:  {len(result['withdrawals'])}")
        print()
        
        # Create pending contributions
        if result['deposits']:
            pending_count = create_pending_contributions(conn, result['deposits'])
            print(f"Pending contributions created: {pending_count}")
            print()
        
        # Send admin alert if new deposits/withdrawals
        if result['deposits'] or result['withdrawals']:
            print("📧 Sending admin alert...")
            send_admin_alert(result['deposits'], result['withdrawals'], start_date)
            print()
        
        print("✅ Transaction sync completed successfully!")
        print()
        
        # Show pending contributions
        if result['deposits']:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM pending_contributions
                WHERE status = 'pending'
            """)
            pending = cursor.fetchone()[0]
            
            if pending > 0:
                print("=" * 70)
                print(f"⚠️  WARNING: {pending} pending contribution(s) need assignment")
                print("=" * 70)
                print()
                print("Run: python scripts/assign_pending_contribution.py")
                print()
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"\n❌ Database error: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
