"""
View Pending Withdrawal Requests

Shows all pending withdrawal requests awaiting approval.

Usage:
    python scripts/view_pending_withdrawals.py
    python scripts/view_pending_withdrawals.py --all  (shows all statuses)
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
import argparse
from pathlib import Path
from datetime import datetime


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def view_pending_requests(show_all=False):
    """View withdrawal requests"""
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get requests
        if show_all:
            query = """
                SELECT 
                    wr.id,
                    wr.request_date,
                    i.name,
                    wr.requested_amount,
                    wr.request_method,
                    wr.status,
                    wr.notes,
                    wr.processed_date,
                    wr.net_proceeds
                FROM withdrawal_requests wr
                JOIN investors i ON wr.investor_id = i.investor_id
                ORDER BY 
                    CASE wr.status
                        WHEN 'Pending' THEN 1
                        WHEN 'Approved' THEN 2
                        WHEN 'Processed' THEN 3
                        WHEN 'Rejected' THEN 4
                    END,
                    wr.request_date DESC
            """
        else:
            query = """
                SELECT 
                    wr.id,
                    wr.request_date,
                    i.name,
                    wr.requested_amount,
                    wr.request_method,
                    wr.status,
                    wr.notes
                FROM withdrawal_requests wr
                JOIN investors i ON wr.investor_id = i.investor_id
                WHERE wr.status IN ('Pending', 'Approved')
                ORDER BY wr.request_date DESC
            """
        
        cursor.execute(query)
        requests = cursor.fetchall()
        
        if not requests:
            if show_all:
                print("No withdrawal requests found.")
            else:
                print("No pending withdrawal requests.")
                print()
                print("💡 Use --all to see all requests (including processed/rejected)")
            return True
        
        print("=" * 90)
        if show_all:
            print("ALL WITHDRAWAL REQUESTS")
        else:
            print("PENDING WITHDRAWAL REQUESTS")
        print("=" * 90)
        print()
        
        pending_count = 0
        approved_count = 0
        
        for request in requests:
            if show_all:
                req_id, date, name, amount, method, status, notes, proc_date, net_proceeds = request
            else:
                req_id, date, name, amount, method, status, notes = request
                proc_date = None
                net_proceeds = None
            
            # Status icon
            if status == 'Pending':
                icon = "⏳"
                pending_count += 1
            elif status == 'Approved':
                icon = "✅"
                approved_count += 1
            elif status == 'Processed':
                icon = "💰"
            elif status == 'Rejected':
                icon = "❌"
            else:
                icon = "❓"
            
            print(f"{icon} Request #{req_id} - {status}")
            print(f"   Investor: {name}")
            print(f"   Amount: ${amount:,.2f}")
            print(f"   Date: {date}")
            print(f"   Method: {method}")
            if notes:
                print(f"   Notes: {notes}")
            if proc_date:
                print(f"   Processed: {proc_date}")
            if net_proceeds:
                print(f"   Net Proceeds: ${net_proceeds:,.2f}")
            print()
        
        print("=" * 90)
        print(f"Total requests: {len(requests)}")
        if not show_all:
            print(f"  Pending: {pending_count}")
            print(f"  Approved: {approved_count}")
        print()
        
        if pending_count > 0:
            print("⚠️  Action required: Review and approve/reject pending requests")
            print("   Use: python scripts/process_withdrawal_enhanced.py")
            print()
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description='View withdrawal requests')
    parser.add_argument('--all', action='store_true', help='Show all requests (not just pending)')
    
    args = parser.parse_args()
    
    try:
        success = view_pending_requests(show_all=args.all)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
