"""
Tests for the Dependency Monitor script.

Covers version classification, report generation, text/Discord formatting,
pip/npm subprocess mocking, report persistence, and notification logic.
"""

import pytest
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.devops.dependency_monitor import DependencyMonitor


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def monitor(tmp_path):
    """DependencyMonitor instance with report_dir set to a temp directory."""
    m = DependencyMonitor(project_root=tmp_path)
    m.report_dir = tmp_path / "reports"
    m.report_dir.mkdir(parents=True, exist_ok=True)
    return m


@pytest.fixture
def sample_pip_results():
    """Sample pip outdated results for testing."""
    return [
        {
            "name": "requests",
            "current": "2.28.0",
            "latest": "3.0.0",
            "constraint": True,
            "requirements_file": "requirements-full.txt",
            "upgrade_type": "major",
        },
        {
            "name": "fastapi",
            "current": "0.100.0",
            "latest": "0.110.0",
            "constraint": True,
            "requirements_file": "requirements.txt",
            "upgrade_type": "minor",
        },
        {
            "name": "click",
            "current": "8.1.3",
            "latest": "8.1.7",
            "constraint": False,
            "requirements_file": "",
            "upgrade_type": "patch",
        },
    ]


@pytest.fixture
def sample_npm_results():
    """Sample npm outdated results for testing."""
    return [
        {
            "name": "react",
            "current": "18.2.0",
            "wanted": "18.3.0",
            "latest": "19.0.0",
            "upgrade_type": "major",
        },
        {
            "name": "vite",
            "current": "5.0.0",
            "wanted": "5.1.0",
            "latest": "5.1.0",
            "upgrade_type": "minor",
        },
    ]


# ============================================================
# classify_upgrade tests
# ============================================================

class TestClassifyUpgrade:
    """Tests for the static classify_upgrade method."""

    def test_classify_upgrade_major(self):
        result = DependencyMonitor.classify_upgrade("1.0.0", "2.0.0")
        assert result == "major"

    def test_classify_upgrade_minor(self):
        result = DependencyMonitor.classify_upgrade("1.0.0", "1.1.0")
        assert result == "minor"

    def test_classify_upgrade_patch(self):
        result = DependencyMonitor.classify_upgrade("1.0.0", "1.0.1")
        assert result == "patch"

    def test_classify_upgrade_invalid(self):
        result = DependencyMonitor.classify_upgrade("not.a.version", "also.bad")
        assert result == "unknown"


# ============================================================
# generate_report tests
# ============================================================

class TestGenerateReport:
    """Tests for the generate_report method."""

    def test_generate_report_with_data(self, monitor, sample_pip_results, sample_npm_results):
        report = monitor.generate_report(sample_pip_results, sample_npm_results)

        assert "timestamp" in report
        assert report["pip_outdated_count"] == 3
        assert report["npm_outdated_count"] == 2
        assert report["pip_major"] == 1
        assert report["pip_minor"] == 1
        assert report["pip_patch"] == 1
        assert report["npm_major"] == 1
        assert report["npm_minor"] == 1
        assert report["npm_patch"] == 0
        assert len(report["pip_packages"]) == 3
        assert len(report["npm_packages"]) == 2

    def test_generate_report_empty(self, monitor):
        report = monitor.generate_report([], [])

        assert report["pip_outdated_count"] == 0
        assert report["npm_outdated_count"] == 0
        assert report["pip_major"] == 0
        assert report["pip_minor"] == 0
        assert report["pip_patch"] == 0
        assert report["npm_major"] == 0
        assert report["npm_minor"] == 0
        assert report["npm_patch"] == 0
        assert report["pip_packages"] == []
        assert report["npm_packages"] == []


# ============================================================
# format_text_report tests
# ============================================================

class TestFormatTextReport:
    """Tests for the format_text_report method."""

    def test_format_text_report_structure(self, monitor, sample_pip_results, sample_npm_results):
        report = monitor.generate_report(sample_pip_results, sample_npm_results)
        text = monitor.format_text_report(report)

        assert "DEPENDENCY UPDATE REPORT" in text
        assert "[REPORT] Summary" in text
        assert "Python (pip)" in text
        assert "Node (npm)" in text
        assert "[MAJOR]" in text
        assert "[MINOR]" in text
        assert "[PATCH]" in text
        assert "requests" in text
        assert "react" in text


# ============================================================
# format_discord_embed tests
# ============================================================

class TestFormatDiscordEmbed:
    """Tests for the format_discord_embed method."""

    def test_format_discord_embed_outdated(self, monitor, sample_pip_results, sample_npm_results):
        report = monitor.generate_report(sample_pip_results, sample_npm_results)
        embed = monitor.format_discord_embed(report)

        assert embed["title"] == "Dependency Update Report"
        assert embed["color"] == 0xFFD600  # gold
        assert len(embed["fields"]) >= 2
        assert "Top Major Updates" in [f["name"] for f in embed["fields"]]

    def test_format_discord_embed_current(self, monitor):
        report = monitor.generate_report([], [])
        embed = monitor.format_discord_embed(report)

        assert embed["color"] == 0x00C853  # green
        assert "up to date" in embed["description"]


# ============================================================
# check_pip_packages tests
# ============================================================

