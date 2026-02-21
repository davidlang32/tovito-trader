"""
Health Check Service
====================
Pure data layer for operations monitoring.  Returns plain Python dicts/lists.
No presentation-framework dependencies (Streamlit, Tkinter, etc.).

Usage:
    from src.monitoring.health_checks import HealthCheckService
    svc = HealthCheckService()            # uses default DB path
    svc = HealthCheckService('data/test.db')  # explicit path
    print(svc.get_overall_health_score())
"""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# PII masking -- import from project utility if available, else stub
# ---------------------------------------------------------------------------
try:
    from src.utils.safe_logging import PIIProtector
    _mask_email = PIIProtector.mask_email
except Exception:
    def _mask_email(email: str) -> str:
        """Fallback masking: d***@***.com"""
        if not email or '@' not in email:
            return '***'
        local, domain = email.rsplit('@', 1)
        return f"{local[0]}***@***.{domain.rsplit('.', 1)[-1]}"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_PROJECT_DIR = Path(os.getenv('PROJECT_DIR', 'C:/tovito-trader'))
_HEARTBEAT_FILE = _PROJECT_DIR / 'logs' / 'daily_nav_heartbeat.txt'
_WATCHDOG_LOG = _PROJECT_DIR / 'logs' / 'watchdog.log'
_WEEKLY_VALIDATION_LOG = _PROJECT_DIR / 'logs' / 'weekly_validation.log'

# Staleness thresholds (hours)
_STALE_NAV_HOURS = 26          # ~1 day + buffer for weekday scheduling
_STALE_HEARTBEAT_HOURS = 26
_STALE_TRADES_HOURS = 72       # Weekends + holiday buffer
_STALE_GENERIC_HOURS = 48


