"""
List Investors - Quick Reference

Shows investor IDs and names for easy selection
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
from pathlib import Path


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def main():
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT investor_id, name, status
            FROM investors
            ORDER BY investor_id
        """)
        
        investors = cursor.fetchall()
        
        print("=" * 70)
        print("INVESTOR QUICK REFERENCE")
        print("=" * 70)
        print()
        
        active = []
        inactive = []
        
        for inv_id, name, status in investors:
            if status == 'Active':
                active.append((inv_id, name))
            else:
                inactive.append((inv_id, name))
        
        if active:
            print("ACTIVE INVESTORS:")
            print("-" * 70)
            for inv_id, name in active:
                # Extract first name for easy reference
                first_name = name.split()[0]
                print(f"  {inv_id}  {name:30s}  ({first_name})")
            print()
        
        if inactive:
            print("INACTIVE INVESTORS:")
            print("-" * 70)
            for inv_id, name in inactive:
                first_name = name.split()[0]
                print(f"  {inv_id}  {name:30s}  ({first_name})")
            print()
        
        print("=" * 70)
        print()
        print("USAGE EXAMPLES:")
        print()
        print("# Single investor (David):")
        print(f"python scripts\\generate_monthly_report.py --month 1 --year 2026 --investor {active[0][0]} --email")
        print()
        print("# Multiple investors (Ken, Beth, David):")
        if len(active) >= 3:
            ken = next((id for id, name in active if 'Kenneth' in name or 'Ken' in name), None)
            beth = next((id for id, name in active if 'Elizabeth' in name or 'Beth' in name), None)
            david = next((id for id, name in active if 'David' in name), None)
            
            investor_list = []
            if david: investor_list.append(david)
            if beth: investor_list.append(beth)
            if ken: investor_list.append(ken)
            
            if investor_list:
                print(f"python scripts\\generate_monthly_report.py --month 1 --year 2026 --investors {' '.join(investor_list)} --email")
        print()
        print("# All investors:")
        print("python scripts\\generate_monthly_report.py --month 1 --year 2026 --email")
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
