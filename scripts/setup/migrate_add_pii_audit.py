"""
Migration: Add PII Access Audit Log Table + Investor Profiles Triggers
=======================================================================

Creates:
1. pii_access_log table for tracking who accessed/modified encrypted PII fields
2. Audit triggers on investor_profiles for INSERT and UPDATE events

Usage:
    python scripts/setup/migrate_add_pii_audit.py
"""

import os
import sys
import sqlite3
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

DB_PATH = os.getenv("DATABASE_PATH", str(PROJECT_DIR / "data" / "tovito.db"))


def run_migration():
    """Create pii_access_log table and investor_profiles audit triggers."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"Database: {DB_PATH}")
    print()

    # Create PII access log table
    print("Creating table: pii_access_log...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pii_access_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            investor_id TEXT NOT NULL,
            field_name TEXT NOT NULL,
            access_type TEXT NOT NULL CHECK (access_type IN ('read', 'write')),
            performed_by TEXT NOT NULL DEFAULT 'system',
            ip_address TEXT,
            context TEXT
        )
    """)
    print("[OK] pii_access_log table created")

    # Create indexes
    print("Creating indexes...")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pii_access_investor
        ON pii_access_log(investor_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pii_access_timestamp
        ON pii_access_log(timestamp)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pii_access_field
        ON pii_access_log(field_name)
    """)
    print("[OK] Indexes created")

    # Create audit triggers on investor_profiles
    # These log INSERT and UPDATE events to the existing audit_log table
    # Encrypted field values are logged as [ENCRYPTED] placeholder
    print("Creating investor_profiles audit triggers...")

    # Drop existing triggers first (idempotent)
    cursor.execute("DROP TRIGGER IF EXISTS trg_audit_profiles_insert")
    cursor.execute("DROP TRIGGER IF EXISTS trg_audit_profiles_update")

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_audit_profiles_insert
        AFTER INSERT ON investor_profiles
        FOR EACH ROW
        BEGIN
            INSERT INTO audit_log (table_name, record_id, action, new_values)
            VALUES ('investor_profiles', NEW.investor_id, 'INSERT',
                    json_object(
                        'full_legal_name', NEW.full_legal_name,
                        'email_primary', NEW.email_primary,
                        'ssn_encrypted', CASE WHEN NEW.ssn_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                        'tax_id_encrypted', CASE WHEN NEW.tax_id_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                        'bank_routing_encrypted', CASE WHEN NEW.bank_routing_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                        'bank_account_encrypted', CASE WHEN NEW.bank_account_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                        'profile_completed', NEW.profile_completed
                    ));
        END
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_audit_profiles_update
        AFTER UPDATE ON investor_profiles
        FOR EACH ROW
        BEGIN
            INSERT INTO audit_log (table_name, record_id, action, old_values, new_values)
            VALUES ('investor_profiles', NEW.investor_id, 'UPDATE',
                    json_object(
                        'full_legal_name', OLD.full_legal_name,
                        'email_primary', OLD.email_primary,
                        'ssn_encrypted', CASE WHEN OLD.ssn_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                        'tax_id_encrypted', CASE WHEN OLD.tax_id_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                        'bank_routing_encrypted', CASE WHEN OLD.bank_routing_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                        'bank_account_encrypted', CASE WHEN OLD.bank_account_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                        'profile_completed', OLD.profile_completed
                    ),
                    json_object(
                        'full_legal_name', NEW.full_legal_name,
                        'email_primary', NEW.email_primary,
                        'ssn_encrypted', CASE WHEN NEW.ssn_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                        'tax_id_encrypted', CASE WHEN NEW.tax_id_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                        'bank_routing_encrypted', CASE WHEN NEW.bank_routing_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                        'bank_account_encrypted', CASE WHEN NEW.bank_account_encrypted IS NOT NULL THEN '[ENCRYPTED]' ELSE NULL END,
                        'profile_completed', NEW.profile_completed
                    ));
        END
    """)
    print("[OK] Audit triggers created")

    conn.commit()
    conn.close()

    print()
    print("[OK] Migration complete")


if __name__ == "__main__":
    run_migration()
