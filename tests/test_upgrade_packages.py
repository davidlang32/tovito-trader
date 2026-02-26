"""
Tests for Package Upgrade Script
=================================

Tests the PackageUpgrader class: environment checks, backup/rollback,
pip/npm upgrade logic, test suite parsing, and summary generation.
"""

import pytest
import sys
import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.devops.upgrade_packages import PackageUpgrader


# ============================================================
# Environment Check Tests
# ============================================================

class TestCheckEnvironment:
    """Tests for the production safety guard."""

    def test_check_environment_dev(self):
        """TOVITO_ENV=development returns True."""
        upgrader = PackageUpgrader()
        with patch.dict(os.environ, {'TOVITO_ENV': 'development'}):
            assert upgrader.check_environment() is True

    def test_check_environment_production(self, capsys):
        """TOVITO_ENV=production returns False and prints error."""
        upgrader = PackageUpgrader()
        with patch.dict(os.environ, {'TOVITO_ENV': 'production'}):
            assert upgrader.check_environment() is False
        captured = capsys.readouterr()
        assert '[ERROR]' in captured.out
        assert 'production' in captured.out.lower()

    def test_check_environment_default(self):
        """Unset TOVITO_ENV defaults to development (returns True)."""
        upgrader = PackageUpgrader()
        env = os.environ.copy()
        env.pop('TOVITO_ENV', None)
        with patch.dict(os.environ, env, clear=True):
            assert upgrader.check_environment() is True


# ============================================================
# Backup Tests
# ============================================================

class TestPreUpgradeBackup:
    """Tests for snapshot creation."""

    def test_pre_upgrade_backup_creates_snapshot(self, tmp_path):
        """Verify snapshot directory is created with dependency files."""
        # Set up a fake project structure
        project = tmp_path / 'project'
        project.mkdir()

        # Create requirements files
        (project / 'requirements.txt').write_text('fastapi>=0.104.0\n')
        (project / 'requirements-full.txt').write_text('fastapi>=0.104.0\nstreamlit>=1.28.0\n')

        # Create frontend directory with package files
        frontend = project / 'apps' / 'investor_portal' / 'frontend' / 'investor_portal'
        frontend.mkdir(parents=True)
        (frontend / 'package.json').write_text('{"name": "test"}\n')
        (frontend / 'package-lock.json').write_text('{"lockfileVersion": 3}\n')

        upgrader = PackageUpgrader(project_root=project)

        # Patch the import inside pre_upgrade_backup so it does not access real DB
        with patch.dict('sys.modules', {'scripts.utilities.backup_database': MagicMock(
            DatabaseBackup=MagicMock(side_effect=ImportError('no db'))
        )}):
            result = upgrader.pre_upgrade_backup()

        assert 'snapshot_dir' in result
        snap = Path(result['snapshot_dir'])
        assert snap.exists()
        assert 'requirements.txt' in result['files_copied']
        assert 'requirements-full.txt' in result['files_copied']
        assert 'package.json' in result['files_copied']
        assert 'package-lock.json' in result['files_copied']

        # Verify actual files were copied
        assert (snap / 'requirements.txt').exists()
        assert (snap / 'requirements-full.txt').exists()
        assert (snap / 'package.json').exists()


# ============================================================
# Outdated Package Discovery Tests
# ============================================================

class TestGetOutdatedPackages:
    """Tests for pip outdated parsing."""

    def test_get_outdated_packages_mock(self):
        """Mock subprocess and verify parsing and classification."""
        upgrader = PackageUpgrader()

        mock_output = json.dumps([
            {'name': 'fastapi', 'version': '0.104.0', 'latest_version': '0.110.0'},
            {'name': 'requests', 'version': '2.31.0', 'latest_version': '2.31.1'},
            {'name': 'sqlalchemy', 'version': '1.4.0', 'latest_version': '2.0.0'},
        ])

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = mock_output

        with patch('scripts.devops.upgrade_packages.subprocess.run', return_value=mock_result):
            packages = upgrader.get_outdated_packages()

        assert len(packages) == 3

        fa = next(p for p in packages if p['name'] == 'fastapi')
        assert fa['current'] == '0.104.0'
        assert fa['latest'] == '0.110.0'
        assert fa['upgrade_type'] == 'minor'

        req = next(p for p in packages if p['name'] == 'requests')
        assert req['upgrade_type'] == 'patch'

        sa = next(p for p in packages if p['name'] == 'sqlalchemy')
        assert sa['upgrade_type'] == 'major'


# ============================================================
# Pip Upgrade Tests
# ============================================================

