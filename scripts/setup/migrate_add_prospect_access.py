"""
Migration: Add Prospect Access Tokens Table
=============================================

Creates the prospect_access_tokens table for gated prospect
access to fund performance data via token-based URLs.

Usage:
    python scripts/setup/migrate_add_prospect_access.py
"""

import os
import sys
import sqlite3
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

DB_PATH = os.getenv("DATABASE_PATH", str(PROJECT_DIR / "data" / "tovito.db"))


def run_migration():
    """Create prospect_access_tokens table."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print(f"Database: {DB_PATH}")
    print()

    # Create table
    print("Creating table: prospect_access_tokens...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prospect_access_tokens (
            token_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            last_accessed_at TIMESTAMP,
            access_count INTEGER DEFAULT 0,
            is_revoked INTEGER DEFAULT 0,
            created_by TEXT DEFAULT 'admin',
            FOREIGN KEY (prospect_id) REFERENCES prospects(id)
        )
    """)

    # Index for fast token lookup
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_prospect_token
        ON prospect_access_tokens(token)
    """)

    # Index for prospect lookup (one active token per prospect)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_prospect_token_prospect
        ON prospect_access_tokens(prospect_id)
    """)

    conn.commit()
    conn.close()

    print("[OK] prospect_access_tokens table created")
    print()
    print("[OK] Migration complete")


if __name__ == "__main__":
    run_migration()
