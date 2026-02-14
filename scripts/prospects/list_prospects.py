"""
List Prospects - View all prospects in database

Shows all active prospects with contact information and communication history.
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
from pathlib import Path
from datetime import datetime


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def list_prospects(show_inactive=False):
    """List all prospects"""
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get prospects
        if show_inactive:
            cursor.execute("""
                SELECT id, name, email, phone, date_added, status, source, last_contact_date
                FROM prospects
                ORDER BY status, name
            """)
        else:
            cursor.execute("""
                SELECT id, name, email, phone, date_added, status, source, last_contact_date
                FROM prospects
                WHERE status = 'Active'
                ORDER BY name
            """)
        
        prospects = cursor.fetchall()
        
        if not prospects:
            print("No prospects found.")
            return True
        
        print("=" * 90)
        print("PROSPECTS DATABASE")
        print("=" * 90)
        print()
        
        for prospect_id, name, email, phone, date_added, status, source, last_contact in prospects:
            print(f"📧 {name}")
            print(f"   Email: {email}")
            if phone:
                print(f"   Phone: {phone}")
            print(f"   Added: {date_added}")
            if source:
                print(f"   Source: {source}")
            print(f"   Status: {status}")
            
            # Get communication count
            cursor.execute("""
                SELECT COUNT(*), MAX(date)
                FROM prospect_communications
                WHERE prospect_id = ?
            """, (prospect_id,))
            comm_count, last_comm = cursor.fetchone()
            
            if comm_count > 0:
                print(f"   Communications: {comm_count} (last: {last_comm})")
            else:
                print(f"   Communications: None")
            
            print()
        
        print("=" * 90)
        print(f"Total prospects: {len(prospects)}")
        
        # Count by status
        cursor.execute("SELECT status, COUNT(*) FROM prospects GROUP BY status")
        status_counts = cursor.fetchall()
        for status, count in status_counts:
            print(f"  {status}: {count}")
        
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


if __name__ == "__main__":
    try:
        show_all = '--all' in sys.argv
        success = list_prospects(show_inactive=show_all)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