class TestUpgradePipPackages:
    """Tests for pip upgrade execution."""

    def test_upgrade_pip_dry_run(self, capsys):
        """Dry run does not call pip install."""
        upgrader = PackageUpgrader()

        outdated = [
            {'name': 'fastapi', 'current': '0.104.0', 'latest': '0.110.0', 'upgrade_type': 'minor'},
        ]

        with patch.object(upgrader, 'get_outdated_packages', return_value=outdated):
            with patch('scripts.devops.upgrade_packages.subprocess.run') as mock_run:
                result = upgrader.upgrade_pip_packages(all_minor=True, dry_run=True)

        # subprocess.run should NOT have been called (no pip install)
        mock_run.assert_not_called()
        assert len(result['upgraded']) == 1
        assert result['upgraded'][0]['name'] == 'fastapi'

        captured = capsys.readouterr()
        assert 'DRY-RUN' in captured.out

    def test_upgrade_pip_success(self):
        """Mock subprocess success and verify result dict."""
        upgrader = PackageUpgrader()

        outdated = [
            {'name': 'uvicorn', 'current': '0.24.0', 'latest': '0.25.0', 'upgrade_type': 'minor'},
            {'name': 'pydantic', 'current': '2.5.0', 'latest': '2.6.0', 'upgrade_type': 'minor'},
        ]

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'Successfully installed'

        with patch.object(upgrader, 'get_outdated_packages', return_value=outdated):
            with patch('scripts.devops.upgrade_packages.subprocess.run', return_value=mock_result):
                result = upgrader.upgrade_pip_packages(all_minor=True)

        assert len(result['upgraded']) == 2
        assert len(result['failed']) == 0
        names = [p['name'] for p in result['upgraded']]
        assert 'uvicorn' in names
        assert 'pydantic' in names


# ============================================================
# Test Suite Runner Tests
# ============================================================

class TestRunTestSuite:
    """Tests for pytest output parsing."""

    def test_run_test_suite_parse_output(self):
        """Mock pytest output and verify pass/fail parsing."""
        upgrader = PackageUpgrader()

        mock_stdout = (
            'tests/test_nav.py::test_basic PASSED\n'
            'tests/test_nav.py::test_edge PASSED\n'
            'tests/test_db.py::test_fail FAILED\n'
            '\n'
            '========== 805 passed, 1 failed in 42.30s ==========\n'
        )

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = mock_stdout

        with patch('scripts.devops.upgrade_packages.subprocess.run', return_value=mock_result):
            result = upgrader.run_test_suite()

        assert result['passed'] == 805
        assert result['failed'] == 1
        assert result['errors'] == 0
        assert result['total'] == 806
        assert result['exit_code'] == 1
        assert isinstance(result['output_tail'], list)


# ============================================================
# Requirements File Update Tests
# ============================================================

class TestUpdateRequirementsFiles:
    """Tests for in-place version constraint updates."""

    def test_update_requirements_files(self, tmp_path):
        """Verify version constraint is updated in requirements file."""
        project = tmp_path / 'project'
        project.mkdir()

        req_content = (
            '# Core API\n'
            'fastapi>=0.104.0\n'
            'uvicorn[standard]>=0.24.0\n'
            'pydantic>=2.5.0\n'
        )
        (project / 'requirements.txt').write_text(req_content)
        (project / 'requirements-full.txt').write_text(
            'fastapi>=0.104.0\nstreamlit>=1.28.0\n'
        )

        upgrader = PackageUpgrader(project_root=project)
        upgraded = [
            {'name': 'fastapi', 'latest': '0.110.0'},
            {'name': 'pydantic', 'latest': '2.6.1'},
            {'name': 'some-transitive-dep', 'latest': '3.0.0'},  # not in file
        ]
        modified = upgrader.update_requirements_files(upgraded)

        assert 'requirements.txt' in modified
        assert 'requirements-full.txt' in modified

        updated_req = (project / 'requirements.txt').read_text()
        assert 'fastapi>=0.110.0' in updated_req
        assert 'pydantic>=2.6.1' in updated_req
        # uvicorn should be untouched
        assert 'uvicorn[standard]>=0.24.0' in updated_req

        updated_full = (project / 'requirements-full.txt').read_text()
        assert 'fastapi>=0.110.0' in updated_full
        # streamlit untouched
        assert 'streamlit>=1.28.0' in updated_full


# ============================================================
# Rollback Tests
# ============================================================

