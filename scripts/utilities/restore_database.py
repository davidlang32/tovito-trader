"""
Database Restore Script
=======================

Restores the Tovito database from a backup file or full backup directory.
Always creates a safety backup of the current database before restoring.

Supports restoring:
  - Simple .db backups (database only)
  - Full backup directories (database + encrypted .env + session)

Usage:
    python scripts/utilities/restore_database.py --list                # List available backups
    python scripts/utilities/restore_database.py --restore PATH        # Restore from specific backup
    python scripts/utilities/restore_database.py --latest              # Restore from most recent backup
    python scripts/utilities/restore_database.py --verify PATH         # Verify backup integrity only
    python scripts/utilities/restore_database.py --full DIR --passphrase X  # Full restore (DB + .env)
    python scripts/utilities/restore_database.py --restore PATH --target data/other.db  # Custom target
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import os
import shutil
import sqlite3
import json
import tempfile
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.safe_logging import get_safe_logger

logger = get_safe_logger(__name__)


class DatabaseRestore:
    """Handle database restoration from backups"""

    def __init__(self):
        self.db_path = 'data/tovito.db'
        self.backup_dir = 'data/backups'

    def list_available_backups(self) -> list:
        """
        List all available backups with type, date, and size.

        Returns both simple .db files and full backup directories.
        Uses DatabaseBackup.list_backups() for consistency.

        Returns:
            List of dicts with filename, path, size_bytes, modified, type
            sorted by date (newest first)
        """
        from scripts.utilities.backup_database import DatabaseBackup
        backup_mgr = DatabaseBackup()
        return backup_mgr.list_backups()

    def restore_database(self, backup_path: str,
                         target_path: Optional[str] = None) -> dict:
        """
        Restore a database from a backup file or full backup directory.

        Steps:
          1. Create a safety backup of the current database
          2. Verify the backup file integrity (PRAGMA integrity_check)
          3. Copy backup to target path
          4. Run PRAGMA integrity_check on the restored copy

        Args:
            backup_path: Path to a .db file or a full backup directory
                         (will look for tovito_backup.db inside it)
            target_path: Where to restore to. Defaults to data/tovito.db

        Returns:
            dict with status, safety_backup_path, restored_from
        """
        if target_path is None:
            target_path = self.db_path

        try:
            # Resolve the actual .db file to restore from
            source_db = self._resolve_db_path(backup_path)
            if source_db is None:
                return {
                    'status': 'error',
                    'error': f'No database file found at: {backup_path}',
                }

            print(f"[RESTORE] Restoring database...")
            print(f"   Source: {source_db}")
            print(f"   Target: {target_path}")

            # --- Step 1: Safety backup of current database ---
            safety_backup_path = None
            if os.path.exists(target_path):
                print(f"   [STEP 1] Creating safety backup of current database...")
                from scripts.utilities.backup_database import DatabaseBackup
                backup_mgr = DatabaseBackup()
                safety_result = backup_mgr.create_backup()
                if safety_result['status'] == 'success':
                    safety_backup_path = safety_result['backup_path']
                    print(f"   [OK] Safety backup: {safety_backup_path}")
                else:
                    print(f"   [ERROR] Safety backup failed: {safety_result.get('error')}")
                    print(f"   Aborting restore to prevent data loss.")
                    return {
                        'status': 'error',
                        'error': f"Safety backup failed: {safety_result.get('error')}",
                    }
            else:
                print(f"   [STEP 1] No existing database at target -- skipping safety backup")

            # --- Step 2: Verify backup file integrity ---
            print(f"   [STEP 2] Verifying backup integrity...")
            from scripts.utilities.backup_database import DatabaseBackup
            verify_mgr = DatabaseBackup()
            verify_result = verify_mgr.verify_backup(source_db)
            if verify_result['status'] != 'ok':
                print(f"   [ERROR] Backup verification failed:")
                for detail in verify_result.get('details', []):
                    print(f"      {detail}")
                print(f"   Aborting restore -- backup may be corrupted.")
                return {
                    'status': 'error',
                    'error': 'Backup verification failed',
                    'details': verify_result.get('details', []),
                    'safety_backup_path': safety_backup_path,
                }

            for detail in verify_result.get('details', []):
                print(f"      {detail}")
            print(f"   [OK] Backup integrity verified")

            # --- Step 3: Copy backup to target ---
            print(f"   [STEP 3] Copying backup to target...")
            target_dir = os.path.dirname(target_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            shutil.copy2(source_db, target_path)
            print(f"   [OK] Database restored to: {target_path}")

            # --- Step 4: Verify restored copy ---
            print(f"   [STEP 4] Verifying restored database...")
            post_result = verify_mgr.verify_backup(target_path)
            if post_result['status'] != 'ok':
                print(f"   [ERROR] Restored database failed verification:")
                for detail in post_result.get('details', []):
                    print(f"      {detail}")
                print(f"   [WARN] The restored file may be corrupted.")
                print(f"   Safety backup available at: {safety_backup_path}")
                return {
                    'status': 'error',
                    'error': 'Post-restore verification failed',
                    'safety_backup_path': safety_backup_path,
                    'restored_from': source_db,
                }

            print(f"   [OK] Restored database passed integrity check")
            print(f"[OK] Database restore complete!")

            logger.info("Database restored successfully",
                       restored_from=source_db,
                       target=target_path)

            return {
                'status': 'success',
                'safety_backup_path': safety_backup_path,
                'restored_from': source_db,
                'target_path': target_path,
            }

        except Exception as e:
            try:
                msg = str(e)
            except UnicodeEncodeError:
                msg = ascii(e)
            print(f"[ERROR] Restore failed: {msg}")
            logger.error("Database restore failed", error=str(e))
            return {
                'status': 'error',
                'error': str(e),
            }

    def restore_env(self, backup_dir: str, passphrase: str) -> dict:
        """
        Decrypt and inspect the .env backup from a full backup directory.

        Reads and decrypts env_backup.enc, shows a masked diff between
        the current .env and the backed-up version. Does NOT auto-overwrite
        the current .env -- prints the decrypted content path and instructions.

        Args:
            backup_dir: Path to the full backup directory
            passphrase: Passphrase used when the backup was created

        Returns:
            dict with status, changes list, decrypted_path
        """
        try:
            enc_file = os.path.join(backup_dir, 'env_backup.enc')
            if not os.path.exists(enc_file):
                return {
                    'status': 'error',
                    'error': f'Encrypted .env not found: {enc_file}',
                }

            print(f"[RESTORE] Decrypting .env backup...")

            # Load salt
            from scripts.utilities.backup_database import _decrypt_file, _get_or_create_salt, SALT_FILE
            salt_path = PROJECT_ROOT / SALT_FILE
            if not salt_path.exists():
                return {
                    'status': 'error',
                    'error': f'Backup salt file not found: {salt_path}. '
                             f'Cannot decrypt without the original salt.',
                }
            salt = salt_path.read_bytes()

            # Decrypt
            try:
                decrypted_bytes = _decrypt_file(enc_file, passphrase, salt)
            except Exception:
                return {
                    'status': 'error',
                    'error': 'Decryption failed -- wrong passphrase or corrupted file.',
                }

            # Write decrypted content to a temp file
            decrypted_dir = os.path.join(backup_dir, 'decrypted')
            os.makedirs(decrypted_dir, exist_ok=True)
            decrypted_path = os.path.join(decrypted_dir, 'env_restored')
            with open(decrypted_path, 'wb') as f:
                f.write(decrypted_bytes)

            print(f"   [OK] Decrypted .env written to: {decrypted_path}")

            # Parse and compare
            changes = self._compare_env_files(
                current_path=os.path.join(str(PROJECT_ROOT), '.env'),
                backup_content=decrypted_bytes.decode('utf-8', errors='replace'),
            )

            if changes:
                print(f"\n   [DIFF] Changes between current .env and backup:")
                for change in changes:
                    print(f"      {change}")
            else:
                print(f"   [OK] No differences found between current .env and backup")

            print(f"\n   [INFO] To restore the backed-up .env:")
            print(f"   1. Review the decrypted file: {decrypted_path}")
            print(f"   2. Manually copy it to: {os.path.join(str(PROJECT_ROOT), '.env')}")
            print(f"   3. Delete the decrypted file after copying")
            print(f"\n   [WARN] Auto-overwrite is disabled for safety.")

            logger.info("Env backup decrypted for review",
                       backup_dir=backup_dir)

            return {
                'status': 'success',
                'changes': changes,
                'decrypted_path': decrypted_path,
            }

        except Exception as e:
            try:
                msg = str(e)
            except UnicodeEncodeError:
                msg = ascii(e)
            print(f"[ERROR] Env restore failed: {msg}")
            logger.error("Env restore failed", error=str(e))
            return {
                'status': 'error',
                'error': str(e),
            }

    def restore_full(self, backup_dir: str, passphrase: str) -> dict:
        """
        Restore both database and .env from a full backup directory.

        Calls restore_database() for the DB part and restore_env() for
        the .env part.

        Args:
            backup_dir: Path to the full backup directory (full_YYYY-MM-DD_HHMMSS)
            passphrase: Passphrase used when the backup was created

        Returns:
            dict with status, db_result, env_result
        """
        print(f"[RESTORE] Starting full restore from: {backup_dir}")
        print()

        # Restore database
        db_result = self.restore_database(backup_dir)
        print()

        # Restore .env
        env_result = self.restore_env(backup_dir, passphrase)
        print()

        # Also check for tastytrade_session backup
        session_enc = os.path.join(backup_dir, 'tastytrade_session_backup.enc')
        session_result = None
        if os.path.exists(session_enc):
            print(f"[INFO] Encrypted .tastytrade_session backup found: {session_enc}")
            print(f"   To decrypt, use the same passphrase with the backup_database module.")
            try:
                from scripts.utilities.backup_database import _decrypt_file, SALT_FILE
                salt_path = PROJECT_ROOT / SALT_FILE
                if salt_path.exists():
                    salt = salt_path.read_bytes()
                    decrypted_bytes = _decrypt_file(session_enc, passphrase, salt)
                    decrypted_dir = os.path.join(backup_dir, 'decrypted')
                    os.makedirs(decrypted_dir, exist_ok=True)
                    session_dest = os.path.join(decrypted_dir, 'tastytrade_session_restored')
                    with open(session_dest, 'wb') as f:
                        f.write(decrypted_bytes)
                    print(f"   [OK] Decrypted session written to: {session_dest}")
                    print(f"   To restore, copy to: {os.path.join(str(PROJECT_ROOT), '.tastytrade_session')}")
                    session_result = {'status': 'success', 'decrypted_path': session_dest}
            except Exception as e:
                try:
                    msg = str(e)
                except UnicodeEncodeError:
                    msg = ascii(e)
                print(f"   [WARN] Could not decrypt session file: {msg}")
                session_result = {'status': 'error', 'error': str(e)}

        overall_status = 'success' if db_result.get('status') == 'success' else 'partial'
        if env_result.get('status') != 'success':
            overall_status = 'partial' if overall_status == 'success' else overall_status

        return {
            'status': overall_status,
            'db_result': db_result,
            'env_result': env_result,
            'session_result': session_result,
        }

    def _resolve_db_path(self, backup_path: str) -> Optional[str]:
        """
        Resolve the actual .db file path from a backup_path.

        If backup_path is a .db file, return it directly.
        If it's a full backup directory, look for tovito_backup.db inside it.

        Args:
            backup_path: Path to a .db file or full backup directory

        Returns:
            Path to the .db file, or None if not found
        """
        p = Path(backup_path)

        if p.is_file() and p.suffix == '.db':
            return str(p)

        if p.is_dir():
            db_file = p / 'tovito_backup.db'
            if db_file.exists():
                return str(db_file)
            # Also check for any .db file in the directory
            for f in p.iterdir():
                if f.suffix == '.db' and f.is_file():
                    return str(f)

        return None

    def _compare_env_files(self, current_path: str,
                           backup_content: str) -> list:
        """
        Compare current .env with backed-up content, masking all values.

        Shows which keys were added, removed, or changed (values are masked).

        Args:
            current_path: Path to the current .env file
            backup_content: String content of the backed-up .env

        Returns:
            List of human-readable change descriptions
        """
        changes = []

        # Parse both into key-value dicts (ignoring comments and blank lines)
        current_vars = self._parse_env_content(
            self._read_file_safe(current_path)
        )
        backup_vars = self._parse_env_content(backup_content)

        all_keys = sorted(set(list(current_vars.keys()) + list(backup_vars.keys())))

        for key in all_keys:
            in_current = key in current_vars
            in_backup = key in backup_vars

            if in_current and not in_backup:
                changes.append(f"  [REMOVED in backup] {key}=***")
            elif not in_current and in_backup:
                changes.append(f"  [ADDED in backup]   {key}=***")
            elif in_current and in_backup:
                if current_vars[key] != backup_vars[key]:
                    changes.append(f"  [CHANGED]           {key}=*** -> ***")

        return changes

    def _parse_env_content(self, content: str) -> dict:
        """
        Parse .env file content into a dict of key-value pairs.

        Ignores comments (#) and blank lines.

        Args:
            content: String content of a .env file

        Returns:
            Dict of environment variable names to values
        """
        result = {}
        if not content:
            return result

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, _, value = line.partition('=')
                result[key.strip()] = value.strip()
        return result

    def _read_file_safe(self, filepath: str) -> str:
        """Read a file's content, returning empty string if it doesn't exist."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except (FileNotFoundError, PermissionError):
            return ''


def _print_backup_list(backups: list):
    """Pretty-print a list of backups."""
    if not backups:
        print("[INFO] No backups found")
        return

    print(f"\n{'='*70}")
    print("AVAILABLE BACKUPS")
    print(f"{'='*70}\n")

    for i, backup in enumerate(backups, 1):
        btype = backup.get('type', 'simple')
        type_label = '[FULL]' if btype == 'full' else '[DB]  '
        size_kb = backup['size_bytes'] / 1024
        date_str = backup['modified'].strftime('%Y-%m-%d %H:%M:%S')

        print(f"  {i:2d}. {type_label} {backup['filename']}")
        print(f"      Date: {date_str}  |  Size: {size_kb:.1f} KB")
        print(f"      Path: {backup['path']}")
        print()

    print(f"{'='*70}")
    print(f"Total: {len(backups)} backup(s)")
    print(f"{'='*70}\n")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Restore Tovito database from backup')
    parser.add_argument('--list', action='store_true',
                        help='List all available backups')
    parser.add_argument('--restore', type=str, default=None, metavar='PATH',
                        help='Restore database from specific backup file or directory')
    parser.add_argument('--latest', action='store_true',
                        help='Restore from the most recent backup')
    parser.add_argument('--full', type=str, default=None, metavar='DIR',
                        help='Full restore (DB + .env) from a full backup directory')
    parser.add_argument('--passphrase', type=str, default=None,
                        help='Passphrase for decrypting sensitive files in full restore')
    parser.add_argument('--verify', type=str, default=None, metavar='PATH',
                        help='Verify backup integrity without restoring')
    parser.add_argument('--target', type=str, default=None, metavar='PATH',
                        help='Custom restore target path (default: data/tovito.db)')

    args = parser.parse_args()

    restore_mgr = DatabaseRestore()

    if args.list:
        backups = restore_mgr.list_available_backups()
        _print_backup_list(backups)

    elif args.verify:
        print(f"[VERIFY] Checking backup: {args.verify}")
        from scripts.utilities.backup_database import DatabaseBackup
        verify_mgr = DatabaseBackup()
        result = verify_mgr.verify_backup(args.verify)
        for detail in result.get('details', []):
            print(f"   {detail}")
        if result['status'] == 'ok':
            print(f"[OK] Backup is valid")
            sys.exit(0)
        else:
            print(f"[ERROR] Backup is corrupted or invalid")
            sys.exit(1)

    elif args.latest:
        backups = restore_mgr.list_available_backups()
        if not backups:
            print("[ERROR] No backups found")
            sys.exit(1)

        latest = backups[0]
        print(f"[INFO] Most recent backup: {latest['filename']}")
        print(f"   Date: {latest['modified'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Type: {latest.get('type', 'simple')}")
        print(f"   Size: {latest['size_bytes'] / 1024:.1f} KB")
        print()

        result = restore_mgr.restore_database(
            latest['path'],
            target_path=args.target,
        )

        if result['status'] == 'success':
            print(f"\n[OK] Restore complete!")
            sys.exit(0)
        else:
            print(f"\n[ERROR] Restore failed: {result.get('error')}")
            sys.exit(1)

    elif args.full:
        if not args.passphrase:
            print("[ERROR] --passphrase is required for full restore")
            print("   Usage: --full BACKUP_DIR --passphrase YOUR_PASSPHRASE")
            sys.exit(1)

        if not os.path.isdir(args.full):
            print(f"[ERROR] Not a directory: {args.full}")
            sys.exit(1)

        result = restore_mgr.restore_full(args.full, args.passphrase)

        if result['status'] == 'success':
            print(f"\n[OK] Full restore complete!")
            sys.exit(0)
        elif result['status'] == 'partial':
            print(f"\n[WARN] Partial restore -- some components had issues")
            sys.exit(1)
        else:
            print(f"\n[ERROR] Full restore failed")
            sys.exit(1)

    elif args.restore:
        if not os.path.exists(args.restore):
            print(f"[ERROR] Backup path not found: {args.restore}")
            sys.exit(1)

        result = restore_mgr.restore_database(
            args.restore,
            target_path=args.target,
        )

        if result['status'] == 'success':
            print(f"\n[OK] Restore complete!")
            sys.exit(0)
        else:
            print(f"\n[ERROR] Restore failed: {result.get('error')}")
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
