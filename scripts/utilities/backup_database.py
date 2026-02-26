"""
Database Backup Script
======================

Creates timestamped backups of the Tovito database.
Supports simple (DB-only) and full (DB + .env + session) backups
with optional passphrase-based encryption for sensitive files.

Includes backup verification, rotation, and manifest tracking.

Usage:
    python scripts/utilities/backup_database.py             # Simple DB backup
    python scripts/utilities/backup_database.py --full       # Full backup (DB only, no passphrase)
    python scripts/utilities/backup_database.py --full --passphrase SECRET  # Full backup with encrypted .env
    python scripts/utilities/backup_database.py --list       # List all backups
    python scripts/utilities/backup_database.py --summary    # Show backup summary
    python scripts/utilities/backup_database.py --verify PATH  # Verify backup integrity
    python scripts/utilities/backup_database.py --rotate     # Rotate old backups
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import os
import shutil
import sqlite3
import hashlib
import json
import base64
from datetime import datetime, timedelta
import sys
from pathlib import Path
from typing import Optional

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.safe_logging import get_safe_logger

logger = get_safe_logger(__name__)

# Sensitive files that can be included in full backups (relative to PROJECT_ROOT)
SENSITIVE_FILES = [
    '.env',
    '.tastytrade_session',
]

# Salt file location for passphrase-based encryption
SALT_FILE = 'data/backups/.backup_salt'


def _derive_key_from_passphrase(passphrase: str, salt: bytes) -> bytes:
    """
    Derive a Fernet-compatible key from a passphrase using PBKDF2.

    Args:
        passphrase: User-provided passphrase string
        salt: Random salt bytes (16 bytes)

    Returns:
        URL-safe base64-encoded 32-byte key suitable for Fernet
    """
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    key_bytes = kdf.derive(passphrase.encode('utf-8'))
    return base64.urlsafe_b64encode(key_bytes)


def _get_or_create_salt() -> bytes:
    """
    Load the backup salt from disk, or create one if it doesn't exist.

    The salt is stored at data/backups/.backup_salt and reused for all
    passphrase-based encryption operations.

    Returns:
        16 bytes of salt
    """
    salt_path = PROJECT_ROOT / SALT_FILE
    salt_path.parent.mkdir(parents=True, exist_ok=True)

    if salt_path.exists():
        return salt_path.read_bytes()

    salt = os.urandom(16)
    salt_path.write_bytes(salt)
    logger.info("Created new backup salt file")
    return salt


def _sha256_file(filepath: str) -> str:
    """
    Compute SHA256 hex digest of a file.

    Args:
        filepath: Path to the file

    Returns:
        Hex string of the SHA256 hash
    """
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _encrypt_file(source_path: str, dest_path: str, passphrase: str, salt: bytes):
    """
    Encrypt a file using Fernet with a passphrase-derived key.

    Args:
        source_path: Path to the plaintext file
        dest_path: Path to write the encrypted file
        passphrase: User passphrase
        salt: PBKDF2 salt bytes
    """
    from cryptography.fernet import Fernet

    key = _derive_key_from_passphrase(passphrase, salt)
    fernet = Fernet(key)

    with open(source_path, 'rb') as f:
        plaintext = f.read()

    ciphertext = fernet.encrypt(plaintext)

    with open(dest_path, 'wb') as f:
        f.write(ciphertext)


def _decrypt_file(source_path: str, passphrase: str, salt: bytes) -> bytes:
    """
    Decrypt a file encrypted with _encrypt_file.

    Args:
        source_path: Path to the encrypted file
        passphrase: User passphrase (same as used for encryption)
        salt: PBKDF2 salt bytes (same as used for encryption)

    Returns:
        Decrypted bytes

    Raises:
        cryptography.fernet.InvalidToken: If passphrase is wrong
    """
    from cryptography.fernet import Fernet

    key = _derive_key_from_passphrase(passphrase, salt)
    fernet = Fernet(key)

    with open(source_path, 'rb') as f:
        ciphertext = f.read()

    return fernet.decrypt(ciphertext)


class DatabaseBackup:
    """Handle database backups"""

    def __init__(self):
        self.db_path = 'data/tovito.db'
        self.backup_dir = 'data/backups'

        # Create backup directory if it doesn't exist
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self) -> dict:
        """
        Create a timestamped backup of the database.

        Returns:
            dict: Result with status, backup_path, and size
        """
        try:
            # Check if database exists
            if not os.path.exists(self.db_path):
                return {
                    'status': 'error',
                    'error': f'Database not found: {self.db_path}'
                }

            # Get database size
            db_size = os.path.getsize(self.db_path)

            # Create timestamp: YYYY-MM-DD_HHMMSS
            timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')

            # Create backup filename
            backup_filename = f'tovito_backup_{timestamp}.db'
            backup_path = os.path.join(self.backup_dir, backup_filename)

            # Copy database file
            print(f"[BACKUP] Creating backup...")
            print(f"   Source: {self.db_path}")
            print(f"   Destination: {backup_path}")

            shutil.copy2(self.db_path, backup_path)

            # Verify backup was created
            if not os.path.exists(backup_path):
                return {
                    'status': 'error',
                    'error': 'Backup file was not created'
                }

            # Get backup size
            backup_size = os.path.getsize(backup_path)

            # Verify sizes match
            if backup_size != db_size:
                return {
                    'status': 'error',
                    'error': f'Size mismatch: original={db_size}, backup={backup_size}'
                }

            print(f"[OK] Backup created successfully!")
            print(f"   Size: {backup_size:,} bytes")
            print(f"   Location: {backup_path}")

            logger.info("Database backup created",
                       backup_file=backup_filename,
                       size_bytes=backup_size)

            return {
                'status': 'success',
                'backup_path': backup_path,
                'backup_filename': backup_filename,
                'size_bytes': backup_size,
                'timestamp': timestamp
            }

        except Exception as e:
            try:
                error_msg = f"Backup failed: {str(e)}"
            except UnicodeEncodeError:
                error_msg = f"Backup failed: {ascii(e)}"
            print(f"[ERROR] {error_msg}")
            logger.error("Database backup failed", error=str(e))
            return {
                'status': 'error',
                'error': str(e)
            }

    def create_full_backup(self, passphrase: Optional[str] = None) -> dict:
        """
        Create a full backup including database, .env, and .tastytrade_session.

        The database is copied as-is. Sensitive files (.env, .tastytrade_session)
        are encrypted with Fernet using a passphrase-derived key (PBKDF2).

        Args:
            passphrase: Passphrase for encrypting sensitive files. If None,
                        sensitive files are skipped with a warning.

        Returns:
            dict with status, backup_dir, manifest
        """
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
            backup_dirname = f'full_{timestamp}'
            backup_dir_path = os.path.join(self.backup_dir, backup_dirname)

            os.makedirs(backup_dir_path, exist_ok=True)

            print(f"[BACKUP] Creating full backup...")
            print(f"   Directory: {backup_dir_path}")

            manifest_files = []

            # --- Step 1: Database backup ---
            if os.path.exists(self.db_path):
                db_dest = os.path.join(backup_dir_path, 'tovito_backup.db')
                shutil.copy2(self.db_path, db_dest)

                db_size = os.path.getsize(db_dest)
                db_hash = _sha256_file(db_dest)

                manifest_files.append({
                    'filename': 'tovito_backup.db',
                    'original_path': self.db_path,
                    'size_bytes': db_size,
                    'sha256': db_hash,
                    'encrypted': False,
                })
                print(f"   [OK] Database: {db_size:,} bytes")
            else:
                print(f"   [WARN] Database not found: {self.db_path}")

            # --- Step 2: Sensitive files ---
            salt = None
            if passphrase:
                salt = _get_or_create_salt()

            for sensitive_file in SENSITIVE_FILES:
                source = os.path.join(str(PROJECT_ROOT), sensitive_file)
                if not os.path.exists(source):
                    print(f"   [--] Skipped {sensitive_file} (not found)")
                    continue

                if passphrase and salt is not None:
                    # Encrypt the file
                    enc_filename = sensitive_file.lstrip('.').replace(os.sep, '_') + '_backup.enc'
                    enc_dest = os.path.join(backup_dir_path, enc_filename)

                    _encrypt_file(source, enc_dest, passphrase, salt)

                    enc_size = os.path.getsize(enc_dest)
                    enc_hash = _sha256_file(enc_dest)

                    manifest_files.append({
                        'filename': enc_filename,
                        'original_path': sensitive_file,
                        'size_bytes': enc_size,
                        'sha256': enc_hash,
                        'encrypted': True,
                    })
                    print(f"   [OK] {sensitive_file}: encrypted ({enc_size:,} bytes)")
                else:
                    print(f"   [WARN] {sensitive_file} NOT included (no passphrase provided)")

            if not passphrase:
                has_sensitive = any(
                    os.path.exists(os.path.join(str(PROJECT_ROOT), sf))
                    for sf in SENSITIVE_FILES
                )
                if has_sensitive:
                    print()
                    print("   [WARN] Sensitive files (.env, .tastytrade_session) were NOT backed up.")
                    print("   To include them, run with: --passphrase YOUR_PASSPHRASE")

            # --- Step 3: Write manifest ---
            manifest = {
                'timestamp': timestamp,
                'backup_type': 'full',
                'files': manifest_files,
            }
            manifest_path = os.path.join(backup_dir_path, 'manifest.json')
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2)

            print(f"   [OK] Manifest written ({len(manifest_files)} files)")
            print(f"[OK] Full backup complete: {backup_dir_path}")

            logger.info("Full backup created",
                       backup_dir=backup_dirname,
                       file_count=len(manifest_files))

            return {
                'status': 'success',
                'backup_dir': backup_dir_path,
                'manifest': manifest,
            }

        except Exception as e:
            try:
                error_msg = f"Full backup failed: {str(e)}"
            except UnicodeEncodeError:
                error_msg = f"Full backup failed: {ascii(e)}"
            print(f"[ERROR] {error_msg}")
            logger.error("Full backup failed", error=str(e))
            return {
                'status': 'error',
                'error': str(e),
            }

    def verify_backup(self, backup_path: str) -> dict:
        """
        Verify the integrity of a backup file or full backup directory.

        For a .db file: runs PRAGMA integrity_check and verifies size > 0.
        For a full backup directory: reads manifest.json, verifies each file
        exists, checks SHA256 checksums, and runs PRAGMA integrity_check on
        the .db file.

        Args:
            backup_path: Path to a .db file or a full backup directory

        Returns:
            dict with status ('ok' or 'corrupted') and details list
        """
        details = []

        try:
            backup_path_obj = Path(backup_path)

            # --- Case 1: Single .db file ---
            if backup_path_obj.is_file() and backup_path_obj.suffix == '.db':
                return self._verify_db_file(str(backup_path_obj))

            # --- Case 2: Full backup directory ---
            if backup_path_obj.is_dir():
                manifest_path = backup_path_obj / 'manifest.json'
                if not manifest_path.exists():
                    return {
                        'status': 'corrupted',
                        'details': ['manifest.json not found in backup directory'],
                    }

                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)

                all_ok = True
                for file_entry in manifest.get('files', []):
                    filename = file_entry['filename']
                    filepath = backup_path_obj / filename

                    if not filepath.exists():
                        details.append(f"MISSING: {filename}")
                        all_ok = False
                        continue

                    # Check SHA256
                    actual_hash = _sha256_file(str(filepath))
                    expected_hash = file_entry.get('sha256', '')
                    if actual_hash != expected_hash:
                        details.append(f"CHECKSUM MISMATCH: {filename}")
                        all_ok = False
                    else:
                        details.append(f"OK: {filename} (checksum verified)")

                    # If it's a .db file, also run integrity check
                    if filename.endswith('.db'):
                        db_result = self._verify_db_file(str(filepath))
                        if db_result['status'] != 'ok':
                            details.extend(db_result['details'])
                            all_ok = False
                        else:
                            details.append(f"OK: {filename} (PRAGMA integrity_check passed)")

                status = 'ok' if all_ok else 'corrupted'
                return {'status': status, 'details': details}

            # --- Not a recognized backup ---
            return {
                'status': 'corrupted',
                'details': [f'Not a recognized backup: {backup_path}'],
            }

        except Exception as e:
            try:
                msg = str(e)
            except UnicodeEncodeError:
                msg = ascii(e)
            return {
                'status': 'corrupted',
                'details': [f'Verification error: {msg}'],
            }

    def _verify_db_file(self, db_path: str) -> dict:
        """
        Verify a single .db file using PRAGMA integrity_check.

        Args:
            db_path: Path to the SQLite database file

        Returns:
            dict with status ('ok' or 'corrupted') and details list
        """
        details = []

        # Check file size
        size = os.path.getsize(db_path)
        if size == 0:
            return {
                'status': 'corrupted',
                'details': ['Database file is empty (0 bytes)'],
            }
        details.append(f'File size: {size:,} bytes')

        # Run PRAGMA integrity_check
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.execute('PRAGMA integrity_check')
            result = cursor.fetchone()
            conn.close()

            if result and result[0] == 'ok':
                details.append('PRAGMA integrity_check: ok')
                return {'status': 'ok', 'details': details}
            else:
                details.append(f'PRAGMA integrity_check: {result}')
                return {'status': 'corrupted', 'details': details}

        except Exception as e:
            try:
                msg = str(e)
            except UnicodeEncodeError:
                msg = ascii(e)
            details.append(f'PRAGMA integrity_check failed: {msg}')
            return {'status': 'corrupted', 'details': details}

    def rotate_backups(self, keep_count: int = 30, keep_days: int = 90) -> dict:
        """
        Remove old backups beyond retention thresholds.

        Removes backups that are BOTH older than keep_days AND beyond
        the keep_count newest. The oldest backup is ALWAYS preserved
        as a baseline regardless of age or count.

        Args:
            keep_count: Maximum number of backups to keep (default 30)
            keep_days: Maximum age in days (default 90)

        Returns:
            dict with removed_count, remaining_count, freed_bytes
        """
        try:
            all_backups = self.list_backups()

            if len(all_backups) <= 1:
                # Nothing to rotate if 0 or 1 backups
                return {
                    'removed_count': 0,
                    'remaining_count': len(all_backups),
                    'freed_bytes': 0,
                }

            cutoff_date = datetime.now() - timedelta(days=keep_days)

            # Sort by date, newest first (list_backups already does this)
            # Identify the oldest backup (last in sorted list)
            oldest_backup = all_backups[-1]

            removed_count = 0
            freed_bytes = 0
            remaining = []

            for i, backup in enumerate(all_backups):
                # Always keep the oldest backup (baseline)
                if backup['path'] == oldest_backup['path']:
                    remaining.append(backup)
                    continue

                # Check if this backup is beyond the keep_count AND older than cutoff
                is_beyond_count = i >= keep_count
                is_too_old = backup['modified'] < cutoff_date

                if is_beyond_count and is_too_old:
                    # Remove this backup
                    try:
                        btype = backup.get('type', 'simple')
                        if btype == 'full' and os.path.isdir(backup['path']):
                            dir_size = self._get_dir_size(backup['path'])
                            shutil.rmtree(backup['path'])
                            freed_bytes += dir_size
                        else:
                            freed_bytes += backup.get('size_bytes', 0)
                            os.remove(backup['path'])
                        removed_count += 1
                        print(f"   [REMOVED] {backup.get('filename', backup['path'])}")
                    except Exception as e:
                        try:
                            msg = str(e)
                        except UnicodeEncodeError:
                            msg = ascii(e)
                        print(f"   [ERROR] Could not remove {backup['path']}: {msg}")
                        remaining.append(backup)
                else:
                    remaining.append(backup)

            result = {
                'removed_count': removed_count,
                'remaining_count': len(remaining),
                'freed_bytes': freed_bytes,
            }

            if removed_count > 0:
                freed_mb = freed_bytes / (1024 * 1024)
                print(f"[OK] Rotation complete: removed {removed_count} backup(s), freed {freed_mb:.2f} MB")
            else:
                print(f"[OK] No backups eligible for rotation ({len(remaining)} within retention policy)")

            logger.info("Backup rotation completed",
                       removed=removed_count,
                       remaining=len(remaining),
                       freed_bytes=freed_bytes)

            return result

        except Exception as e:
            try:
                msg = str(e)
            except UnicodeEncodeError:
                msg = ascii(e)
            print(f"[ERROR] Rotation failed: {msg}")
            logger.error("Backup rotation failed", error=str(e))
            return {
                'removed_count': 0,
                'remaining_count': 0,
                'freed_bytes': 0,
            }

    def list_backups(self) -> list:
        """
        List all existing backups (simple .db files and full backup directories).

        Returns:
            List of dicts with filename, path, size_bytes, modified, type
            sorted by modified date (newest first)
        """
        try:
            backups = []

            if not os.path.exists(self.backup_dir):
                return backups

            for entry_name in os.listdir(self.backup_dir):
                entry_path = os.path.join(self.backup_dir, entry_name)

                # Simple .db backup files
                if entry_name.endswith('.db') and os.path.isfile(entry_path):
                    size = os.path.getsize(entry_path)
                    modified = datetime.fromtimestamp(os.path.getmtime(entry_path))

                    backups.append({
                        'filename': entry_name,
                        'path': entry_path,
                        'size_bytes': size,
                        'modified': modified,
                        'type': 'simple',
                    })

                # Full backup directories (full_YYYY-MM-DD_HHMMSS)
                elif entry_name.startswith('full_') and os.path.isdir(entry_path):
                    manifest_path = os.path.join(entry_path, 'manifest.json')
                    dir_size = self._get_dir_size(entry_path)

                    # Try to get timestamp from manifest or directory name
                    modified = datetime.fromtimestamp(os.path.getmtime(entry_path))
                    if os.path.exists(manifest_path):
                        try:
                            with open(manifest_path, 'r', encoding='utf-8') as f:
                                manifest = json.load(f)
                            ts_str = manifest.get('timestamp', '')
                            if ts_str:
                                modified = datetime.strptime(ts_str, '%Y-%m-%d_%H%M%S')
                        except (json.JSONDecodeError, ValueError):
                            pass

                    backups.append({
                        'filename': entry_name,
                        'path': entry_path,
                        'size_bytes': dir_size,
                        'modified': modified,
                        'type': 'full',
                    })

            # Sort by modified date (newest first)
            backups.sort(key=lambda x: x['modified'], reverse=True)

            return backups

        except Exception as e:
            logger.error("Failed to list backups", error=str(e))
            return []

    def _get_dir_size(self, dir_path: str) -> int:
        """Calculate total size of all files in a directory."""
        total = 0
        for dirpath, _dirnames, filenames in os.walk(dir_path):
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                try:
                    total += os.path.getsize(fpath)
                except OSError:
                    pass
        return total

    def show_backup_summary(self):
        """Display summary of all backups"""
        backups = self.list_backups()

        if not backups:
            print("\n[INFO] No backups found")
            return

        print(f"\n{'='*70}")
        print(f"DATABASE BACKUPS")
        print(f"{'='*70}")
        print(f"Location: {self.backup_dir}")
        print(f"Total backups: {len(backups)}")
        print(f"{'='*70}\n")

        total_size = 0

        for backup in backups:
            size_kb = backup['size_bytes'] / 1024
            total_size += backup['size_bytes']
            btype = backup.get('type', 'simple')
            type_label = '[FULL]' if btype == 'full' else '[DB]'

            print(f"  {type_label} {backup['filename']}")
            print(f"   Date: {backup['modified'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Size: {size_kb:.1f} KB")
            print()

        print(f"{'='*70}")
        total_mb = total_size / (1024 * 1024)
        print(f"Total storage: {total_mb:.2f} MB")
        print(f"{'='*70}\n")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Backup Tovito database')
    parser.add_argument('--list', action='store_true', help='List all backups')
    parser.add_argument('--summary', action='store_true', help='Show backup summary')
    parser.add_argument('--full', action='store_true', help='Create full backup (DB + .env + session)')
    parser.add_argument('--passphrase', type=str, default=None,
                        help='Passphrase for encrypting sensitive files in full backup')
    parser.add_argument('--rotate', action='store_true', help='Rotate old backups')
    parser.add_argument('--keep', type=int, default=30,
                        help='Number of backups to keep during rotation (default: 30)')
    parser.add_argument('--verify', type=str, default=None, metavar='PATH',
                        help='Verify integrity of a backup file or directory')

    args = parser.parse_args()

    backup_manager = DatabaseBackup()

    if args.list or args.summary:
        backup_manager.show_backup_summary()

    elif args.verify:
        print(f"[VERIFY] Checking backup: {args.verify}")
        result = backup_manager.verify_backup(args.verify)
        for detail in result.get('details', []):
            print(f"   {detail}")
        if result['status'] == 'ok':
            print(f"[OK] Backup is valid")
            sys.exit(0)
        else:
            print(f"[ERROR] Backup is corrupted or invalid")
            sys.exit(1)

    elif args.rotate:
        print(f"[ROTATE] Running backup rotation (keep={args.keep}, keep_days=90)...")
        backup_manager.rotate_backups(keep_count=args.keep, keep_days=90)

    elif args.full:
        result = backup_manager.create_full_backup(passphrase=args.passphrase)
        if result['status'] == 'success':
            print(f"\n[OK] Full backup complete!")
            sys.exit(0)
        else:
            print(f"\n[ERROR] Full backup failed: {result.get('error')}")
            sys.exit(1)

    else:
        # Default: simple database backup
        result = backup_manager.create_backup()

        if result['status'] == 'success':
            print(f"\n[OK] Backup complete!")
            sys.exit(0)
        else:
            print(f"\n[ERROR] Backup failed: {result.get('error')}")
            sys.exit(1)


if __name__ == "__main__":
    main()