class TestRollback:
    """Tests for snapshot restoration."""

    def test_rollback_restores_files(self, tmp_path):
        """Verify files are restored from a snapshot directory."""
        project = tmp_path / 'project'
        project.mkdir()

        # Create current (post-upgrade) requirements
        (project / 'requirements.txt').write_text('fastapi>=0.110.0\n')
        (project / 'requirements-full.txt').write_text('fastapi>=0.110.0\n')

        # Create frontend dir
        frontend = project / 'apps' / 'investor_portal' / 'frontend' / 'investor_portal'
        frontend.mkdir(parents=True)
        (frontend / 'package.json').write_text('{"version": "new"}\n')

        # Create a snapshot with old versions
        snap_dir = project / 'data' / 'devops' / 'upgrade_snapshots' / '2026-02-26_150000'
        snap_dir.mkdir(parents=True)
        (snap_dir / 'requirements.txt').write_text('fastapi>=0.104.0\n')
        (snap_dir / 'requirements-full.txt').write_text('fastapi>=0.104.0\n')
        (snap_dir / 'package.json').write_text('{"version": "old"}\n')

        upgrader = PackageUpgrader(project_root=project)

        # Mock pip install and npm install so they don't actually run
        with patch('scripts.devops.upgrade_packages.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with patch('scripts.devops.upgrade_packages.shutil.which', return_value='/usr/bin/npm'):
                result = upgrader.rollback('2026-02-26_150000')

        assert result['status'] == 'success'
        assert 'requirements.txt' in result['restored']

        # Verify the files were restored to old content
        assert 'fastapi>=0.104.0' in (project / 'requirements.txt').read_text()
        assert 'fastapi>=0.104.0' in (project / 'requirements-full.txt').read_text()
        assert '"old"' in (frontend / 'package.json').read_text()


# ============================================================
# Summary Generation Tests
# ============================================================

class TestGenerateUpgradeSummary:
    """Tests for the formatted summary output."""

    def test_generate_upgrade_summary_success(self, capsys):
        """Verify next steps shown when all tests pass."""
        upgrader = PackageUpgrader()

        snapshot = {'snapshot_dir': 'data/devops/upgrade_snapshots/2026-02-26_150000'}
        pip_results = {
            'upgraded': [
                {'name': 'fastapi', 'current': '0.104.0', 'latest': '0.110.0', 'upgrade_type': 'minor'},
                {'name': 'requests', 'current': '2.31.0', 'latest': '2.31.1', 'upgrade_type': 'patch'},
            ],
            'failed': [],
            'skipped': [
                {'name': 'sqlalchemy', 'current': '1.4.0', 'latest': '2.0.0', 'upgrade_type': 'major'},
            ],
        }
        npm_results = {'upgraded': [], 'failed': [], 'skipped': []}
        test_results = {
            'passed': 806,
            'failed': 0,
            'errors': 0,
            'total': 806,
            'duration_seconds': 45.2,
            'output_tail': [],
            'exit_code': 0,
        }

        upgrader.generate_upgrade_summary(snapshot, pip_results, npm_results, test_results)
        captured = capsys.readouterr()

        assert 'UPGRADE SUMMARY' in captured.out
        assert 'Upgraded: 2' in captured.out
        assert 'Failed:   0' in captured.out
        assert 'Skipped:  1' in captured.out
        assert 'Passed:  806' in captured.out
        assert '[OK] ALL TESTS PASSED' in captured.out
        assert 'NEXT STEPS' in captured.out
        assert 'git add' in captured.out
        assert 'railway up' in captured.out

    def test_generate_upgrade_summary_failure(self, capsys):
        """Verify rollback command shown when tests fail."""
        upgrader = PackageUpgrader()

        snapshot = {'snapshot_dir': 'data/devops/upgrade_snapshots/2026-02-26_160000'}
        pip_results = {
            'upgraded': [
                {'name': 'fastapi', 'current': '0.104.0', 'latest': '0.110.0', 'upgrade_type': 'minor'},
            ],
            'failed': [],
            'skipped': [],
        }
        test_results = {
            'passed': 800,
            'failed': 6,
            'errors': 0,
            'total': 806,
            'duration_seconds': 44.0,
            'output_tail': [],
            'exit_code': 1,
        }

        upgrader.generate_upgrade_summary(snapshot, pip_results, None, test_results)
        captured = capsys.readouterr()

        assert 'UPGRADE SUMMARY' in captured.out
        assert '[ERROR] TESTS FAILED' in captured.out
        assert 'NOT safe to promote' in captured.out
        assert '--rollback' in captured.out
        assert '2026-02-26_160000' in captured.out
        # Should NOT show next steps for deployment
        assert 'railway up' not in captured.out
