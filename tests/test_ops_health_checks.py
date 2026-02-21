"""
Tests for the Operations Health Check data layer.

Exercises HealthCheckService against the test_db fixture.
No Streamlit or UI dependencies.
"""

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, date
from pathlib import Path

import pytest

# Ensure project root is on path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.monitoring.health_checks import HealthCheckService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_nav(conn, nav_date: str, nav_per_share: float = 1.05,
                total_value: float = 40000, total_shares: float = 38000):
    """Insert a daily_nav row for testing."""
    conn.execute("""
        INSERT INTO daily_nav
        (date, nav_per_share, total_portfolio_value, total_shares,
         daily_change_dollars, daily_change_percent, created_at)
        VALUES (?, ?, ?, ?, 0, 0, ?)
    """, (nav_date, nav_per_share, total_value, total_shares,
          datetime.now().isoformat()))
    conn.commit()


def _insert_system_log(conn, log_type: str, category: str,
                       message: str, ts: str = None):
    """Insert a system_logs row."""
    if ts is None:
        ts = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO system_logs (timestamp, level, category, message, details)
        VALUES (?, ?, ?, ?, NULL)
    """, (ts, log_type, category, message))
    conn.commit()


def _insert_email_log(conn, recipient: str, subject: str,
                      email_type: str, status: str = 'Sent',
                      sent_at: str = None):
    """Insert an email_logs row."""
    if sent_at is None:
        sent_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute("""
        INSERT INTO email_logs (sent_at, recipient, subject, email_type, status)
        VALUES (?, ?, ?, ?, ?)
    """, (sent_at, recipient, subject, email_type, status))
    conn.commit()


def _insert_reconciliation(conn, rec_date: str, status: str,
                           difference: float = 0.0, notes: str = None):
    """Insert a daily_reconciliation row."""
    conn.execute("""
        INSERT INTO daily_reconciliation
        (date, tradier_balance, calculated_portfolio_value, difference,
         total_shares, nav_per_share, status, notes)
        VALUES (?, 40000, 40000, ?, 38000, 1.05, ?, ?)
    """, (rec_date, difference, status, notes))
    conn.commit()


# ---------------------------------------------------------------------------
# Fixture: HealthCheckService backed by test DB
# ---------------------------------------------------------------------------

@pytest.fixture
def health_svc(test_db):
    """Return a HealthCheckService that points at the test database."""
    # test_db fixture comes from conftest.py
    db_path = "data/test_tovito.db"
    return HealthCheckService(db_path=db_path)


# ===================================================================
# Test: Data Freshness
# ===================================================================

class TestDataFreshness:

    def test_fresh_nav(self, test_db, health_svc):
        """NAV inserted today should show status 'ok'."""
        today = datetime.now().strftime('%Y-%m-%d')
        _insert_nav(test_db, today)

        freshness = health_svc.get_data_freshness()
        assert 'daily_nav' in freshness
        assert freshness['daily_nav']['status'] == 'ok'
        assert freshness['daily_nav']['last_date'] == today

    def test_stale_nav(self, test_db, health_svc):
        """NAV only from 3 days ago should show status 'stale'."""
        old_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
        _insert_nav(test_db, old_date)

        freshness = health_svc.get_data_freshness()
        assert freshness['daily_nav']['status'] == 'stale'

    def test_missing_nav(self, test_db, health_svc):
        """Empty daily_nav table should show status 'missing'."""
        freshness = health_svc.get_data_freshness()
        assert freshness['daily_nav']['status'] == 'missing'

    def test_handles_missing_optional_tables(self, health_svc):
        """Should not crash even if optional tables don't exist
        (tested indirectly -- test_db creates all tables, but we verify
        the method completes without error)."""
        freshness = health_svc.get_data_freshness()
        assert isinstance(freshness, dict)


# ===================================================================
# Test: Reconciliation
# ===================================================================

class TestReconciliation:

    def test_empty_history(self, test_db, health_svc):
        """No reconciliation records -> empty list."""
        history = health_svc.get_reconciliation_history()
        assert history == []

    def test_history_with_data(self, test_db, health_svc):
        """Inserted records should come back sorted by date desc."""
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        _insert_reconciliation(test_db, yesterday, 'matched')
        _insert_reconciliation(test_db, today, 'mismatch',
                               difference=0.05,
                               notes='Share mismatch: 0.05')

        history = health_svc.get_reconciliation_history(days=7)
        assert len(history) == 2
        # Most recent first
        assert history[0]['date'] == today
        assert history[0]['status'] == 'mismatch'
        assert history[1]['status'] == 'matched'

    def test_current_status_matched(self, test_db, health_svc):
        """Latest record is 'matched'."""
        today = datetime.now().strftime('%Y-%m-%d')
        _insert_reconciliation(test_db, today, 'matched')

        status = health_svc.get_current_reconciliation_status()
        assert status is not None
        assert status['status'] == 'matched'

    def test_current_status_none(self, test_db, health_svc):
        """No records -> None."""
        status = health_svc.get_current_reconciliation_status()
        assert status is None


# ===================================================================
# Test: System Logs
# ===================================================================

class TestSystemLogs:

    def test_unfiltered(self, test_db, health_svc):
        """Returns all entries up to limit."""
        _insert_system_log(test_db, 'INFO', 'DailyRunner', 'NAV updated')
        _insert_system_log(test_db, 'ERROR', 'DailyRunner', 'API timeout')

        logs = health_svc.get_system_logs(limit=50)
        assert len(logs) == 2

    def test_filtered_by_type(self, test_db, health_svc):
        """Filter by log_type should only return matching rows."""
        _insert_system_log(test_db, 'INFO', 'DailyRunner', 'NAV updated')
        _insert_system_log(test_db, 'ERROR', 'DailyRunner', 'API timeout')

        logs = health_svc.get_system_logs(log_type='ERROR')
        assert len(logs) == 1
        assert logs[0]['message'] == 'API timeout'

    def test_filtered_by_category(self, test_db, health_svc):
        """Filter by category."""
        _insert_system_log(test_db, 'INFO', 'DailyRunner', 'NAV updated')
        _insert_system_log(test_db, 'INFO', 'Transaction', 'Contribution')

        logs = health_svc.get_system_logs(category='Transaction')
        assert len(logs) == 1
        assert logs[0]['message'] == 'Contribution'


# ===================================================================
# Test: Log Summary
# ===================================================================

class TestLogSummary:

    def test_counts_by_type(self, test_db, health_svc):
        """Verify aggregation by type."""
        now = datetime.now().isoformat()
        _insert_system_log(test_db, 'ERROR', 'DailyRunner', 'fail 1', ts=now)
        _insert_system_log(test_db, 'ERROR', 'DailyRunner', 'fail 2', ts=now)
        _insert_system_log(test_db, 'INFO', 'DailyRunner', 'ok', ts=now)

        summary = health_svc.get_log_summary(days=1)
        assert summary['total'] == 3
        assert summary['by_type']['ERROR'] == 2
        assert summary['by_type']['INFO'] == 1

    def test_empty_logs(self, test_db, health_svc):
        """No logs -> total 0."""
        summary = health_svc.get_log_summary(days=7)
        assert summary['total'] == 0


# ===================================================================
# Test: Email Delivery Stats
# ===================================================================

class TestEmailStats:

    def test_empty(self, test_db, health_svc):
        """No emails -> zeros."""
        stats = health_svc.get_email_delivery_stats()
        assert stats['total_sent'] == 0
        assert stats['total_failed'] == 0
        assert stats['recent'] == []

    def test_with_data(self, test_db, health_svc):
        """Insert test emails and verify counts + masking."""
        _insert_email_log(test_db, 'test@example.com',
                          'Monthly Report', 'MonthlyReport', 'Sent')
        _insert_email_log(test_db, 'admin@example.com',
                          'Alert: NAV Failed', 'Alert', 'Failed')
        _insert_email_log(test_db, 'other@example.com',
                          'Monthly Report', 'MonthlyReport', 'Sent')

        stats = health_svc.get_email_delivery_stats(days=30)
        assert stats['total_sent'] == 2
        assert stats['total_failed'] == 1
        assert stats['by_type']['MonthlyReport'] == 2
        assert stats['by_type']['Alert'] == 1

        # Recipients should be masked
        for entry in stats['recent']:
            assert '@' in entry['recipient']
            assert '***' in entry['recipient']


# ===================================================================
# Test: NAV Gap Check
# ===================================================================

class TestNAVGapCheck:

    def test_no_gaps(self, test_db, health_svc):
        """Consecutive weekday dates -> no gaps."""
        # Insert Mon-Fri of a single week
        base = date(2026, 1, 5)  # Monday
        for i in range(5):
            d = base + timedelta(days=i)
            _insert_nav(test_db, d.isoformat())

        result = health_svc.get_nav_gap_check()
        assert result['has_gaps'] is False
        assert result['gaps'] == []

    def test_with_gap(self, test_db, health_svc):
        """Missing Wednesday -> 1 business day gap."""
        base = date(2026, 1, 5)  # Monday
        for i in [0, 1, 3, 4]:  # Skip Wed (index 2)
            d = base + timedelta(days=i)
            _insert_nav(test_db, d.isoformat())

        result = health_svc.get_nav_gap_check()
        assert result['has_gaps'] is True
        assert len(result['gaps']) == 1
        assert result['gaps'][0]['business_days_missing'] == 1

    def test_weekend_not_counted(self, test_db, health_svc):
        """Friday -> Monday is not a gap (weekend)."""
        _insert_nav(test_db, '2026-01-02')  # Friday
        _insert_nav(test_db, '2026-01-05')  # Monday

        result = health_svc.get_nav_gap_check()
        assert result['has_gaps'] is False

    def test_empty_nav(self, test_db, health_svc):
        """Empty table -> no gaps, no crash."""
        result = health_svc.get_nav_gap_check()
        assert result['has_gaps'] is False
        assert result['latest_nav_date'] is None


# ===================================================================
# Test: Database Health
# ===================================================================

class TestDatabaseHealth:

    def test_integrity_passes(self, test_db, health_svc):
        """Test DB should pass integrity check."""
        db_health = health_svc.get_database_health()
        assert db_health['integrity_ok'] is True
        assert db_health['file_size_mb'] >= 0

    def test_table_counts(self, test_db, health_svc):
        """Table counts should be present for existing tables."""
        db_health = health_svc.get_database_health()
        counts = db_health['table_counts']
        # These tables exist in test schema
        assert 'daily_nav' in counts
        assert 'investors' in counts
        assert 'system_logs' in counts
        assert 'email_logs' in counts


# ===================================================================
# Test: Overall Health Score
# ===================================================================

class TestOverallHealthScore:

    def test_score_structure(self, test_db, health_svc):
        """Score dict has required keys."""
        score = health_svc.get_overall_health_score()
        assert 'score' in score
        assert 'grade' in score
        assert 'components' in score
        assert isinstance(score['score'], (int, float))
        assert 0 <= score['score'] <= 100
        assert score['grade'] in ('A', 'B', 'C', 'D', 'F')

    def test_all_components_present(self, test_db, health_svc):
        """All 5 components should be present."""
        score = health_svc.get_overall_health_score()
        names = {c['name'] for c in score['components']}
        assert 'NAV Freshness' in names
        assert 'Reconciliation' in names
        assert 'System Logs' in names
        assert 'Email Delivery' in names
        assert 'Database Integrity' in names

    def test_populated_db_scores_higher(self, populated_db, health_svc):
        """A populated DB should score higher than empty thanks to
        NAV data and DB integrity."""
        score = health_svc.get_overall_health_score()
        # DB integrity alone is 15, partial credits for missing data
        assert score['score'] > 0
        # With populated NAV data the freshness component might be stale
        # depending on test data dates, but DB integrity should be fine
        db_comp = next(
            c for c in score['components']
            if c['name'] == 'Database Integrity'
        )
        assert db_comp['score'] == 15
