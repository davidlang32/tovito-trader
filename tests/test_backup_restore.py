"""
Tests for Backup & Restore Enhancement (Phase 20C)
===================================================
Tests for full backup, verification, rotation, and restore functionality.
"""

import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.utilities.backup_database import DatabaseBackup


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def backup_env(tmp_path):
    """Create a minimal environment for backup testing."""
    # Create a test database
    db_path = tmp_path / "data" / "tovito.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO test VALUES (1, 'hello')")
    conn.commit()
    conn.close()

    # Create a test .env file
    env_path = tmp_path / ".env"
    env_path.write_text("SECRET_KEY=test123\nDB_PATH=data/tovito.db\n")

    # Create backup directory
    backup_dir = tmp_path / "data" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Create DatabaseBackup instance with test paths
    backup = DatabaseBackup()
    backup.db_path = str(db_path)
    backup.backup_dir = str(backup_dir)
    backup.project_root = tmp_path

    return {
        "backup": backup,
        "db_path": db_path,
        "env_path": env_path,
        "backup_dir": backup_dir,
        "tmp_path": tmp_path,
    }


# ---------------------------------------------------------------------------
# Test: Simple backup (existing functionality)
# ---------------------------------------------------------------------------

class TestSimpleBackup:
    """Test existing create_backup() functionality."""

    def test_create_backup_success(self, backup_env):
        result = backup_env["backup"].create_backup()
        assert result["status"] == "success"
        assert Path(result["backup_path"]).exists()
        assert result["size_bytes"] > 0

    def test_create_backup_missing_db(self, backup_env):
        backup_env["backup"].db_path = "/nonexistent/path.db"
        result = backup_env["backup"].create_backup()
        assert result["status"] == "error"

    def test_list_backups_empty(self, backup_env):
        backups = backup_env["backup"].list_backups()
        assert backups == []

    def test_list_backups_after_create(self, backup_env):
        backup_env["backup"].create_backup()
        backups = backup_env["backup"].list_backups()
        assert len(backups) >= 1
        assert backups[0]["filename"].startswith("tovito_backup_")


# ---------------------------------------------------------------------------
# Test: Full backup
# ---------------------------------------------------------------------------

class TestFullBackup:
    """Test create_full_backup() with encrypted .env."""

    def test_full_backup_without_passphrase(self, backup_env):
        """Without passphrase, should still backup DB but skip .env."""
        b = backup_env["backup"]
        b.project_root = backup_env["tmp_path"]
        result = b.create_full_backup()
        assert result["status"] == "success"
        assert Path(result["backup_dir"]).exists()
        # Manifest should exist
        manifest_path = Path(result["backup_dir"]) / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert manifest["backup_type"] == "full"
        # DB should be present
        db_files = [f for f in manifest["files"] if f["filename"] == "tovito_backup.db"]
        assert len(db_files) == 1

    def test_full_backup_with_passphrase(self, backup_env):
        """With passphrase, should backup and encrypt .env."""
        b = backup_env["backup"]
        b.project_root = backup_env["tmp_path"]
        result = b.create_full_backup(passphrase="test-passphrase-123")
        assert result["status"] == "success"
        manifest_path = Path(result["backup_dir"]) / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        # Should have encrypted env file
        enc_files = [f for f in manifest["files"] if f.get("encrypted")]
        assert len(enc_files) >= 1

    def test_full_backup_creates_timestamped_dir(self, backup_env):
        """Backup directory should be named full_YYYY-MM-DD_HHMMSS."""
        b = backup_env["backup"]
        b.project_root = backup_env["tmp_path"]
        result = b.create_full_backup()
        dir_name = Path(result["backup_dir"]).name
        assert dir_name.startswith("full_")


# ---------------------------------------------------------------------------
# Test: Verify backup
# ---------------------------------------------------------------------------

class TestVerifyBackup:
    """Test verify_backup() integrity checking."""

    def test_verify_simple_backup_ok(self, backup_env):
        """Verify a valid .db backup passes integrity check."""
        result = backup_env["backup"].create_backup()
        verify = backup_env["backup"].verify_backup(result["backup_path"])
        assert verify["status"] == "ok"

    def test_verify_corrupted_backup(self, backup_env, tmp_path):
        """Verify a corrupted file is detected."""
        bad_file = tmp_path / "corrupted.db"
        bad_file.write_bytes(b"not a database at all")
        verify = backup_env["backup"].verify_backup(str(bad_file))
        assert verify["status"] == "corrupted"

    def test_verify_missing_backup(self, backup_env):
        """Verify a nonexistent path is reported."""
        verify = backup_env["backup"].verify_backup("/nonexistent/backup.db")
        assert verify["status"] == "corrupted"

    def test_verify_full_backup_ok(self, backup_env):
        """Verify a full backup directory passes all checks."""
        b = backup_env["backup"]
        b.project_root = backup_env["tmp_path"]
        result = b.create_full_backup()
        verify = b.verify_backup(result["backup_dir"])
        assert verify["status"] == "ok"