class HealthCheckService:
    """Operations health-check queries.

    Every public method connects, queries, and disconnects so the caller
    does not need to manage connection lifecycle.  All methods are safe to
    call even when optional tables (daily_reconciliation, holdings_snapshots,
    alert_events) do not yet exist.
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.getenv('DATABASE_PATH', 'data/tovito.db')
        self.db_path = db_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return cursor.fetchone() is not None

    @staticmethod
    def _safe_query(cursor: sqlite3.Cursor, sql: str,
                    params: tuple = ()) -> List[dict]:
        """Execute *sql* and return rows as list of dicts, or [] on error."""
        try:
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    @staticmethod
    def _file_age_hours(filepath: Path) -> Optional[float]:
        """Return age of *filepath* in hours, or None if missing."""
        try:
            if filepath.exists():
                mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                return (datetime.now() - mtime).total_seconds() / 3600
        except Exception:
            pass
        return None

    @staticmethod
    def _freshness_status(age_hours: Optional[float],
                          stale_threshold: float) -> str:
        if age_hours is None:
            return 'missing'
        return 'ok' if age_hours <= stale_threshold else 'stale'

    # ------------------------------------------------------------------
    # 1. Data Freshness
    # ------------------------------------------------------------------

    def get_data_freshness(self) -> Dict[str, Dict[str, Any]]:
        """Check how recently each data source was updated.

        Returns a dict keyed by source name, each containing:
            last_date, age_hours, status ('ok'|'stale'|'missing')
        """
        result: Dict[str, Dict[str, Any]] = {}
        conn = self._connect()
        cur = conn.cursor()

        # NAV
        rows = self._safe_query(cur,
            "SELECT date FROM daily_nav ORDER BY date DESC LIMIT 1")
        if rows:
            try:
                last = datetime.strptime(str(rows[0]['date'])[:10], '%Y-%m-%d')
                age = (datetime.now() - last).total_seconds() / 3600
            except Exception:
                last, age = None, None
            result['daily_nav'] = {
                'last_date': str(rows[0]['date'])[:10] if rows else None,
                'age_hours': round(age, 1) if age is not None else None,
                'status': self._freshness_status(age, _STALE_NAV_HOURS),
            }
        else:
            result['daily_nav'] = {'last_date': None, 'age_hours': None,
                                   'status': 'missing'}

        # Heartbeat file
        hb_age = self._file_age_hours(_HEARTBEAT_FILE)
        result['heartbeat'] = {
            'last_date': (
                datetime.fromtimestamp(_HEARTBEAT_FILE.stat().st_mtime)
                .strftime('%Y-%m-%d %H:%M')
                if _HEARTBEAT_FILE.exists() else None
            ),
            'age_hours': round(hb_age, 1) if hb_age is not None else None,
            'status': self._freshness_status(hb_age, _STALE_HEARTBEAT_HOURS),
        }

        # Trades
        rows = self._safe_query(cur,
            "SELECT date FROM trades ORDER BY date DESC LIMIT 1")
        if rows:
            try:
                last = datetime.strptime(str(rows[0]['date'])[:10], '%Y-%m-%d')
                age = (datetime.now() - last).total_seconds() / 3600
            except Exception:
                last, age = None, None
            result['trades'] = {
                'last_date': str(rows[0]['date'])[:10] if rows else None,
                'age_hours': round(age, 1) if age is not None else None,
                'status': self._freshness_status(age, _STALE_TRADES_HOURS),
            }
        else:
            result['trades'] = {'last_date': None, 'age_hours': None,
                                'status': 'missing'}

        # Holdings snapshots (optional table)
        if self._table_exists(cur, 'holdings_snapshots'):
            rows = self._safe_query(cur,
                "SELECT date FROM holdings_snapshots ORDER BY date DESC LIMIT 1")
            if rows:
                try:
                    last = datetime.strptime(str(rows[0]['date'])[:10], '%Y-%m-%d')
                    age = (datetime.now() - last).total_seconds() / 3600
                except Exception:
                    last, age = None, None
                result['holdings_snapshots'] = {
                    'last_date': str(rows[0]['date'])[:10],
                    'age_hours': round(age, 1) if age is not None else None,
                    'status': self._freshness_status(age, _STALE_GENERIC_HOURS),
                }
            else:
                result['holdings_snapshots'] = {
                    'last_date': None, 'age_hours': None, 'status': 'missing'}

        # Email logs
        if self._table_exists(cur, 'email_logs'):
            rows = self._safe_query(cur,
                "SELECT sent_at FROM email_logs ORDER BY sent_at DESC LIMIT 1")
            if rows:
                try:
                    last = datetime.strptime(
                        str(rows[0]['sent_at'])[:19], '%Y-%m-%d %H:%M:%S')
                    age = (datetime.now() - last).total_seconds() / 3600
                except Exception:
                    last, age = None, None
                result['email_logs'] = {
                    'last_date': str(rows[0]['sent_at'])[:19] if rows else None,
                    'age_hours': round(age, 1) if age is not None else None,
                    'status': self._freshness_status(age, _STALE_GENERIC_HOURS),
                }
            else:
                result['email_logs'] = {
                    'last_date': None, 'age_hours': None, 'status': 'missing'}

        # Daily reconciliation (optional table)
        if self._table_exists(cur, 'daily_reconciliation'):
            rows = self._safe_query(cur,
                "SELECT date FROM daily_reconciliation ORDER BY date DESC LIMIT 1")
            if rows:
                try:
                    last = datetime.strptime(str(rows[0]['date'])[:10], '%Y-%m-%d')
                    age = (datetime.now() - last).total_seconds() / 3600
                except Exception:
                    last, age = None, None
                result['reconciliation'] = {
                    'last_date': str(rows[0]['date'])[:10],
                    'age_hours': round(age, 1) if age is not None else None,
                    'status': self._freshness_status(age, _STALE_NAV_HOURS),
                }
            else:
                result['reconciliation'] = {
                    'last_date': None, 'age_hours': None, 'status': 'missing'}

        conn.close()
        return result

    # ------------------------------------------------------------------
    # 2. Reconciliation History
    # ------------------------------------------------------------------

    def get_reconciliation_history(self, days: int = 30) -> List[dict]:
        """Return reconciliation rows for the last *days* days."""
        conn = self._connect()
        cur = conn.cursor()
        if not self._table_exists(cur, 'daily_reconciliation'):
            conn.close()
            return []
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        rows = self._safe_query(cur, """
            SELECT date, status, difference, total_shares, nav_per_share, notes
            FROM daily_reconciliation
            WHERE date >= ?
            ORDER BY date DESC
        """, (cutoff,))
        conn.close()
        return rows

    # ------------------------------------------------------------------
    # 3. Current Reconciliation Status
    # ------------------------------------------------------------------

    def get_current_reconciliation_status(self) -> Optional[dict]:
        """Return the most recent reconciliation record, or None."""
        conn = self._connect()
        cur = conn.cursor()
        if not self._table_exists(cur, 'daily_reconciliation'):
            conn.close()
            return None
        rows = self._safe_query(cur, """
            SELECT date, status, difference, total_shares, nav_per_share, notes
            FROM daily_reconciliation
            ORDER BY date DESC LIMIT 1
        """)
        conn.close()
        return rows[0] if rows else None

    # ------------------------------------------------------------------
    # 4. System Logs
    # ------------------------------------------------------------------

    def get_system_logs(self, limit: int = 50, log_type: str = None,
                        category: str = None) -> List[dict]:
        """Return recent system_logs, optionally filtered."""
        conn = self._connect()
        cur = conn.cursor()
        clauses: List[str] = []
        params: List[Any] = []
        if log_type:
            clauses.append("log_type = ?")
            params.append(log_type)
        if category:
            clauses.append("category = ?")
            params.append(category)
        where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''

        # Handle both column name variants (level vs log_type)
        # Test DB uses 'level', prod DB uses 'log_type'
        try:
            sql = f"""
                SELECT timestamp, log_type, category, message, details
                FROM system_logs{where}
                ORDER BY timestamp DESC LIMIT ?
            """
            params.append(limit)
            rows = self._safe_query(cur, sql, tuple(params))
            if not rows:
                # Try alternative column name
                params_alt: List[Any] = []
                clauses_alt: List[str] = []
                if log_type:
                    clauses_alt.append("level = ?")
                    params_alt.append(log_type)
                if category:
                    clauses_alt.append("category = ?")
                    params_alt.append(category)
                where_alt = (' WHERE ' + ' AND '.join(clauses_alt)) if clauses_alt else ''
                sql_alt = f"""
                    SELECT timestamp, level as log_type, category, message, details
                    FROM system_logs{where_alt}
                    ORDER BY timestamp DESC LIMIT ?
                """
                params_alt.append(limit)
                rows = self._safe_query(cur, sql_alt, tuple(params_alt))
        except Exception:
            rows = []
        conn.close()
        return rows

    # ------------------------------------------------------------------
    # 5. Log Summary
    # ------------------------------------------------------------------

    def get_log_summary(self, days: int = 7) -> dict:
        """Aggregate system_logs counts by type and category."""
        conn = self._connect()
        cur = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days)).strftime(
            '%Y-%m-%d %H:%M:%S')

        # Try 'log_type' column first, fall back to 'level'
        type_col = 'log_type'
        test_rows = self._safe_query(cur,
            "SELECT log_type FROM system_logs LIMIT 1")
        if not test_rows:
            test_rows2 = self._safe_query(cur,
                "SELECT level FROM system_logs LIMIT 1")
            if test_rows2:
                type_col = 'level'

        by_type = {}
        rows = self._safe_query(cur, f"""
            SELECT {type_col} as lt, COUNT(*) as cnt
            FROM system_logs
            WHERE timestamp >= ?
            GROUP BY {type_col}
        """, (cutoff,))
        for r in rows:
            by_type[r['lt'] or 'UNKNOWN'] = r['cnt']

        by_category = {}
        rows = self._safe_query(cur, """
            SELECT category, COUNT(*) as cnt
            FROM system_logs
            WHERE timestamp >= ?
            GROUP BY category
        """, (cutoff,))
        for r in rows:
            by_category[r['category'] or 'UNKNOWN'] = r['cnt']

        total = sum(by_type.values())
        conn.close()
        return {'total': total, 'by_type': by_type, 'by_category': by_category}

    # ------------------------------------------------------------------
    # 6. Email Delivery Stats
    # ------------------------------------------------------------------

    def get_email_delivery_stats(self, days: int = 30) -> dict:
        """Email delivery counts and recent log (with masked recipients)."""
        conn = self._connect()
        cur = conn.cursor()
        if not self._table_exists(cur, 'email_logs'):
            conn.close()
            return {'total_sent': 0, 'total_failed': 0,
                    'by_type': {}, 'recent': []}

        cutoff = (datetime.now() - timedelta(days=days)).strftime(
            '%Y-%m-%d %H:%M:%S')

        # Totals by status
        rows = self._safe_query(cur, """
            SELECT status, COUNT(*) as cnt
            FROM email_logs
            WHERE sent_at >= ?
            GROUP BY status
        """, (cutoff,))
        sent = sum(r['cnt'] for r in rows if r['status'] == 'Sent')
        failed = sum(r['cnt'] for r in rows if r['status'] == 'Failed')

        # By email_type
        by_type: Dict[str, int] = {}
        rows = self._safe_query(cur, """
            SELECT email_type, COUNT(*) as cnt
            FROM email_logs
            WHERE sent_at >= ?
            GROUP BY email_type
        """, (cutoff,))
        for r in rows:
            by_type[r['email_type'] or 'Unknown'] = r['cnt']

        # Recent 10 (masked)
        rows = self._safe_query(cur, """
            SELECT sent_at, recipient, subject, email_type, status,
                   error_message
            FROM email_logs
            ORDER BY sent_at DESC LIMIT 10
        """)
        recent = []
        for r in rows:
            entry = dict(r)
            entry['recipient'] = _mask_email(entry.get('recipient', ''))
            recent.append(entry)

        conn.close()
        return {
            'total_sent': sent,
            'total_failed': failed,
            'by_type': by_type,
            'recent': recent,
        }

    # ------------------------------------------------------------------
    # 7. NAV Gap Check
    # ------------------------------------------------------------------

    def get_nav_gap_check(self) -> dict:
        """Find gaps in daily_nav dates (excluding weekends)."""
        conn = self._connect()
        cur = conn.cursor()
        rows = self._safe_query(cur,
            "SELECT date FROM daily_nav ORDER BY date ASC")
        conn.close()

        if not rows:
            return {'has_gaps': False, 'gaps': [],
                    'longest_gap': 0, 'latest_nav_date': None}

        dates = []
        for r in rows:
            try:
                dates.append(
                    datetime.strptime(str(r['date'])[:10], '%Y-%m-%d').date())
            except Exception:
                continue

        if not dates:
            return {'has_gaps': False, 'gaps': [],
                    'longest_gap': 0, 'latest_nav_date': None}

        gaps: List[dict] = []
        longest = 0

        for i in range(1, len(dates)):
            prev, curr = dates[i - 1], dates[i]
            # Count business days between prev and curr
            biz_days = 0
            d = prev + timedelta(days=1)
            while d < curr:
                if d.weekday() < 5:  # Mon-Fri
                    biz_days += 1
                d += timedelta(days=1)
            if biz_days > 0:
                gaps.append({
                    'start': prev.isoformat(),
                    'end': curr.isoformat(),
                    'business_days_missing': biz_days,
                })
                longest = max(longest, biz_days)

        return {
            'has_gaps': len(gaps) > 0,
            'gaps': gaps,
            'longest_gap': longest,
            'latest_nav_date': dates[-1].isoformat(),
        }

    # ------------------------------------------------------------------
    # 8. Database Health
    # ------------------------------------------------------------------

    def get_database_health(self) -> dict:
        """PRAGMA integrity check, file size, table row counts."""
        result: Dict[str, Any] = {
            'integrity_ok': False,
            'file_size_mb': 0.0,
            'table_counts': {},
        }
        try:
            db_file = Path(self.db_path)
            if db_file.exists():
                result['file_size_mb'] = round(
                    db_file.stat().st_size / (1024 * 1024), 2)
        except Exception:
            pass

        conn = self._connect()
        cur = conn.cursor()

        # Integrity
        try:
            cur.execute("PRAGMA integrity_check")
            row = cur.fetchone()
            result['integrity_ok'] = (row and row[0] == 'ok')
        except Exception:
            result['integrity_ok'] = False

        # Row counts for key tables
        for table in ('daily_nav', 'investors', 'transactions', 'trades',
                      'system_logs', 'email_logs', 'holdings_snapshots',
                      'daily_reconciliation'):
            if self._table_exists(cur, table):
                rows = self._safe_query(cur,
                    f"SELECT COUNT(*) as cnt FROM {table}")
                result['table_counts'][table] = (
                    rows[0]['cnt'] if rows else 0)

        conn.close()
        return result

    # ------------------------------------------------------------------
    # 9. Automation Status
    # ------------------------------------------------------------------

    def get_automation_status(self) -> List[dict]:
        """Check evidence of each scheduled automation task."""
        tasks: List[dict] = []
        conn = self._connect()
        cur = conn.cursor()

        # -- Daily NAV --
        nav_age = self._file_age_hours(_HEARTBEAT_FILE)
        rows = self._safe_query(cur,
            "SELECT date FROM daily_nav ORDER BY date DESC LIMIT 1")
        last_nav = rows[0]['date'] if rows else None
        tasks.append({
            'name': 'Daily NAV Update',
            'last_run': (
                datetime.fromtimestamp(_HEARTBEAT_FILE.stat().st_mtime)
                .strftime('%Y-%m-%d %H:%M')
                if _HEARTBEAT_FILE.exists() else last_nav
            ),
            'status': self._freshness_status(nav_age, _STALE_NAV_HOURS),
            'details': f"Latest NAV date: {last_nav}" if last_nav else
                       "No NAV records found",
        })

        # -- Watchdog --
        wd_age = self._file_age_hours(_WATCHDOG_LOG)
        tasks.append({
            'name': 'Watchdog Monitor',
            'last_run': (
                datetime.fromtimestamp(_WATCHDOG_LOG.stat().st_mtime)
                .strftime('%Y-%m-%d %H:%M')
                if _WATCHDOG_LOG.exists() else None
            ),
            'status': self._freshness_status(wd_age, _STALE_NAV_HOURS),
            'details': 'Checks NAV, heartbeat, DB, errors',
        })

        # -- Weekly Validation --
        wv_age = self._file_age_hours(_WEEKLY_VALIDATION_LOG)
        tasks.append({
            'name': 'Weekly Validation',
            'last_run': (
                datetime.fromtimestamp(
                    _WEEKLY_VALIDATION_LOG.stat().st_mtime)
                .strftime('%Y-%m-%d %H:%M')
                if _WEEKLY_VALIDATION_LOG.exists() else None
            ),
            'status': self._freshness_status(
                wv_age, 7 * 24 + 12),  # ~7.5 days
            'details': 'Comprehensive data validation',
        })

        # -- Monthly Reports --
        if self._table_exists(cur, 'email_logs'):
            rows = self._safe_query(cur, """
                SELECT sent_at FROM email_logs
                WHERE email_type = 'MonthlyReport'
                ORDER BY sent_at DESC LIMIT 1
            """)
            last_report = rows[0]['sent_at'] if rows else None
        else:
            last_report = None
        tasks.append({
            'name': 'Monthly Reports',
            'last_run': str(last_report)[:19] if last_report else None,
            'status': 'ok' if last_report else 'missing',
            'details': 'PDF generation + email delivery',
        })

        conn.close()
        return tasks

    # ------------------------------------------------------------------
    # 10. Overall Health Score
    # ------------------------------------------------------------------

    def get_overall_health_score(self) -> dict:
        """Compute a composite 0-100 health score.

        Components (max points):
            NAV Freshness       25
            Reconciliation      25
            System Logs         20
            Email Delivery      15
            Database Integrity  15
        """
        components: List[dict] = []

        # --- NAV Freshness (25) ---
        freshness = self.get_data_freshness()
        nav_info = freshness.get('daily_nav', {})
        nav_status = nav_info.get('status', 'missing')
        if nav_status == 'ok':
            nav_score = 25
        elif nav_status == 'stale':
            nav_score = 10
        else:
            nav_score = 0
        components.append({
            'name': 'NAV Freshness',
            'score': nav_score, 'max': 25, 'status': nav_status,
        })

        # --- Reconciliation (25) ---
        recon = self.get_current_reconciliation_status()
        if recon is None:
            recon_status = 'missing'
            recon_score = 10  # Partial credit -- table may not exist yet
        elif recon.get('status') == 'matched':
            recon_status = 'ok'
            recon_score = 25
        else:
            recon_status = 'mismatch'
            recon_score = 5
        components.append({
            'name': 'Reconciliation',
            'score': recon_score, 'max': 25, 'status': recon_status,
        })

        # --- System Logs (20) ---
        summary = self.get_log_summary(days=1)
        errors_today = summary['by_type'].get('ERROR', 0)
        if errors_today == 0:
            log_score = 20
            log_status = 'ok'
        elif errors_today <= 2:
            log_score = 12
            log_status = 'warning'
        else:
            log_score = 4
            log_status = 'critical'
        components.append({
            'name': 'System Logs',
            'score': log_score, 'max': 20, 'status': log_status,
        })

        # --- Email Delivery (15) ---
        email = self.get_email_delivery_stats(days=30)
        total = email['total_sent'] + email['total_failed']
        if total == 0:
            email_score = 10  # Partial -- no emails sent yet
            email_status = 'no_data'
        elif email['total_failed'] == 0:
            email_score = 15
            email_status = 'ok'
        elif email['total_failed'] / total < 0.1:
            email_score = 10
            email_status = 'warning'
        else:
            email_score = 3
            email_status = 'critical'
        components.append({
            'name': 'Email Delivery',
            'score': email_score, 'max': 15, 'status': email_status,
        })

        # --- Database Integrity (15) ---
        db_health = self.get_database_health()
        if db_health['integrity_ok']:
            db_score = 15
            db_status = 'ok'
        else:
            db_score = 0
            db_status = 'critical'
        components.append({
            'name': 'Database Integrity',
            'score': db_score, 'max': 15, 'status': db_status,
        })

        # --- Composite ---
        total_score = sum(c['score'] for c in components)
        if total_score >= 85:
            grade = 'A'
        elif total_score >= 70:
            grade = 'B'
        elif total_score >= 50:
            grade = 'C'
        elif total_score >= 30:
            grade = 'D'
        else:
            grade = 'F'

        return {
            'score': total_score,
            'grade': grade,
            'components': components,
        }


# ======================================================================
# Remediation Guidance Lookup
# ======================================================================

def get_remediation(source: str, status: str,
                    context: dict = None) -> Optional[dict]:
    """Return actionable remediation guidance for a non-green indicator.

    This is a standalone lookup function, not a method on HealthCheckService.
    It maps (source, status, context) to a plain dict of guidance text so
    any UI can render it.

    Args:
        source:  Health-check source key, e.g. 'daily_nav', 'watchdog',
                 'holdings_snapshots', 'monthly_reports', etc.
        status:  Status string, e.g. 'ok', 'stale', 'missing', 'mismatch',
                 'warning', 'critical', 'no_data'.
        context: Optional dict for smart time-aware guidance.
                 Supported keys:
                   age_hours (float) -- staleness in hours
                   last_date (str)   -- last recorded date
                   now (datetime)    -- current time (default: now())

    Returns:
        None if status is 'ok'.
        Otherwise a dict with keys:
            summary            (str)       1-line human explanation
            action             (str)       what the user should do
            command            (str|None)  copy-pasteable shell command
            wait_for_next_cycle (bool)     True = just wait, no action
            log_file           (str|None)  log to check for errors
    """
    if status == 'ok':
        return None

    ctx = context or {}
    now = ctx.get('now', datetime.now())
    age_hours = ctx.get('age_hours')

    # Time-of-day helpers (EST-oriented)
    is_weekday = now.weekday() < 5          # Mon=0 .. Fri=4
    past_market_close = now.hour >= 17      # 5 PM -- generous buffer past 4:05
    before_market_close = is_weekday and not past_market_close

    # ==============================================================
    # DAILY NAV
    # ==============================================================
    if source == 'daily_nav':
        if status == 'stale':
            if before_market_close:
                return {
                    'summary': 'NAV updates daily after market close (~4:05 PM EST).',
                    'action': 'Wait for the automated daily update to run after market close.',
                    'command': None,
                    'wait_for_next_cycle': True,
                    'log_file': 'logs/task_scheduler.log',
                }
            if is_weekday and past_market_close:
                return {
                    'summary': 'NAV is stale and market has closed. The daily task may have failed.',
                    'action': 'Run the daily NAV update manually, then check the log for errors.',
                    'command': 'python scripts/daily_nav_enhanced.py',
                    'wait_for_next_cycle': False,
                    'log_file': 'logs/daily_runner.log',
                }
            # Weekend
            return {
                'summary': 'NAV is from the last trading day. Markets are closed on weekends.',
                'action': 'No action needed. NAV will update automatically on the next trading day.',
                'command': None,
                'wait_for_next_cycle': True,
                'log_file': None,
            }
        if status == 'missing':
            return {
                'summary': 'No NAV records found in the database.',
                'action': 'Run the daily NAV update to create the first record.',
                'command': 'python scripts/daily_nav_enhanced.py',
                'wait_for_next_cycle': False,
                'log_file': 'logs/daily_runner.log',
            }

    # ==============================================================
    # HEARTBEAT
    # ==============================================================
    if source == 'heartbeat':
        if status in ('stale', 'missing'):
            return {
                'summary': 'The daily NAV task has not written a heartbeat recently.',
                'action': ('Check that the Daily NAV task is enabled in Windows '
                           'Task Scheduler and configured correctly.'),
                'command': 'python scripts/daily_nav_enhanced.py',
                'wait_for_next_cycle': False,
                'log_file': 'logs/task_scheduler.log',
            }

    # ==============================================================
    # TRADES
    # ==============================================================
    if source == 'trades':
        if status == 'stale':
            return {
                'summary': 'Trade data is stale. This may be normal over weekends or holidays.',
                'action': 'Sync trades from the brokerage if any trading has occurred.',
                'command': 'python scripts/trading/sync_all_trades.py',
                'wait_for_next_cycle': False,
                'log_file': None,
            }
        if status == 'missing':
            return {
                'summary': 'No trade records found.',
                'action': 'Import trade history from the brokerage.',
                'command': 'python scripts/trading/sync_all_trades.py',
                'wait_for_next_cycle': False,
                'log_file': None,
            }

    # ==============================================================
    # HOLDINGS SNAPSHOTS
    # ==============================================================
    if source == 'holdings_snapshots':
        if status == 'missing':
            return {
                'summary': 'Holdings snapshots are a new feature. No data has been captured yet.',
                'action': ('This populates automatically as Step 4 of the daily NAV '
                           'update. It will appear after the next successful daily run.'),
                'command': 'python scripts/daily_nav_enhanced.py',
                'wait_for_next_cycle': True,
                'log_file': 'logs/daily_runner.log',
            }
        if status == 'stale':
            return {
                'summary': 'Holdings snapshot is out of date.',
                'action': ('Snapshots are captured during the daily NAV update (Step 4). '
                           'Run it manually if the scheduled task missed.'),
                'command': 'python scripts/daily_nav_enhanced.py',
                'wait_for_next_cycle': False,
                'log_file': 'logs/daily_runner.log',
            }

    # ==============================================================
    # EMAIL LOGS
    # ==============================================================
    if source == 'email_logs':
        if status == 'missing':
            return {
                'summary': 'Email logging was recently added. No emails have been sent yet.',
                'action': ('This will auto-populate the next time the system sends '
                           'an email (monthly reports, failure alerts, etc.). '
                           'No manual action needed.'),
                'command': None,
                'wait_for_next_cycle': True,
                'log_file': None,
            }
        if status == 'stale':
            return {
                'summary': 'No recent emails logged.',
                'action': 'This is normal if no reports or alerts were triggered recently.',
                'command': None,
                'wait_for_next_cycle': True,
                'log_file': None,
            }

    # ==============================================================
    # RECONCILIATION (data freshness context)
    # ==============================================================
    if source == 'reconciliation':
        if status == 'stale':
            return {
                'summary': 'Reconciliation data is stale.',
                'action': ('Reconciliation runs automatically as Step 5 of the '
                           'daily NAV update. Running the daily NAV script will '
                           'also refresh reconciliation.'),
                'command': 'python scripts/daily_nav_enhanced.py',
                'wait_for_next_cycle': False,
                'log_file': 'logs/daily_runner.log',
            }
        if status == 'missing':
            return {
                'summary': 'No reconciliation records found.',
                'action': ('Reconciliation runs as part of the daily NAV update '
                           '(Step 5). Records will appear after the next '
                           'successful daily run.'),
                'command': 'python scripts/daily_nav_enhanced.py',
                'wait_for_next_cycle': True,
                'log_file': 'logs/daily_runner.log',
            }
        if status == 'mismatch':
            return {
                'summary': 'Reconciliation detected a mismatch between expected and actual values.',
                'action': ('Run the comprehensive validation script to identify '
                           'the discrepancy, then investigate the specific '
                           'mismatch noted in the reconciliation record.'),
                'command': 'python scripts/validation/validate_reconciliation.py --verbose',
                'wait_for_next_cycle': False,
                'log_file': 'logs/weekly_validation.log',
            }

    # ==============================================================
    # AUTOMATION: WATCHDOG
    # ==============================================================
    if source == 'watchdog':
        stale_detail = ''
        if age_hours is not None and age_hours > 168:  # > 1 week
            stale_detail = (f' It has not run in {age_hours:.0f} hours '
                            f'(~{age_hours / 24:.0f} days).')
        return {
            'summary': f'Watchdog monitor is not running on schedule.{stale_detail}',
            'action': ('Check that the Watchdog task is enabled in Windows '
                       'Task Scheduler. It should run ~1 hour after the daily '
                       'NAV task (e.g., 5:05 PM EST). You can also run it manually.'),
            'command': 'python apps/market_monitor/watchdog_monitor.py',
            'wait_for_next_cycle': False,
            'log_file': 'logs/watchdog.log',
        }

    # ==============================================================
    # AUTOMATION: WEEKLY VALIDATION
    # ==============================================================
    if source == 'weekly_validation':
        return {
            'summary': 'Weekly validation has not run recently.',
            'action': ('Check the Weekly Validation task in Windows Task '
                       'Scheduler, or run it manually.'),
            'command': 'python scripts/validation/validate_reconciliation.py --verbose',
            'wait_for_next_cycle': False,
            'log_file': 'logs/weekly_validation.log',
        }

    # ==============================================================
    # AUTOMATION: MONTHLY REPORTS
    # ==============================================================
    if source == 'monthly_reports':
        if status == 'missing':
            return {
                'summary': 'No monthly reports have been sent yet.',
                'action': ('Monthly reports are generated and emailed at '
                           'month-end. If the fund is new, this is expected. '
                           'Generate manually for a specific month:'),
                'command': ('python scripts/reporting/generate_monthly_report.py '
                            '--month 2 --year 2026 --email'),
                'wait_for_next_cycle': True,
                'log_file': None,
            }
        if status == 'stale':
            return {
                'summary': 'Monthly report delivery appears overdue.',
                'action': 'Generate and email reports for the previous month.',
                'command': ('python scripts/reporting/generate_monthly_report.py '
                            '--month 2 --year 2026 --email'),
                'wait_for_next_cycle': False,
                'log_file': None,
            }

    # ==============================================================
    # HEALTH SCORE COMPONENTS
    # ==============================================================
    if source == 'system_logs':
        if status == 'warning':
            return {
                'summary': 'A small number of errors appeared in recent system logs.',
                'action': 'Review recent ERROR entries in the System Logs section below.',
                'command': None,
                'wait_for_next_cycle': False,
                'log_file': 'logs/daily_runner.log',
            }
        if status == 'critical':
            return {
                'summary': 'Multiple errors detected in system logs.',
                'action': ('Review the ERROR entries below urgently. Check '
                           'daily_runner.log and watchdog.log for details.'),
                'command': None,
                'wait_for_next_cycle': False,
                'log_file': 'logs/daily_runner.log',
            }

    if source == 'email_delivery':
        if status == 'no_data':
            return {
                'summary': 'No emails have been sent yet. The email logging feature is new.',
                'action': ('This will auto-populate when the system sends its '
                           'first email (monthly reports, alerts, etc.).'),
                'command': None,
                'wait_for_next_cycle': True,
                'log_file': None,
            }
        if status == 'warning':
            return {
                'summary': 'Some emails failed to deliver (under 10% failure rate).',
                'action': ('Check the Email Delivery section below for failed '
                           'entries. Verify SMTP credentials in .env are correct.'),
                'command': None,
                'wait_for_next_cycle': False,
                'log_file': None,
            }
        if status == 'critical':
            return {
                'summary': 'High email failure rate (over 10%).',
                'action': ('Check SMTP configuration in .env. Verify the Gmail '
                           'app password is still valid and the account is not locked.'),
                'command': None,
                'wait_for_next_cycle': False,
                'log_file': None,
            }

    if source == 'database_integrity':
        if status == 'critical':
            return {
                'summary': 'CRITICAL: Database integrity check failed.',
                'action': ('Back up the database IMMEDIATELY, then run '
                           'PRAGMA integrity_check manually to see detailed '
                           'errors. Consider restoring from the most recent backup.'),
                'command': 'python scripts/utilities/backup_database.py',
                'wait_for_next_cycle': False,
                'log_file': None,
            }

    # ==============================================================
    # FALLBACK
    # ==============================================================
    return {
        'summary': f'{source.replace("_", " ").title()} status is {status}.',
        'action': 'Investigate manually.',
        'command': None,
        'wait_for_next_cycle': False,
        'log_file': None,
    }
