"""
Synthetic Monitor
=================
Validates the Tovito Trader production system from an external perspective.
Runs health checks against the live API and frontend, reporting failures
via Discord and email alerts.

Designed to run on OPS-AUTOMATION laptop (no local database dependency).
All checks use HTTP requests to the production API.

Usage:
    python scripts/devops/synthetic_monitor.py                      # Run all checks
    python scripts/devops/synthetic_monitor.py --check health        # Single check
    python scripts/devops/synthetic_monitor.py --no-notify           # Skip alerts
    python scripts/devops/synthetic_monitor.py --url http://localhost:8000  # Test against local
    python scripts/devops/synthetic_monitor.py --json                # JSON output
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import requests as http_requests  # renamed to avoid conflict with function names

from dotenv import load_dotenv
load_dotenv()

from src.utils.safe_logging import get_safe_logger

logger = get_safe_logger(__name__)


class SyntheticMonitor:
    """External synthetic monitor for Tovito Trader production system.

    Performs health checks against the live API and frontend from an
    external perspective, simulating what a real user would experience.
    Reports failures via Discord webhook and email alerts.

    Args:
        base_url: API base URL. Defaults to PRODUCTION_API_URL env var
                  or https://api.tovitotrader.com.
        admin_key: Admin API key for admin endpoint checks.
                   Defaults to ADMIN_API_KEY env var.
    """

    def __init__(self, base_url=None, admin_key=None):
        self.base_url = (
            base_url
            or os.getenv('PRODUCTION_API_URL', 'https://api.tovitotrader.com')
        ).rstrip('/')
        self.admin_key = admin_key or os.getenv('ADMIN_API_KEY', '')
        self.frontend_url = os.getenv(
            'PORTAL_BASE_URL', 'https://tovitotrader.com'
        )
        self.monitor_email = os.getenv('SYNTHETIC_MONITOR_EMAIL', '')
        self.monitor_password = os.getenv('SYNTHETIC_MONITOR_PASSWORD', '')
        self.timeout = 10  # seconds per request
        self.log_file = PROJECT_ROOT / 'logs' / 'synthetic_monitor.log'

    # ------------------------------------------------------------------
    # Result helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_result(name, status, response_time_ms, details=None, error=None):
        """Build a standardized check result dict.

        Args:
            name: Human-readable check name.
            status: 'pass', 'fail', or 'skip'.
            response_time_ms: Elapsed time in milliseconds.
            details: Optional dict with additional context.
            error: Optional error message on failure.

        Returns:
            Dict with name, status, response_time_ms, details, error,
            and an ISO-8601 timestamp.
        """
        return {
            'name': name,
            'status': status,
            'response_time_ms': round(response_time_ms, 1),
            'details': details,
            'error': error,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        }

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def check_health_endpoint(self):
        """Check the /health endpoint returns 200 with a status field.

        Returns:
            Result dict with pass/fail status.
        """
        name = 'Health Endpoint'
        start = time.perf_counter()
        try:
            resp = http_requests.get(
                f'{self.base_url}/health', timeout=self.timeout
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                return self._make_result(
                    name, 'fail', elapsed_ms,
                    error=f'HTTP {resp.status_code}'
                )

            data = resp.json()
            if 'status' not in data:
                return self._make_result(
                    name, 'fail', elapsed_ms,
                    error='Response missing "status" field'
                )

            if elapsed_ms > 5000:
                return self._make_result(
                    name, 'fail', elapsed_ms,
                    error=f'Response too slow ({elapsed_ms:.0f}ms > 5000ms)'
                )

            return self._make_result(
                name, 'pass', elapsed_ms, details={'status': data['status']}
            )

        except http_requests.exceptions.Timeout:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return self._make_result(
                name, 'fail', elapsed_ms, error='Request timed out'
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            try:
                err_msg = str(exc)
            except UnicodeEncodeError:
                err_msg = ascii(str(exc))
            return self._make_result(name, 'fail', elapsed_ms, error=err_msg)

    def check_public_teaser(self):
        """Check the /public/teaser-stats endpoint returns valid fund metrics.

        Validates since_inception_pct is a number, total_investors > 0,
        and trading_days > 0.

        Returns:
            Result dict with pass/fail status.
        """
        name = 'Public Teaser Stats'
        start = time.perf_counter()
        try:
            resp = http_requests.get(
                f'{self.base_url}/public/teaser-stats', timeout=self.timeout
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                return self._make_result(
                    name, 'fail', elapsed_ms,
                    error=f'HTTP {resp.status_code}'
                )

            data = resp.json()

            # Validate required fields
            missing = []
            if 'since_inception_pct' not in data:
                missing.append('since_inception_pct')
            if 'total_investors' not in data:
                missing.append('total_investors')
            if 'trading_days' not in data:
                missing.append('trading_days')

            if missing:
                return self._make_result(
                    name, 'fail', elapsed_ms,
                    error=f'Missing fields: {", ".join(missing)}'
                )

            # Validate data types and values
            errors = []
            if not isinstance(data['since_inception_pct'], (int, float)):
                errors.append('since_inception_pct is not a number')
            if not isinstance(data['total_investors'], int) or data['total_investors'] <= 0:
                errors.append('total_investors must be > 0')
            if not isinstance(data['trading_days'], int) or data['trading_days'] <= 0:
                errors.append('trading_days must be > 0')

            if errors:
                return self._make_result(
                    name, 'fail', elapsed_ms,
                    error='; '.join(errors)
                )

            return self._make_result(
                name, 'pass', elapsed_ms,
                details={
                    'total_investors': data['total_investors'],
                    'trading_days': data['trading_days'],
                }
            )

        except http_requests.exceptions.Timeout:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return self._make_result(
                name, 'fail', elapsed_ms, error='Request timed out'
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            try:
                err_msg = str(exc)
            except UnicodeEncodeError:
                err_msg = ascii(str(exc))
            return self._make_result(name, 'fail', elapsed_ms, error=err_msg)

    def check_login_flow(self):
        """Attempt login with synthetic monitor credentials.

        If SYNTHETIC_MONITOR_EMAIL / SYNTHETIC_MONITOR_PASSWORD are not
        configured, the check is skipped (not failed).

        Returns:
            Result dict with pass/fail/skip status.  On pass, the
            access_token is included in details['access_token'].
        """
        name = 'Login Flow'

        if not self.monitor_email or not self.monitor_password:
            return self._make_result(
                name, 'skip', 0.0,
                details='Synthetic monitor credentials not configured'
            )

        start = time.perf_counter()
        try:
            resp = http_requests.post(
                f'{self.base_url}/auth/login',
                json={
                    'email': self.monitor_email,
                    'password': self.monitor_password,
                },
                timeout=self.timeout,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                return self._make_result(
                    name, 'fail', elapsed_ms,
                    error=f'HTTP {resp.status_code}'
                )

            data = resp.json()
            if 'access_token' not in data:
                return self._make_result(
                    name, 'fail', elapsed_ms,
                    error='Response missing "access_token"'
                )

            return self._make_result(
                name, 'pass', elapsed_ms,
                details={'access_token': data['access_token']}
            )

        except http_requests.exceptions.Timeout:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return self._make_result(
                name, 'fail', elapsed_ms, error='Request timed out'
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            try:
                err_msg = str(exc)
            except UnicodeEncodeError:
                err_msg = ascii(str(exc))
            return self._make_result(name, 'fail', elapsed_ms, error=err_msg)

    def check_nav_freshness(self, access_token):
        """Verify the latest NAV date is within 3 calendar days of today.

        Handles weekends and holidays gracefully: on Monday, Friday's NAV
        is acceptable (3 calendar days ago).

        Args:
            access_token: JWT bearer token from login.

        Returns:
            Result dict with pass/fail/skip status.
        """
        name = 'NAV Freshness'

        if not access_token:
            return self._make_result(
                name, 'skip', 0.0,
                details='No access token available'
            )

        start = time.perf_counter()
        try:
            resp = http_requests.get(
                f'{self.base_url}/nav/current',
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=self.timeout,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                return self._make_result(
                    name, 'fail', elapsed_ms,
                    error=f'HTTP {resp.status_code}'
                )

            data = resp.json()

            if 'date' not in data:
                return self._make_result(
                    name, 'fail', elapsed_ms,
                    error='Response missing "date" field'
                )

            if 'nav_per_share' not in data or data['nav_per_share'] <= 0:
                return self._make_result(
                    name, 'fail', elapsed_ms,
                    error='nav_per_share missing or <= 0'
                )

            # Check freshness (within 3 calendar days)
            try:
                nav_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                return self._make_result(
                    name, 'fail', elapsed_ms,
                    error=f'Invalid date format: {data["date"]}'
                )

            today = datetime.utcnow().date()
            days_old = (today - nav_date).days

            if days_old > 3:
                return self._make_result(
                    name, 'fail', elapsed_ms,
                    error=f'NAV is {days_old} days old (max 3)',
                    details={'nav_date': str(nav_date), 'days_old': days_old}
                )

            return self._make_result(
                name, 'pass', elapsed_ms,
                details={'nav_date': str(nav_date), 'days_old': days_old}
            )

        except http_requests.exceptions.Timeout:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return self._make_result(
                name, 'fail', elapsed_ms, error='Request timed out'
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            try:
                err_msg = str(exc)
            except UnicodeEncodeError:
                err_msg = ascii(str(exc))
            return self._make_result(name, 'fail', elapsed_ms, error=err_msg)

    def check_authenticated_endpoints(self, access_token):
        """Spot-check authenticated API endpoints for 200 responses.

        Tests /nav/history?days=7, /investor/position, and
        /analysis/risk-metrics.

        Args:
            access_token: JWT bearer token from login.

        Returns:
            Result dict with pass/fail/skip status.
        """
        name = 'Authenticated Endpoints'

        if not access_token:
            return self._make_result(
                name, 'skip', 0.0,
                details='No access token available'
            )

        endpoints = [
            '/nav/history?days=7',
            '/investor/position',
            '/analysis/risk-metrics',
        ]

        headers = {'Authorization': f'Bearer {access_token}'}
        failed = []
        total_start = time.perf_counter()

        for endpoint in endpoints:
            try:
                resp = http_requests.get(
                    f'{self.base_url}{endpoint}',
                    headers=headers,
                    timeout=self.timeout,
                )
                if resp.status_code != 200:
                    failed.append(f'{endpoint} -> HTTP {resp.status_code}')
                elif not resp.content:
                    failed.append(f'{endpoint} -> empty response')
            except http_requests.exceptions.Timeout:
                failed.append(f'{endpoint} -> timeout')
            except Exception as exc:
                try:
                    err_msg = str(exc)
                except UnicodeEncodeError:
                    err_msg = ascii(str(exc))
                failed.append(f'{endpoint} -> {err_msg}')

        elapsed_ms = (time.perf_counter() - total_start) * 1000

        if failed:
            return self._make_result(
                name, 'fail', elapsed_ms,
                error=f'{len(failed)}/{len(endpoints)} endpoints failed',
                details={'failed_endpoints': failed}
            )

        return self._make_result(
            name, 'pass', elapsed_ms,
            details={'endpoints_checked': len(endpoints)}
        )

    def check_frontend_accessible(self):
        """Verify the frontend at tovitotrader.com loads successfully.

        Checks that the response is 200, the body is > 1000 bytes (not
        an error page), and the body contains 'Tovito'.

        Returns:
            Result dict with pass/fail status.
        """
        name = 'Frontend Accessible'
        start = time.perf_counter()
        try:
            resp = http_requests.get(
                self.frontend_url, timeout=self.timeout
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                return self._make_result(
                    name, 'fail', elapsed_ms,
                    error=f'HTTP {resp.status_code}'
                )

            body_len = len(resp.content)
            if body_len < 1000:
                return self._make_result(
                    name, 'fail', elapsed_ms,
                    error=f'Response too small ({body_len} bytes < 1000)',
                )

            if 'Tovito' not in resp.text:
                return self._make_result(
                    name, 'fail', elapsed_ms,
                    error='Response body does not contain "Tovito"',
                )

            return self._make_result(
                name, 'pass', elapsed_ms,
                details={'body_length': body_len}
            )

        except http_requests.exceptions.Timeout:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return self._make_result(
                name, 'fail', elapsed_ms, error='Request timed out'
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            try:
                err_msg = str(exc)
            except UnicodeEncodeError:
                err_msg = ascii(str(exc))
            return self._make_result(name, 'fail', elapsed_ms, error=err_msg)

    def check_admin_endpoint(self):
        """Check the admin /admin/prospects endpoint with API key auth.

        If ADMIN_API_KEY is not configured, the check is skipped.

        Returns:
            Result dict with pass/fail/skip status.
        """
        name = 'Admin Endpoint'

        if not self.admin_key:
            return self._make_result(
                name, 'skip', 0.0,
                details='Admin API key not configured'
            )

        start = time.perf_counter()
        try:
            resp = http_requests.get(
                f'{self.base_url}/admin/prospects',
                headers={'X-Admin-Key': self.admin_key},
                timeout=self.timeout,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                return self._make_result(
                    name, 'fail', elapsed_ms,
                    error=f'HTTP {resp.status_code}'
                )

            return self._make_result(name, 'pass', elapsed_ms)

        except http_requests.exceptions.Timeout:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return self._make_result(
                name, 'fail', elapsed_ms, error='Request timed out'
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            try:
                err_msg = str(exc)
            except UnicodeEncodeError:
                err_msg = ascii(str(exc))
            return self._make_result(name, 'fail', elapsed_ms, error=err_msg)

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def run_all_checks(self):
        """Run all synthetic checks in sequence.

        Some checks depend on the login token, so ordering matters:
        1. health_endpoint
        2. public_teaser
        3. frontend_accessible
        4. login_flow (captures access_token)
        5. nav_freshness (uses token)
        6. authenticated_endpoints (uses token)
        7. admin_endpoint

        Returns:
            Dict with overall_status, per-check results, counts, and
            aggregate response time.
        """
        results = {}

        # Independent checks first
        results['health_endpoint'] = self.check_health_endpoint()
        results['public_teaser'] = self.check_public_teaser()
        results['frontend_accessible'] = self.check_frontend_accessible()

        # Login (captures token for subsequent checks)
        login_result = self.check_login_flow()
        results['login_flow'] = login_result

        access_token = None
        if login_result['status'] == 'pass' and login_result.get('details'):
            access_token = login_result['details'].get('access_token')

        # Token-dependent checks
        results['nav_freshness'] = self.check_nav_freshness(access_token)
        results['authenticated_endpoints'] = self.check_authenticated_endpoints(access_token)

        # Admin check (independent of login token)
        results['admin_endpoint'] = self.check_admin_endpoint()

        # Aggregate
        passed = sum(1 for r in results.values() if r['status'] == 'pass')
        failed = sum(1 for r in results.values() if r['status'] == 'fail')
        skipped = sum(1 for r in results.values() if r['status'] == 'skip')
        total_time = sum(r['response_time_ms'] for r in results.values())

        # Overall: pass only if zero failures (skips are acceptable)
        overall = 'pass' if failed == 0 else 'fail'

        return {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'base_url': self.base_url,
            'overall_status': overall,
            'checks_passed': passed,
            'checks_failed': failed,
            'checks_skipped': skipped,
            'total_response_time_ms': round(total_time, 1),
            'results': results,
        }

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def send_notifications(self, results):
        """Send Discord and email alerts when checks fail.

        Only sends notifications if at least one check has status 'fail'.
        Both notification channels are non-fatal -- failures are logged
        but do not raise exceptions.

        Args:
            results: The dict returned by run_all_checks().
        """
        if results['overall_status'] != 'fail':
            return

        failed_checks = {
            k: v for k, v in results['results'].items()
            if v['status'] == 'fail'
        }
        if not failed_checks:
            return

        # Build failure summary
        failure_lines = []
        for check_name, result in failed_checks.items():
            failure_lines.append(
                f"  - {result['name']}: {result.get('error', 'unknown error')}"
            )
        failure_summary = '\n'.join(failure_lines)

        # --- Discord notification ---
        try:
            from src.utils.discord import post_embed, make_embed, COLORS

            webhook_url = os.getenv('DISCORD_ALERTS_WEBHOOK_URL', '')
            if webhook_url:
                fields = []
                for check_name, result in failed_checks.items():
                    fields.append({
                        'name': result['name'],
                        'value': result.get('error', 'unknown error'),
                        'inline': False,
                    })

                embed = make_embed(
                    title='Synthetic Monitor Alert',
                    color=COLORS['critical'],
                    description=(
                        f'{results["checks_failed"]} of '
                        f'{results["checks_passed"] + results["checks_failed"] + results["checks_skipped"]} '
                        f'checks failed against {results["base_url"]}'
                    ),
                    fields=fields,
                )
                post_embed(webhook_url, embed)
                logger.info('Discord alert sent for synthetic monitor failure')
        except Exception as exc:
            try:
                logger.error(f'Discord notification failed: {exc}')
            except UnicodeEncodeError:
                logger.error(f'Discord notification failed: {ascii(str(exc))}')

        # --- Email notification ---
        try:
            from src.automation.email_service import EmailService

            admin_email = os.getenv('ADMIN_EMAIL', os.getenv('ALERT_EMAIL', ''))
            if admin_email:
                subject = (
                    f'[ALERT] Synthetic Monitor - '
                    f'{results["checks_failed"]} checks failed'
                )
                body = (
                    f'Synthetic Monitor detected failures at '
                    f'{results["timestamp"]}\n'
                    f'Target: {results["base_url"]}\n\n'
                    f'Failed checks:\n{failure_summary}\n\n'
                    f'Passed: {results["checks_passed"]}  |  '
                    f'Failed: {results["checks_failed"]}  |  '
                    f'Skipped: {results["checks_skipped"]}\n'
                    f'Total response time: {results["total_response_time_ms"]:.0f}ms'
                )
                email_svc = EmailService()
                email_svc.send_email(
                    admin_email, subject, body, email_type='Alert'
                )
                logger.info('Email alert sent for synthetic monitor failure')
        except Exception as exc:
            try:
                logger.error(f'Email notification failed: {exc}')
            except UnicodeEncodeError:
                logger.error(f'Email notification failed: {ascii(str(exc))}')

    def ping_healthcheck(self, results):
        """Ping healthchecks.io with pass/fail status.

        Uses HEALTHCHECK_SYNTHETIC_URL env var.  On all-pass, pings
        the success URL; on any failure, pings {url}/fail.

        Non-fatal -- errors are logged but do not raise.

        Args:
            results: The dict returned by run_all_checks().
        """
        healthcheck_url = os.getenv('HEALTHCHECK_SYNTHETIC_URL', '')
        if not healthcheck_url:
            return

        try:
            if results['overall_status'] == 'pass':
                http_requests.get(healthcheck_url, timeout=10)
            else:
                fail_url = healthcheck_url.rstrip('/') + '/fail'
                http_requests.get(fail_url, timeout=10)
        except Exception as exc:
            try:
                logger.error(f'Healthcheck ping failed: {exc}')
            except UnicodeEncodeError:
                logger.error(f'Healthcheck ping failed: {ascii(str(exc))}')

    # ------------------------------------------------------------------
    # Logging & reporting
    # ------------------------------------------------------------------

    def log_results(self, results):
        """Append a summary line to the synthetic monitor log file.

        Format:
            [YYYY-MM-DD HH:MM:SS] [PASS/FAIL] N/M checks passed (Xms total)
            On failure, lists which checks failed.

        Args:
            results: The dict returned by run_all_checks().
        """
        try:
            os.makedirs(self.log_file.parent, exist_ok=True)

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            total_checks = (
                results['checks_passed']
                + results['checks_failed']
                + results['checks_skipped']
            )
            non_skip = results['checks_passed'] + results['checks_failed']
            status_tag = results['overall_status'].upper()

            lines = [
                f'[{timestamp}] [{status_tag}] '
                f'{results["checks_passed"]}/{non_skip} checks passed '
                f'({results["total_response_time_ms"]:.0f}ms total)'
            ]

            if results['overall_status'] == 'fail':
                for check_name, result in results['results'].items():
                    if result['status'] == 'fail':
                        lines.append(
                            f'  FAILED: {result["name"]} - '
                            f'{result.get("error", "unknown")}'
                        )

            with open(self.log_file, 'a', encoding='utf-8') as f:
                for line in lines:
                    f.write(line + '\n')

        except Exception as exc:
            try:
                print(f'[WARN] Could not write log: {exc}')
            except UnicodeEncodeError:
                print(f'[WARN] Could not write log: {ascii(str(exc))}')

    def format_text_report(self, results):
        """Format results as a human-readable console report.

        Args:
            results: The dict returned by run_all_checks().

        Returns:
            Multi-line string suitable for printing to the terminal.
        """
        divider = '=' * 60

        lines = [
            divider,
            'SYNTHETIC MONITOR RESULTS',
            divider,
            f'Target: {results["base_url"]}',
            f'Time:   {results["timestamp"]}',
            '',
        ]

        for check_name, result in results['results'].items():
            status = result['status'].upper()
            tag = f'[{status}]'
            name = result['name']
            ms = result['response_time_ms']

            if status == 'SKIP':
                detail = result.get('details', '')
                if isinstance(detail, dict):
                    detail = ''
                lines.append(f'{tag:8s} {name:<30s} ({detail})')
            else:
                lines.append(f'{tag:8s} {name:<30s} ({ms:.0f}ms)')

        lines.append('')
        lines.append(divider)

        non_skip = results['checks_passed'] + results['checks_failed']
        total_ms = results['total_response_time_ms']
        overall_tag = 'PASS' if results['overall_status'] == 'pass' else 'FAIL'
        lines.append(
            f'RESULT: {results["checks_passed"]}/{non_skip} checks passed '
            f'({total_ms:.0f}ms total)  [{overall_tag}]'
        )
        if results['checks_skipped'] > 0:
            lines.append(f'Skipped: {results["checks_skipped"]}')
        lines.append(divider)

        return '\n'.join(lines)


# ======================================================================
# CLI entry point
# ======================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Run synthetic monitoring checks against Tovito Trader production'
    )
    parser.add_argument(
        '--check', type=str,
        choices=['health', 'teaser', 'frontend', 'login', 'nav', 'auth', 'admin'],
        help='Run a single check instead of all checks'
    )
    parser.add_argument(
        '--no-notify', action='store_true',
        help='Skip Discord and email notifications'
    )
    parser.add_argument(
        '--url', type=str,
        help='Override API base URL (e.g. http://localhost:8000)'
    )
    parser.add_argument(
        '--json', action='store_true', dest='output_json',
        help='Output results as JSON to stdout'
    )
    args = parser.parse_args()

    monitor = SyntheticMonitor(base_url=args.url)

    if args.check:
        # Single-check mode
        check_map = {
            'health': lambda: monitor.check_health_endpoint(),
            'teaser': lambda: monitor.check_public_teaser(),
            'frontend': lambda: monitor.check_frontend_accessible(),
            'login': lambda: monitor.check_login_flow(),
            'nav': lambda: _run_nav_check(monitor),
            'auth': lambda: _run_auth_check(monitor),
            'admin': lambda: monitor.check_admin_endpoint(),
        }

        result = check_map[args.check]()

        if args.output_json:
            print(json.dumps(result, indent=2, default=str))
        else:
            status = result['status'].upper()
            print(f'[{status}] {result["name"]} ({result["response_time_ms"]:.0f}ms)')
            if result.get('error'):
                print(f'  Error: {result["error"]}')
            if result.get('details') and isinstance(result['details'], dict):
                for k, v in result['details'].items():
                    if k != 'access_token':
                        print(f'  {k}: {v}')

        sys.exit(0 if result['status'] != 'fail' else 1)

    else:
        # Full run
        results = monitor.run_all_checks()

        if args.output_json:
            # Strip access tokens from JSON output
            safe_results = _strip_tokens(results)
            print(json.dumps(safe_results, indent=2, default=str))
        else:
            print(monitor.format_text_report(results))

        monitor.log_results(results)

        if not args.no_notify:
            monitor.send_notifications(results)

        monitor.ping_healthcheck(results)

        sys.exit(0 if results['overall_status'] == 'pass' else 1)


def _run_nav_check(monitor):
    """Helper: run login first to get a token, then check NAV freshness."""
    login_result = monitor.check_login_flow()
    token = None
    if login_result['status'] == 'pass' and login_result.get('details'):
        token = login_result['details'].get('access_token')
    return monitor.check_nav_freshness(token)


def _run_auth_check(monitor):
    """Helper: run login first to get a token, then check authenticated endpoints."""
    login_result = monitor.check_login_flow()
    token = None
    if login_result['status'] == 'pass' and login_result.get('details'):
        token = login_result['details'].get('access_token')
    return monitor.check_authenticated_endpoints(token)


def _strip_tokens(results):
    """Remove access_token values from results for safe JSON output."""
    import copy
    safe = copy.deepcopy(results)
    for check_name, result in safe.get('results', {}).items():
        if isinstance(result.get('details'), dict):
            if 'access_token' in result['details']:
                result['details']['access_token'] = '***'
    return safe


if __name__ == '__main__':
    main()