# ---------------------------------------------------------------------------
# Test: Rotate backups
# ---------------------------------------------------------------------------

class TestRotateBackups:
    """Test rotate_backups() cleanup logic."""

    def test_rotate_keeps_recent(self, backup_env):
        """Recent backups should not be removed."""
        b = backup_env["backup"]
        # Create 3 backups with distinct timestamps (same-second creates overwrite)
        for i in range(3):
            backup_path = Path(b.backup_dir) / f"tovito_backup_2026-02-{24+i:02d}_120000.db"
            shutil.copy2(b.db_path, str(backup_path))
        result = b.rotate_backups(keep_count=5, keep_days=90)
        assert result["removed_count"] == 0
        assert result["remaining_count"] >= 3

    def test_rotate_removes_excess(self, backup_env):
        """Excess backups beyond keep_count should be removed."""
        b = backup_env["backup"]
        # Create 5 backups with different timestamps
        for i in range(5):
            backup_path = Path(b.backup_dir) / f"tovito_backup_2026-01-{10+i:02d}_120000.db"
            shutil.copy2(b.db_path, str(backup_path))
        result = b.rotate_backups(keep_count=2, keep_days=0)
        assert result["removed_count"] >= 2  # Should remove at least some
        assert result["remaining_count"] >= 2  # Should keep at least 2

    def test_rotate_always_keeps_oldest(self, backup_env):
        """The oldest backup should never be removed (baseline)."""
        b = backup_env["backup"]
        # Create 3 backups
        oldest = Path(b.backup_dir) / "tovito_backup_2025-01-01_120000.db"
        shutil.copy2(b.db_path, str(oldest))
        for i in range(3):
            path = Path(b.backup_dir) / f"tovito_backup_2026-02-{20+i:02d}_120000.db"
            shutil.copy2(b.db_path, str(path))
        result = b.rotate_backups(keep_count=1, keep_days=0)
        # Oldest should still exist
        assert oldest.exists()

    def test_rotate_empty_dir(self, backup_env):
        """Rotating with no backups should be a no-op."""
        result = backup_env["backup"].rotate_backups()
        assert result["removed_count"] == 0
        assert result["remaining_count"] == 0


# ---------------------------------------------------------------------------
# Test: Restore database
# ---------------------------------------------------------------------------

class TestRestoreDatabase:
    """Test restore functionality."""

    def test_restore_creates_safety_backup(self, backup_env):
        """Restoring should first create a safety backup of current DB."""
        b = backup_env["backup"]
        # Create a backup to restore from
        create_result = b.create_backup()
        backup_path = create_result["backup_path"]

        # Import and test restore
        from scripts.utilities.restore_database import DatabaseRestore
        restorer = DatabaseRestore()
        restorer.db_path = b.db_path
        restorer.backup_dir = b.backup_dir

        result = restorer.restore_database(backup_path)
        assert result["status"] == "success"
        assert result.get("safety_backup_path") is not None
        assert Path(result["safety_backup_path"]).exists()

    def test_restore_from_invalid_path(self, backup_env):
        """Restoring from nonexistent file should fail gracefully."""
        from scripts.utilities.restore_database import DatabaseRestore
        restorer = DatabaseRestore()
        restorer.db_path = backup_env["backup"].db_path
        restorer.backup_dir = backup_env["backup"].backup_dir

        result = restorer.restore_database("/nonexistent/backup.db")
        assert result["status"] == "error"

    def test_list_available_backups(self, backup_env):
        """List should show both simple and full backups."""
        b = backup_env["backup"]
        b.create_backup()

        from scripts.utilities.restore_database import DatabaseRestore
        restorer = DatabaseRestore()
        restorer.backup_dir = b.backup_dir

        backups = restorer.list_available_backups()
        assert len(backups) >= 1


# ---------------------------------------------------------------------------
# Test: Manifest checksums
# ---------------------------------------------------------------------------

class TestManifestChecksums:
    """Test manifest.json integrity features."""

    def test_manifest_has_checksums(self, backup_env):
        """Full backup manifest should include SHA256 checksums."""
        b = backup_env["backup"]
        b.project_root = backup_env["tmp_path"]
        result = b.create_full_backup()
        manifest_path = Path(result["backup_dir"]) / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        for file_info in manifest["files"]:
            assert "sha256" in file_info
            assert len(file_info["sha256"]) == 64  # SHA256 hex digest length

    def test_manifest_timestamp(self, backup_env):
        """Manifest should include a timestamp."""
        b = backup_env["backup"]
        b.project_root = backup_env["tmp_path"]
        result = b.create_full_backup()
        manifest_path = Path(result["backup_dir"]) / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        assert "timestamp" in manifest
