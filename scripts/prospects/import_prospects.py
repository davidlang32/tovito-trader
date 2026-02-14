"""
Import Prospects from CSV

Bulk import prospects from a CSV file.

CSV format:
    Name,Email,Phone,Source,Notes
    John Doe,john@example.com,555-1234,Referral,Met at conference
    Jane Smith,jane@example.com,,LinkedIn,

Usage:
    python scripts/import_prospects.py prospects.csv
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
import csv
from pathlib import Path
from datetime import datetime


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def import_prospects(csv_file):
    """Import prospects from CSV file"""
    
    csv_path = Path(csv_file)
    
    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        return False
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    print("=" * 70)
    print("IMPORT PROSPECTS FROM CSV")
    print("=" * 70)
    print()
    print(f"CSV file: {csv_path}")
    print()
    
    # Read CSV file
    prospects = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Verify required columns
            required = ['Name', 'Email']
            if not all(col in reader.fieldnames for col in required):
                print(f"❌ CSV must have columns: {', '.join(required)}")
                print(f"   Found: {', '.join(reader.fieldnames)}")
                return False
            
            for row in reader:
                if row['Name'].strip() and row['Email'].strip():
                    prospects.append({
                        'name': row['Name'].strip(),
                        'email': row['Email'].strip(),
                        'phone': row.get('Phone', '').strip() or None,
                        'source': row.get('Source', '').strip() or None,
                        'notes': row.get('Notes', '').strip() or None
                    })
        
        if not prospects:
            print("❌ No valid prospects found in CSV")
            return False
        
        print(f"Found {len(prospects)} prospects:")
        for i, p in enumerate(prospects, 1):
            print(f"  {i}. {p['name']} <{p['email']}>")
        
        print()
        confirm = input(f"Import these {len(prospects)} prospects? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            print("Import cancelled.")
            return False
        
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return False
    
    # Import to database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        added = 0
        updated = 0
        errors = 0
        
        date_added = datetime.now().date().isoformat()
        
        for prospect in prospects:
            try:
                # Check if email already exists
                cursor.execute("SELECT id, name FROM prospects WHERE email = ?", (prospect['email'],))
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing
                    cursor.execute("""
                        UPDATE prospects
                        SET name = ?, phone = ?, source = ?, notes = ?, updated_at = ?
                        WHERE email = ?
                    """, (
                        prospect['name'],
                        prospect['phone'],
                        prospect['source'],
                        prospect['notes'],
                        datetime.now().isoformat(),
                        prospect['email']
                    ))
                    updated += 1
                    print(f"   ✅ Updated: {prospect['name']}")
                else:
                    # Insert new
                    cursor.execute("""
                        INSERT INTO prospects (name, email, phone, date_added, source, notes)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        prospect['name'],
                        prospect['email'],
                        prospect['phone'],
                        date_added,
                        prospect['source'],
                        prospect['notes']
                    ))
                    added += 1
                    print(f"   ✅ Added: {prospect['name']}")
                
            except sqlite3.Error as e:
                errors += 1
                print(f"   ❌ Error importing {prospect['name']}: {e}")
        
        conn.commit()
        
        # Show summary
        print()
        print("=" * 70)
        print("IMPORT COMPLETE")
        print("=" * 70)
        print(f"  Added:   {added}")
        print(f"  Updated: {updated}")
        print(f"  Errors:  {errors}")
        
        # Show total
        cursor.execute("SELECT COUNT(*) FROM prospects WHERE status = 'Active'")
        total = cursor.fetchone()[0]
        print(f"  Total active prospects: {total}")
        print()
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"\n❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/import_prospects.py prospects.csv")
        print()
        print("CSV format:")
        print("  Name,Email,Phone,Source,Notes")
        print("  John Doe,john@example.com,555-1234,Referral,Met at conference")
        print("  Jane Smith,jane@example.com,,LinkedIn,")
        sys.exit(1)
    
    try:
        success = import_prospects(sys.argv[1])
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nImport cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
