"""
Tests for the get_remediation() guidance lookup function.

No database required -- the function is a pure lookup based on
(source, status, context).
"""

import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.monitoring.health_checks import get_remediation


# Required keys every non-None result must have
REQUIRED_KEYS = {'summary', 'action', 'command', 'wait_for_next_cycle', 'log_file'}


# ===================================================================
# Basics
# ===================================================================

class TestBasics:

    def test_ok_status_returns_none(self):
        """Any source with status 'ok' should return None."""
        for src in ('daily_nav', 'heartbeat', 'trades', 'watchdog',
                    'reconciliation', 'holdings_snapshots', 'email_logs',
                    'monthly_reports', 'system_logs', 'email_delivery',
                    'database_integrity'):
            assert get_remediation(src, 'ok') is None

    def test_fallback_for_unknown_source(self):
        """Unknown source should return a generic guidance dict."""
        result = get_remediation('some_unknown_thing', 'stale')
        assert result is not None
        assert set(result.keys()) == REQUIRED_KEYS
        assert 'Some Unknown Thing' in result['summary']

    def test_required_keys_present(self):
        """Spot-check several source/status combos for all required keys."""
        combos = [
            ('daily_nav', 'stale'),
            ('daily_nav', 'missing'),
            ('watchdog', 'missing'),
            ('monthly_reports', 'missing'),
            ('database_integrity', 'critical'),
            ('holdings_snapshots', 'missing'),
            ('email_logs', 'missing'),
            ('reconciliation', 'mismatch'),
            ('email_delivery', 'no_data'),
            ('system_logs', 'warning'),
        ]
        for src, status in combos:
            result = get_remediation(src, status)
            assert result is not None, f"None for {src}/{status}"
            assert set(result.keys()) == REQUIRED_KEYS, (
                f"Missing keys for {src}/{status}: "
                f"{REQUIRED_KEYS - set(result.keys())}")


# ===================================================================
# NAV Freshness (time-aware)
# ===================================================================

class TestNAVRemediation:

    def test_stale_weekday_morning(self):
        """Weekday before market close -> wait for automation."""
        # Wednesday 10:00 AM
        ctx = {'now': datetime(2026, 2, 18, 10, 0)}
        result = get_remediation('daily_nav', 'stale', ctx)
        assert result is not None
        assert result['wait_for_next_cycle'] is True
        assert result['command'] is None
        assert '4:05' in result['summary'] or 'market close' in result['summary'].lower()

    def test_stale_weekday_evening(self):
        """Weekday after 5 PM -> run manually."""
        # Wednesday 6:00 PM
        ctx = {'now': datetime(2026, 2, 18, 18, 0)}
        result = get_remediation('daily_nav', 'stale', ctx)
        assert result is not None
        assert result['wait_for_next_cycle'] is False
        assert result['command'] is not None
        assert 'daily_nav_enhanced' in result['command']

    def test_stale_weekend(self):
        """Weekend -> markets closed, no action needed."""
        # Saturday noon
        ctx = {'now': datetime(2026, 2, 21, 12, 0)}
        result = get_remediation('daily_nav', 'stale', ctx)
        assert result is not None
        assert result['wait_for_next_cycle'] is True
        assert result['command'] is None

    def test_missing_nav(self):
        """Missing NAV -> provides command to run."""
        result = get_remediation('daily_nav', 'missing')
        assert result is not None
        assert result['command'] is not None
        assert result['wait_for_next_cycle'] is False


# ===================================================================
# New Features (wait for auto-populate)
# ===================================================================

class TestNewFeatures:

    def test_holdings_missing(self):
        """New feature that hasn't populated yet."""
        result = get_remediation('holdings_snapshots', 'missing')
        assert result is not None
        assert result['wait_for_next_cycle'] is True
        assert 'new feature' in result['summary'].lower() or 'Step 4' in result['action']

    def test_email_logs_missing(self):
        """Email logging just added, no emails sent yet."""
        result = get_remediation('email_logs', 'missing')
        assert result is not None
        assert result['wait_for_next_cycle'] is True
        assert result['command'] is None

    def test_email_delivery_no_data(self):
        """Health score component: no emails sent -> partial credit."""
        result = get_remediation('email_delivery', 'no_data')
        assert result is not None
        assert result['wait_for_next_cycle'] is True


# ===================================================================
# Automation Tasks
# ===================================================================

class TestAutomation:

    def test_watchdog_very_stale(self):
        """Watchdog not run in > 1 week includes duration info."""
        result = get_remediation('watchdog', 'stale',
                                 context={'age_hours': 500.0})
        assert result is not None
        assert '500' in result['summary'] or 'days' in result['summary']
        assert result['command'] is not None
        assert 'watchdog' in result['command']

    def test_watchdog_short_stale(self):
        """Watchdog stale but recently -> still provides guidance."""
        result = get_remediation('watchdog', 'stale',
                                 context={'age_hours': 30.0})
        assert result is not None
        assert result['command'] is not None

    def test_monthly_reports_missing(self):
        """No monthly reports -> explains new fund, provides command."""
        result = get_remediation('monthly_reports', 'missing')
        assert result is not None
        assert result['command'] is not None
        assert 'generate_monthly_report' in result['command']
        # New fund -- should indicate waiting is fine
        assert result['wait_for_next_cycle'] is True

    def test_weekly_validation_stale(self):
        """Weekly validation not running -> check Task Scheduler."""
        result = get_remediation('weekly_validation', 'stale')
        assert result is not None
        assert result['command'] is not None
        assert 'Task Scheduler' in result['action']


# ===================================================================
# Reconciliation
# ===================================================================

class TestReconciliation:

    def test_mismatch(self):
        """Reconciliation mismatch -> provides validate command."""
        result = get_remediation('reconciliation', 'mismatch')
        assert result is not None
        assert result['command'] is not None
        assert 'validate' in result['command']
        assert result['wait_for_next_cycle'] is False

    def test_stale(self):
        """Stale reconciliation -> run daily NAV."""
        result = get_remediation('reconciliation', 'stale')
        assert result is not None
        assert 'daily_nav_enhanced' in result['command']

    def test_missing(self):
        """No reconciliation records -> will auto-populate."""
        result = get_remediation('reconciliation', 'missing')
        assert result is not None
        assert result['wait_for_next_cycle'] is True


# ===================================================================
# Critical: Database Integrity
# ===================================================================

class TestCritical:

    def test_database_integrity_critical(self):
        """Failed integrity check -> CRITICAL, suggest backup."""
        result = get_remediation('database_integrity', 'critical')
        assert result is not None
        assert 'CRITICAL' in result['summary']
        assert 'backup' in result['command'].lower() or 'backup' in result['action'].lower()
        assert result['wait_for_next_cycle'] is False

    def test_system_logs_critical(self):
        """Multiple errors in logs -> urgent review."""
        result = get_remediation('system_logs', 'critical')
        assert result is not None
        assert result['wait_for_next_cycle'] is False
        assert 'ERROR' in result['action'] or 'error' in result['action'].lower()
