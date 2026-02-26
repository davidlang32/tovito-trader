"""
Encryption Key Rotation Script
================================

Rotates the encryption key for all encrypted PII fields in investor_profiles.
Creates a database backup first, then decrypts all fields with the current key
and re-encrypts with the new key using versioned ciphertext format (v1:...).

Safety:
    - Creates a database backup before starting
    - Wraps all updates in a single transaction (rollback on any failure)
    - Validates every field round-trips correctly before committing
    - Supports --dry-run to preview changes without writing

Usage:
    python scripts/setup/rotate_encryption_key.py                    # Generate new key and rotate
    python scripts/setup/rotate_encryption_key.py --dry-run          # Preview without writing
    python scripts/setup/rotate_encryption_key.py --new-key KEY      # Use specific new key

Post-rotation steps:
    1. Update ENCRYPTION_KEY in .env with the new key
    2. Add the old key to ENCRYPTION_LEGACY_KEYS in .env
    3. Restart any running services
    4. Verify profile access still works
"""

import os
import sys
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv
load_dotenv(PROJECT_DIR / ".env")

DB_PATH = os.getenv("DATABASE_PATH", str(PROJECT_DIR / "data" / "tovito.db"))

# Fields in investor_profiles that are encrypted
ENCRYPTED_FIELDS = [
    'ssn_encrypted',
    'tax_id_encrypted',
    'bank_routing_encrypted',
    'bank_account_encrypted',
    'date_of_birth',
]


def create_backup():
    """Create a database backup before rotation."""
    try:
        from scripts.utilities.backup_database import create_backup as do_backup
        do_backup()
        return True
    except Exception:
        # Fallback: manual backup
        import shutil
        db_path = Path(DB_PATH)
        if not db_path.exists():
            print("[ERROR] Database not found: %s" % DB_PATH)
            return False

        backup_dir = db_path.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"tovito_backup_{timestamp}_pre_rotation.db"
        shutil.copy2(db_path, backup_path)
        print(f"[OK] Backup created: {backup_path}")
        return True


