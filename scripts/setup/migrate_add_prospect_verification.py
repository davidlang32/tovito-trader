"""
Migration: Add Prospect Email Verification Columns
====================================================

Adds email_verified, verification_token, and verification_token_expires
columns to the existing prospects table.

Usage:
    python scripts/setup/migrate_add_prospect_verification.py
"""

import os
import sys
import sqlite3
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

DB_PATH = os.getenv("DATABASE_PATH", str(PROJECT_DIR / "data" / "tovito.db"))


def run_migration():
    """Add email verification columns to prospects table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"Database: {DB_PATH}")
    print()

    # Check if prospects table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='prospects'"
    )
    if not cursor.fetchone():
        print("[ERROR] prospects table does not exist. Run the base migration first.")
        conn.close()
        return

    # Check which columns already exist
    cursor.execute("PRAGMA table_info(prospects)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    columns_to_add = [
        ("email_verified", "INTEGER DEFAULT 0"),
        ("verification_token", "TEXT"),
        ("verification_token_expires", "TIMESTAMP"),
    ]

    added = 0
    for col_name, col_def in columns_to_add:
        if col_name in existing_cols:
            print(f"  [SKIP] Column '{col_name}' already exists")
        else:
            cursor.execute(
                f"ALTER TABLE prospects ADD COLUMN {col_name} {col_def}"
            )
            print(f"  [OK] Added column '{col_name}' ({col_def})")
            added += 1

    # Index for fast token lookup
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_prospects_verification_token
        ON prospects(verification_token)
    """)
    print("  [OK] Index idx_prospects_verification_token ensured")

    conn.commit()
    conn.close()

    print()
    print(f"[OK] Migration complete ({added} columns added)")


if __name__ == "__main__":
    run_migration()