class TestCheckPipPackages:
    """Tests for the check_pip_packages method."""

    @patch("subprocess.run")
    def test_check_pip_packages_with_mock(self, mock_run, monitor):
        pip_json = json.dumps([
            {"name": "requests", "version": "2.28.0", "latest_version": "3.0.0"},
            {"name": "click", "version": "8.1.3", "latest_version": "8.1.7"},
        ])
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=pip_json,
            stderr="",
        )

        results = monitor.check_pip_packages()

        assert len(results) == 2
        assert results[0]["name"] == "requests"
        assert results[0]["current"] == "2.28.0"
        assert results[0]["latest"] == "3.0.0"
        assert results[0]["upgrade_type"] == "major"
        assert results[1]["upgrade_type"] == "patch"


# ============================================================
# check_npm_packages tests
# ============================================================

class TestCheckNpmPackages:
    """Tests for the check_npm_packages method."""

    @patch("subprocess.run")
    def test_check_npm_packages_with_mock(self, mock_run, monitor, tmp_path):
        # Ensure the frontend_dir exists for the check
        monitor.frontend_dir = tmp_path / "frontend"
        monitor.frontend_dir.mkdir(parents=True, exist_ok=True)

        npm_json = json.dumps({
            "react": {"current": "18.2.0", "wanted": "18.3.0", "latest": "19.0.0"},
            "vite": {"current": "5.0.0", "wanted": "5.1.0", "latest": "5.1.0"},
        })
        mock_run.return_value = MagicMock(
            returncode=1,  # npm returns 1 when outdated packages exist
            stdout=npm_json,
            stderr="",
        )

        results = monitor.check_npm_packages()

        assert len(results) == 2
        names = [r["name"] for r in results]
        assert "react" in names
        assert "vite" in names

    @patch("subprocess.run")
    def test_check_npm_exit_code_1(self, mock_run, monitor, tmp_path):
        """npm returns exit code 1 when outdated packages exist -- should still parse."""
        monitor.frontend_dir = tmp_path / "frontend"
        monitor.frontend_dir.mkdir(parents=True, exist_ok=True)

        npm_json = json.dumps({
            "tailwindcss": {"current": "3.3.0", "wanted": "3.4.0", "latest": "4.0.0"},
        })
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=npm_json,
            stderr="",
        )

        results = monitor.check_npm_packages()

        assert len(results) == 1
        assert results[0]["name"] == "tailwindcss"
        assert results[0]["upgrade_type"] == "major"


# ============================================================
# save_report tests
# ============================================================

class TestSaveReport:
    """Tests for the save_report method."""

    def test_save_report(self, monitor, tmp_path):
        report = {
            "timestamp": "2026-02-26T12:00:00Z",
            "pip_outdated_count": 2,
            "npm_outdated_count": 1,
            "pip_major": 1,
            "pip_minor": 1,
            "pip_patch": 0,
            "npm_major": 0,
            "npm_minor": 1,
            "npm_patch": 0,
            "pip_packages": [{"name": "foo", "current": "1.0", "latest": "2.0"}],
            "npm_packages": [{"name": "bar", "current": "1.0", "latest": "1.1"}],
        }

        filepath = monitor.save_report(report)

        assert filepath.exists()
        assert filepath.suffix == ".json"

        with open(filepath, "r", encoding="utf-8") as fh:
            saved = json.load(fh)

        assert saved["pip_outdated_count"] == 2
        assert saved["npm_outdated_count"] == 1
        assert len(saved["pip_packages"]) == 1
        assert len(saved["npm_packages"]) == 1


# ============================================================
# run and notification tests
# ============================================================

class TestRunAndNotifications:
    """Tests for run() and send_notifications() methods."""

    @patch("subprocess.run")
    def test_run_no_notify(self, mock_run, monitor, tmp_path):
        """run() with notify=False should skip notifications entirely."""
        monitor.frontend_dir = tmp_path / "frontend"
        monitor.frontend_dir.mkdir(parents=True, exist_ok=True)

        # Mock pip returning empty (all current)
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="[]",
            stderr="",
        )

        with patch.object(monitor, "send_notifications") as mock_notify:
            report = monitor.run(notify=False)
            mock_notify.assert_not_called()

        assert report["pip_outdated_count"] == 0

    def test_send_notifications_no_outdated(self, monitor):
        """No notification should be sent when 0 packages are outdated."""
        report = monitor.generate_report([], [])

        with patch.dict("os.environ", {"DISCORD_ALERTS_WEBHOOK_URL": "https://hooks.example.com"}):
            with patch("scripts.devops.dependency_monitor.os.getenv") as mock_getenv:
                # Return webhook URL but it should not be called
                mock_getenv.side_effect = lambda key, default="": {
                    "DISCORD_ALERTS_WEBHOOK_URL": "https://hooks.example.com",
                    "ADMIN_EMAIL": "admin@test.com",
                    "ALERT_EMAIL": "",
                }.get(key, default)

                # Patch the discord post_embed at module level so it never actually posts
                with patch("src.utils.discord.post_embed") as mock_discord:
                    monitor.send_notifications(report)
                    # Discord should NOT be called because total == 0
                    mock_discord.assert_not_called()
