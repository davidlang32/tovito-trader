"""
Database Schema Inspector

Shows all tables and columns in your database.

Usage:
    python scripts/check_database_schema.py
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
from pathlib import Path


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def main():
    print("=" * 70)
    print("DATABASE SCHEMA INSPECTOR")
    print("=" * 70)
    print()
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """)
        
        tables = cursor.fetchall()
        
        print(f"📊 Found {len(tables)} table(s):")
        print()
        
        for (table_name,) in tables:
            print(f"📁 Table: {table_name}")
            print("-" * 70)
            
            # Get columns for this table
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            print("   Columns:")
            for col in columns:
                col_id, col_name, col_type, not_null, default, pk = col
                pk_marker = " [PRIMARY KEY]" if pk else ""
                print(f"   - {col_name} ({col_type}){pk_marker}")
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"   Rows: {count}")
            
            print()
        
        # Check for NAV-related tables specifically
        print("=" * 70)
        print("NAV DATA SEARCH:")
        print("=" * 70)
        print()
        
        nav_tables = [t[0] for t in tables if 'nav' in t[0].lower() or 'daily' in t[0].lower()]
        
        if nav_tables:
            print(f"Found NAV-related table(s): {', '.join(nav_tables)}")
            print()
            
            for table in nav_tables:
                print(f"Sample data from {table}:")
                cursor.execute(f"SELECT * FROM {table} ORDER BY ROWID DESC LIMIT 3")
                rows = cursor.fetchall()
                
                # Get column names
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [col[1] for col in cursor.fetchall()]
                
                print(f"   Columns: {', '.join(columns)}")
                print()
                
                for row in rows:
                    print(f"   {dict(zip(columns, row))}")
                print()
        else:
            print("⚠️  No NAV-related tables found!")
            print()
            print("Looking for any date-related columns in all tables...")
            print()
            
            for (table_name,) in tables:
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                
                date_cols = [col[1] for col in columns if 'date' in col[1].lower()]
                
                if date_cols:
                    print(f"   {table_name}: {', '.join(date_cols)}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
