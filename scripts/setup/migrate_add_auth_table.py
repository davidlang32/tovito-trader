#!/usr/bin/env python3
"""
Migration: Add Auth Table
==========================

Creates a separate authentication table for secure password storage
and email verification flow.

Usage:
    python migrate_add_auth_table.py

Tables Created:
    - investor_auth: Password hashes, verification tokens, login tracking
"""

import sqlite3
from pathlib import Path
from datetime import datetime

# Database path - find relative to this script or use project root
SCRIPT_DIR = Path(__file__).parent
if (SCRIPT_DIR / 'data' / 'tovito.db').exists():
    DB_PATH = SCRIPT_DIR / 'data' / 'tovito.db'
elif (Path.cwd() / 'data' / 'tovito.db').exists():
    DB_PATH = Path.cwd() / 'data' / 'tovito.db'
else:
    # Default to current working directory
    DB_PATH = Path('data') / 'tovito.db'

MIGRATION_SQL = """
-- ============================================================
-- INVESTOR AUTHENTICATION TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS investor_auth (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    investor_id TEXT NOT NULL UNIQUE,
    
    -- Password (nullable until first login)
    password_hash TEXT,
    
    -- Email verification
    email_verified INTEGER DEFAULT 0,
    verification_token TEXT,
    verification_token_expires TIMESTAMP,
    
    -- Password reset
    reset_token TEXT,
    reset_token_expires TIMESTAMP,
    
    -- Login tracking
    last_login TIMESTAMP,
    failed_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (investor_id) REFERENCES investors(investor_id)
);

CREATE INDEX IF NOT EXISTS idx_investor_auth_investor ON investor_auth(investor_id);
CREATE INDEX IF NOT EXISTS idx_investor_auth_verification ON investor_auth(verification_token);
CREATE INDEX IF NOT EXISTS idx_investor_auth_reset ON investor_auth(reset_token);
"""


def run_migration():
    """Run the migration"""
    print("\n" + "="*60)
    print(" MIGRATION: Add Auth Table")
    print("="*60 + "\n")
    
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        return False
    
    print(f"📁 Database: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='investor_auth'
        """)
        
        if cursor.fetchone():
            print("⏭️  Table 'investor_auth' already exists")
            
            # Show current state
            cursor.execute("SELECT COUNT(*) FROM investor_auth")
            count = cursor.fetchone()[0]
            print(f"   Current records: {count}")
            
            cursor.execute("""
                SELECT ia.investor_id, i.name, ia.email_verified, ia.last_login
                FROM investor_auth ia
                JOIN investors i ON ia.investor_id = i.investor_id
            """)
            for row in cursor.fetchall():
                verified = "✅" if row[2] else "❌"
                last_login = row[3] or "Never"
                print(f"   • {row[1]}: verified={verified}, last_login={last_login}")
            
            return True
        
        # Run migration
        print("🔨 Creating investor_auth table...")
        cursor.executescript(MIGRATION_SQL)
        conn.commit()
        print("✅ Table created successfully")
        
        # Create auth records for existing investors
        print("\n📝 Creating auth records for existing investors...")
        cursor.execute("""
            SELECT investor_id, name, email
            FROM investors
            WHERE status = 'Active'
        """)
        investors = cursor.fetchall()
        
        for investor_id, name, email in investors:
            cursor.execute("""
                INSERT OR IGNORE INTO investor_auth (investor_id, email_verified)
                VALUES (?, 0)
            """, (investor_id,))
            print(f"   • Created auth record for {name}")
        
        conn.commit()
        print(f"\n✅ Migration complete! Created {len(investors)} auth records")
        
        print("""
NEXT STEPS:
-----------
1. Investors will receive verification emails on first login attempt
2. They click the link to set their password
3. After that, normal email/password login works

To manually verify an investor (skip email verification):
    python scripts/setup/verify_investor.py --email investor@email.com
""")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()


if __name__ == '__main__':
    success = run_migration()
    exit(0 if success else 1)
