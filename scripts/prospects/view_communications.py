"""
View Communications - See email history for prospects and investors

Shows complete communication history with filtering options.

Usage:
    python scripts/view_communications.py
    python scripts/view_communications.py --prospects
    python scripts/view_communications.py --investors
    python scripts/view_communications.py --days 30
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def view_prospect_communications(cursor, days=None):
    """View prospect communications"""
    
    print("=" * 90)
    print("PROSPECT COMMUNICATIONS")
    print("=" * 90)
    print()
    
    # Build query
    query = """
        SELECT 
            pc.id,
            pc.date,
            p.name,
            p.email,
            pc.communication_type,
            pc.report_period,
            pc.status,
            pc.error_message
        FROM prospect_communications pc
        JOIN prospects p ON pc.prospect_id = p.id
    """
    
    params = []
    if days:
        cutoff_date = (datetime.now() - timedelta(days=days)).date().isoformat()
        query += " WHERE pc.date >= ?"
        params.append(cutoff_date)
    
    query += " ORDER BY pc.date DESC, p.name"
    
    cursor.execute(query, params)
    comms = cursor.fetchall()
    
    if not comms:
        print("No prospect communications found.")
        return
    
    for comm_id, date, name, email, comm_type, period, status, error in comms:
        status_icon = "✅" if status == 'Sent' else "❌"
        print(f"{status_icon} {date} - {name} <{email}>")
        print(f"   Type: {comm_type}")
        if period:
            print(f"   Period: {period}")
        print(f"   Status: {status}")
        if error:
            print(f"   Error: {error}")
        print()
    
    print(f"Total: {len(comms)} communications")
    print()


def view_investor_communications(cursor, days=None):
    """View investor communications"""
    
    print("=" * 90)
    print("INVESTOR COMMUNICATIONS")
    print("=" * 90)
    print()
    
    # Build query
    query = """
        SELECT 
            ic.id,
            ic.date,
            i.investor_id,
            i.name,
            ic.communication_type,
            ic.report_period,
            ic.status,
            ic.error_message
        FROM investor_communications ic
        JOIN investors i ON ic.investor_id = i.investor_id
    """
    
    params = []
    if days:
        cutoff_date = (datetime.now() - timedelta(days=days)).date().isoformat()
        query += " WHERE ic.date >= ?"
        params.append(cutoff_date)
    
    query += " ORDER BY ic.date DESC, i.name"
    
    cursor.execute(query, params)
    comms = cursor.fetchall()
    
    if not comms:
        print("No investor communications found.")
        return
    
    for comm_id, date, inv_id, name, comm_type, period, status, error in comms:
        status_icon = "✅" if status == 'Sent' else ("🧪" if status == 'Test' else "❌")
        print(f"{status_icon} {date} - {name} ({inv_id})")
        print(f"   Type: {comm_type}")
        if period:
            print(f"   Period: {period}")
        print(f"   Status: {status}")
        if error:
            print(f"   Note: {error}")
        print()
    
    print(f"Total: {len(comms)} communications")
    print()


def view_summary(cursor, days=None):
    """View summary of all communications"""
    
    print("=" * 90)
    print("COMMUNICATIONS SUMMARY")
    print("=" * 90)
    print()
    
    # Get prospect stats
    query = "SELECT COUNT(*), MAX(date) FROM prospect_communications"
    params = []
    if days:
        cutoff_date = (datetime.now() - timedelta(days=days)).date().isoformat()
        query += " WHERE date >= ?"
        params.append(cutoff_date)
    
    cursor.execute(query, params)
    prospect_count, prospect_last = cursor.fetchone()
    
    # Get investor stats
    query = "SELECT COUNT(*), MAX(date) FROM investor_communications"
    params = []
    if days:
        query += " WHERE date >= ?"
        params.append(cutoff_date)
    
    cursor.execute(query, params)
    investor_count, investor_last = cursor.fetchone()
    
    period_str = f"Last {days} days" if days else "All time"
    
    print(f"Period: {period_str}")
    print()
    print(f"Prospect Communications:  {prospect_count}")
    if prospect_last:
        print(f"  Last sent: {prospect_last}")
    print()
    print(f"Investor Communications:  {investor_count}")
    if investor_last:
        print(f"  Last sent: {investor_last}")
    print()
    
    # Recent activity
    if not days or days >= 7:
        print("Recent Activity (Last 7 days):")
        print()
        
        # Prospect activity
        cutoff = (datetime.now() - timedelta(days=7)).date().isoformat()
        cursor.execute("""
            SELECT pc.date, p.name, pc.communication_type, pc.status
            FROM prospect_communications pc
            JOIN prospects p ON pc.prospect_id = p.id
            WHERE pc.date >= ?
            ORDER BY pc.date DESC
            LIMIT 5
        """, (cutoff,))
        
        recent_prospects = cursor.fetchall()
        if recent_prospects:
            print("Prospects:")
            for date, name, comm_type, status in recent_prospects:
                status_icon = "✅" if status == 'Sent' else "❌"
                print(f"  {status_icon} {date} - {name} ({comm_type})")
            print()
        
        # Investor activity
        cursor.execute("""
            SELECT ic.date, i.name, ic.communication_type, ic.status
            FROM investor_communications ic
            JOIN investors i ON ic.investor_id = i.investor_id
            WHERE ic.date >= ?
            ORDER BY ic.date DESC
            LIMIT 5
        """, (cutoff,))
        
        recent_investors = cursor.fetchall()
        if recent_investors:
            print("Investors:")
            for date, name, comm_type, status in recent_investors:
                status_icon = "✅" if status == 'Sent' else ("🧪" if status == 'Test' else "❌")
                print(f"  {status_icon} {date} - {name} ({comm_type})")
            print()
    
    print("=" * 90)
    print()


def main():
    parser = argparse.ArgumentParser(description='View communication history')
    parser.add_argument('--prospects', action='store_true', help='Show prospect communications only')
    parser.add_argument('--investors', action='store_true', help='Show investor communications only')
    parser.add_argument('--days', type=int, help='Show communications from last N days')
    
    args = parser.parse_args()
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('prospect_communications', 'investor_communications')
        """)
        tables = cursor.fetchall()
        
        if len(tables) < 2:
            print("❌ Communication tracking tables not found.")
            print("Run migration first: python scripts/migrate_add_communications_tracking.py")
            return False
        
        if args.prospects:
            view_prospect_communications(cursor, args.days)
        elif args.investors:
            view_investor_communications(cursor, args.days)
        else:
            view_summary(cursor, args.days)
        
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


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