def rotate_keys(new_key: str, dry_run: bool = False):
    """
    Rotate encryption key for all encrypted fields.

    Args:
        new_key: The new Fernet key to encrypt with
        dry_run: If True, show what would change without writing
    """
    from src.utils.encryption import FieldEncryptor

    # Initialize encryptors
    current_key = os.getenv('ENCRYPTION_KEY')
    if not current_key:
        print("[ERROR] ENCRYPTION_KEY not set in environment. Cannot rotate.")
        return False

    try:
        current_enc = FieldEncryptor(current_key)
    except ValueError as e:
        print(f"[ERROR] Current key is invalid: {e}")
        return False

    try:
        new_enc = FieldEncryptor(new_key)
    except ValueError as e:
        print(f"[ERROR] New key is invalid: {e}")
        return False

    if current_key == new_key:
        print("[ERROR] New key is the same as the current key. Nothing to rotate.")
        return False

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Read all profiles with encrypted fields
        field_list = ', '.join(['investor_id'] + ENCRYPTED_FIELDS)
        cursor.execute(f"SELECT {field_list} FROM investor_profiles")
        rows = cursor.fetchall()

        if not rows:
            print("[OK] No investor profiles found. Nothing to rotate.")
            conn.close()
            return True

        print(f"Found {len(rows)} investor profile(s) to process")
        print()

        total_fields = 0
        rotated_fields = 0
        skipped_fields = 0
        errors = []

        for row in rows:
            investor_id = row['investor_id']
            updates = {}

            for field in ENCRYPTED_FIELDS:
                total_fields += 1
                value = row[field]

                if value is None:
                    skipped_fields += 1
                    continue

                # Decrypt with current key
                try:
                    plaintext = current_enc.decrypt(value)
                except ValueError as e:
                    errors.append(f"  {investor_id}.{field}: decrypt failed - {e}")
                    continue

                # Re-encrypt with new key (produces v1: prefix)
                new_ciphertext = new_enc.encrypt(plaintext)

                # Validate round-trip with new key
                try:
                    verify = new_enc.decrypt(new_ciphertext)
                    if verify != plaintext:
                        errors.append(f"  {investor_id}.{field}: round-trip verification failed")
                        continue
                except ValueError as e:
                    errors.append(f"  {investor_id}.{field}: verification decrypt failed - {e}")
                    continue

                updates[field] = new_ciphertext
                rotated_fields += 1

                if dry_run:
                    # Mask the field for display
                    masked = plaintext[:2] + "***" + plaintext[-2:] if len(plaintext) > 4 else "****"
                    print(f"  [DRY-RUN] {investor_id}.{field}: would re-encrypt ({masked})")

            # Apply updates for this investor
            if updates and not dry_run:
                set_clause = ', '.join([f"{f} = ?" for f in updates.keys()])
                values = list(updates.values()) + [investor_id]
                cursor.execute(
                    f"UPDATE investor_profiles SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE investor_id = ?",
                    values
                )

        # Check for errors before committing
        if errors:
            print()
            print("[WARN] Errors encountered:")
            for err in errors:
                print(err)
            print()
            if not dry_run:
                print("[ROLLBACK] Rolling back due to errors. No changes written.")
                conn.rollback()
                conn.close()
                return False

        # Commit if not dry-run
        if not dry_run:
            conn.commit()

        conn.close()

        # Print summary
        print()
        print("=" * 60)
        if dry_run:
            print("  DRY RUN SUMMARY (no changes written)")
        else:
            print("  ROTATION COMPLETE")
        print("=" * 60)
        print(f"  Profiles processed: {len(rows)}")
        print(f"  Fields checked:     {total_fields}")
        print(f"  Fields rotated:     {rotated_fields}")
        print(f"  Fields skipped:     {skipped_fields} (NULL)")
        print(f"  Errors:             {len(errors)}")
        print()

        if not dry_run and rotated_fields > 0:
            print("  NEXT STEPS:")
            print("  1. Update ENCRYPTION_KEY in .env with the new key:")
            print(f"     ENCRYPTION_KEY={new_key}")
            print()
            print("  2. Add the old key to ENCRYPTION_LEGACY_KEYS:")
            print(f"     ENCRYPTION_LEGACY_KEYS={current_key}")
            print()
            print("  3. Restart any running services (API, scripts)")
            print("  4. Verify profile access still works:")
            print("     python scripts/investor/manage_profile.py")
            print()

        return True

    except Exception as e:
        conn.rollback()
        conn.close()
        try:
            print(f"[ERROR] Rotation failed: {e}")
        except UnicodeEncodeError:
            print(f"[ERROR] Rotation failed: {ascii(str(e))}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Rotate encryption key for investor profile PII fields"
    )
    parser.add_argument(
        '--new-key',
        help='New Fernet key to use. If not provided, one will be generated.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would change without writing to database'
    )
    parser.add_argument(
        '--skip-backup',
        action='store_true',
        help='Skip database backup (not recommended)'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  ENCRYPTION KEY ROTATION")
    print("=" * 60)
    print(f"  Database: {DB_PATH}")
    print(f"  Mode:     {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    # Generate or validate new key
    if args.new_key:
        new_key = args.new_key
        print("  Using provided key")
    else:
        from src.utils.encryption import FieldEncryptor
        new_key = FieldEncryptor.generate_key()
        print("  Generated new key")

    print()

    # Create backup
    if not args.dry_run and not args.skip_backup:
        print("Creating database backup...")
        if not create_backup():
            print("[ERROR] Backup failed. Aborting rotation.")
            print("Use --skip-backup to override (not recommended).")
            sys.exit(1)
        print()

    # Perform rotation
    success = rotate_keys(new_key, dry_run=args.dry_run)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
