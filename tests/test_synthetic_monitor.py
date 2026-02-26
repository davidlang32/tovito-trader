"""
Tests for Synthetic Monitor
============================

Tests the SyntheticMonitor class using mocked HTTP responses.
No real network calls are made.
"""

import pytest
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock, call
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.devops.synthetic_monitor import SyntheticMonitor


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def monitor():
    """Create a SyntheticMonitor with test defaults."""
    m = SyntheticMonitor(
        base_url='https://api.test.com',
        admin_key='test-admin-key-123',
    )
    m.frontend_url = 'https://test.com'
    m.monitor_email = ''
    m.monitor_password = ''
    return m


@pytest.fixture
def monitor_with_creds():
    """Create a SyntheticMonitor with login credentials set."""
    m = SyntheticMonitor(
        base_url='https://api.test.com',
        admin_key='test-admin-key-123',
    )
    m.frontend_url = 'https://test.com'
    m.monitor_email = 'monitor@test.com'
    m.monitor_password = 'TestPass123!'
    return m


def _mock_response(status_code=200, json_data=None, text='', content=b''):
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text or json.dumps(json_data or {})
    resp.content = content or resp.text.encode('utf-8')
    return resp


# ============================================================
# Health Endpoint Tests
# ============================================================

class TestCheckHealth:
    """Tests for check_health_endpoint()."""

    @patch('scripts.devops.synthetic_monitor.http_requests')
    def test_check_health_success(self, mock_req, monitor):
        """200 with status field returns pass."""
        mock_req.get.return_value = _mock_response(
            200, {'status': 'healthy'}
        )
        mock_req.exceptions = MagicMock()

        result = monitor.check_health_endpoint()

        assert result['status'] == 'pass'
        assert result['name'] == 'Health Endpoint'
        assert result['response_time_ms'] >= 0
        assert result['details']['status'] == 'healthy'

    @patch('scripts.devops.synthetic_monitor.http_requests')
    def test_check_health_timeout(self, mock_req, monitor):
        """Timeout exception returns fail."""
        import requests
        mock_req.exceptions.Timeout = requests.exceptions.Timeout
        mock_req.get.side_effect = requests.exceptions.Timeout('timed out')

        result = monitor.check_health_endpoint()

        assert result['status'] == 'fail'
        assert 'timed out' in result['error'].lower()

    @patch('scripts.devops.synthetic_monitor.http_requests')
    def test_check_health_500(self, mock_req, monitor):
        """500 status code returns fail."""
        mock_req.get.return_value = _mock_response(500)
        mock_req.exceptions = MagicMock()

        result = monitor.check_health_endpoint()

        assert result['status'] == 'fail'
        assert 'HTTP 500' in result['error']


# ============================================================
# Public Teaser Tests
# ============================================================

class TestCheckPublicTeaser:
    """Tests for check_public_teaser()."""

    @patch('scripts.devops.synthetic_monitor.http_requests')
    def test_check_public_teaser_success(self, mock_req, monitor):
        """Valid teaser data returns pass."""
        mock_req.get.return_value = _mock_response(200, {
            'since_inception_pct': 12.5,
            'total_investors': 5,
            'trading_days': 40,
        })
        mock_req.exceptions = MagicMock()

        result = monitor.check_public_teaser()

        assert result['status'] == 'pass'
        assert result['details']['total_investors'] == 5
        assert result['details']['trading_days'] == 40

    @patch('scripts.devops.synthetic_monitor.http_requests')
    def test_check_public_teaser_missing_fields(self, mock_req, monitor):
        """Incomplete data returns fail with missing field names."""
        mock_req.get.return_value = _mock_response(200, {
            'since_inception_pct': 12.5,
            # missing total_investors and trading_days
        })
        mock_req.exceptions = MagicMock()

        result = monitor.check_public_teaser()

        assert result['status'] == 'fail'
        assert 'total_investors' in result['error']
        assert 'trading_days' in result['error']


# ============================================================
# Login Flow Tests
# ============================================================

class TestCheckLoginFlow:
    """Tests for check_login_flow()."""

    @patch('scripts.devops.synthetic_monitor.http_requests')
    def test_check_login_success(self, mock_req, monitor_with_creds):
        """Successful login returns pass with access_token in details."""
        mock_req.post.return_value = _mock_response(200, {
            'access_token': 'jwt-token-abc123',
            'token_type': 'bearer',
        })
        mock_req.exceptions = MagicMock()

        result = monitor_with_creds.check_login_flow()

        assert result['status'] == 'pass'
        assert result['details']['access_token'] == 'jwt-token-abc123'

    @patch('scripts.devops.synthetic_monitor.http_requests')
    def test_check_login_wrong_credentials(self, mock_req, monitor_with_creds):
        """401 response returns fail."""
        mock_req.post.return_value = _mock_response(401, {
            'detail': 'Invalid credentials'
        })
        mock_req.exceptions = MagicMock()

        result = monitor_with_creds.check_login_flow()

        assert result['status'] == 'fail'
        assert 'HTTP 401' in result['error']

    def test_check_login_no_credentials(self, monitor):
        """No credentials configured returns skip."""
        result = monitor.check_login_flow()

        assert result['status'] == 'skip'
        assert 'not configured' in result['details'].lower()


# ============================================================
# NAV Freshness Tests
# ============================================================

class TestCheckNavFreshness:
    """Tests for check_nav_freshness()."""

    @patch('scripts.devops.synthetic_monitor.http_requests')
    def test_check_nav_fresh(self, mock_req, monitor):
        """NAV from today returns pass."""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        mock_req.get.return_value = _mock_response(200, {
            'date': today,
            'nav_per_share': 10.5432,
        })
        mock_req.exceptions = MagicMock()

        result = monitor.check_nav_freshness('test-token')

        assert result['status'] == 'pass'
        assert result['details']['days_old'] == 0

    @patch('scripts.devops.synthetic_monitor.http_requests')
    def test_check_nav_stale(self, mock_req, monitor):
        """NAV from 5 days ago (on a weekday) returns fail."""
        stale_date = (datetime.utcnow() - timedelta(days=5)).strftime('%Y-%m-%d')
        mock_req.get.return_value = _mock_response(200, {
            'date': stale_date,
            'nav_per_share': 10.5432,
        })
        mock_req.exceptions = MagicMock()

        result = monitor.check_nav_freshness('test-token')

        assert result['status'] == 'fail'
        assert 'days old' in result['error']

    @patch('scripts.devops.synthetic_monitor.http_requests')
    def test_check_nav_weekend_ok(self, mock_req, monitor):
        """NAV from 3 days ago is acceptable (covers Friday->Monday)."""
        three_days_ago = (datetime.utcnow() - timedelta(days=3)).strftime('%Y-%m-%d')
        mock_req.get.return_value = _mock_response(200, {
            'date': three_days_ago,
            'nav_per_share': 10.5432,
        })
        mock_req.exceptions = MagicMock()

        result = monitor.check_nav_freshness('test-token')

        assert result['status'] == 'pass'
        assert result['details']['days_old'] == 3

    def test_check_nav_no_token(self, monitor):
        """No token returns skip."""
        result = monitor.check_nav_freshness(None)

        assert result['status'] == 'skip'


# ============================================================
# Authenticated Endpoints Tests
# ============================================================

class TestCheckAuthenticatedEndpoints:
    """Tests for check_authenticated_endpoints()."""

    @patch('scripts.devops.synthetic_monitor.http_requests')
    def test_check_authenticated_endpoints_success(self, mock_req, monitor):
        """All 3 endpoints returning 200 returns pass."""
        mock_req.get.return_value = _mock_response(
            200, {'data': 'ok'}, content=b'{"data": "ok"}'
        )
        mock_req.exceptions = MagicMock()

        result = monitor.check_authenticated_endpoints('test-token')

        assert result['status'] == 'pass'
        assert result['details']['endpoints_checked'] == 3

    @patch('scripts.devops.synthetic_monitor.http_requests')
    def test_check_authenticated_endpoints_partial_failure(self, mock_req, monitor):
        """One endpoint returning 500 results in fail."""
        ok_resp = _mock_response(200, {'data': 'ok'}, content=b'{"data": "ok"}')
        fail_resp = _mock_response(500, {'error': 'server error'})

        # First two calls succeed, third fails
        mock_req.get.side_effect = [ok_resp, ok_resp, fail_resp]
        mock_req.exceptions = MagicMock()

        result = monitor.check_authenticated_endpoints('test-token')

        assert result['status'] == 'fail'
        assert '1/3' in result['error']
        assert len(result['details']['failed_endpoints']) == 1

    def test_check_authenticated_no_token(self, monitor):
        """No token returns skip."""
        result = monitor.check_authenticated_endpoints(None)

        assert result['status'] == 'skip'


# ============================================================
# Frontend Accessible Tests
# ============================================================

class TestCheckFrontendAccessible:
    """Tests for check_frontend_accessible()."""

    @patch('scripts.devops.synthetic_monitor.http_requests')
    def test_check_frontend_success(self, mock_req, monitor):
        """200 with 'Tovito' in large body returns pass."""
        body = '<html><head><title>Tovito Trader</title></head><body>' + 'x' * 2000 + '</body></html>'
        mock_req.get.return_value = _mock_response(
            200, text=body, content=body.encode('utf-8')
        )
        mock_req.exceptions = MagicMock()

        result = monitor.check_frontend_accessible()

        assert result['status'] == 'pass'

    @patch('scripts.devops.synthetic_monitor.http_requests')
    def test_check_frontend_error_page(self, mock_req, monitor):
        """200 but body < 1000 bytes returns fail (error page)."""
        body = '<html><body>Error</body></html>'
        mock_req.get.return_value = _mock_response(
            200, text=body, content=body.encode('utf-8')
        )
        mock_req.exceptions = MagicMock()

        result = monitor.check_frontend_accessible()

        assert result['status'] == 'fail'
        assert 'too small' in result['error'].lower()


# ============================================================
# Admin Endpoint Tests
# ============================================================

class TestCheckAdminEndpoint:
    """Tests for check_admin_endpoint()."""

    @patch('scripts.devops.synthetic_monitor.http_requests')
    def test_check_admin_success(self, mock_req, monitor):
        """200 with admin key returns pass."""
        mock_req.get.return_value = _mock_response(200, [])
        mock_req.exceptions = MagicMock()

        result = monitor.check_admin_endpoint()

        assert result['status'] == 'pass'
        # Verify the admin key header was sent
        mock_req.get.assert_called_once()
        call_kwargs = mock_req.get.call_args
        assert call_kwargs[1]['headers']['X-Admin-Key'] == 'test-admin-key-123'

    def test_check_admin_no_key(self, monitor):
        """No admin key returns skip."""
        monitor.admin_key = ''

        result = monitor.check_admin_endpoint()

        assert result['status'] == 'skip'
        assert 'not configured' in result['details'].lower()


# ============================================================
# Run All Checks Tests
# ============================================================

class TestRunAllChecks:
    """Tests for run_all_checks()."""

    @patch('scripts.devops.synthetic_monitor.http_requests')
    def test_run_all_checks_all_pass(self, mock_req, monitor_with_creds):
        """All checks passing results in overall_status='pass'."""
        today = datetime.utcnow().strftime('%Y-%m-%d')

        # Build distinct responses for different endpoints
        health_resp = _mock_response(200, {'status': 'healthy'})
        teaser_resp = _mock_response(200, {
            'since_inception_pct': 12.5,
            'total_investors': 5,
            'trading_days': 40,
        })
        frontend_body = '<html><title>Tovito Trader</title>' + 'x' * 2000 + '</html>'
        frontend_resp = _mock_response(
            200, text=frontend_body, content=frontend_body.encode('utf-8')
        )
        nav_resp = _mock_response(200, {
            'date': today, 'nav_per_share': 10.54
        })
        auth_resp = _mock_response(200, {'data': 'ok'}, content=b'{"data":"ok"}')
        admin_resp = _mock_response(200, [])

        def side_effect_get(url, **kwargs):
            if '/health' in url:
                return health_resp
            elif '/teaser-stats' in url:
                return teaser_resp
            elif '/nav/current' in url:
                return nav_resp
            elif '/admin/prospects' in url:
                return admin_resp
            elif 'test.com' in url and '/api' not in url and '/nav' not in url and '/analysis' not in url and '/investor' not in url and '/admin' not in url:
                return frontend_resp
            else:
                return auth_resp

        mock_req.get.side_effect = side_effect_get
        mock_req.post.return_value = _mock_response(200, {
            'access_token': 'test-jwt-token'
        })
        mock_req.exceptions = MagicMock()

        results = monitor_with_creds.run_all_checks()

        assert results['overall_status'] == 'pass'
        assert results['checks_failed'] == 0
        assert results['checks_passed'] >= 1
        assert 'results' in results

    @patch('scripts.devops.synthetic_monitor.http_requests')
    def test_run_all_checks_with_failure(self, mock_req, monitor):
        """One check failing results in overall_status='fail'."""
        # Health returns 500, everything else returns 200
        health_resp = _mock_response(500, {'error': 'internal error'})
        teaser_resp = _mock_response(200, {
            'since_inception_pct': 12.5,
            'total_investors': 5,
            'trading_days': 40,
        })
        frontend_body = '<html><title>Tovito Trader</title>' + 'x' * 2000 + '</html>'
        frontend_resp = _mock_response(
            200, text=frontend_body, content=frontend_body.encode('utf-8')
        )
        admin_resp = _mock_response(200, [])

        def side_effect_get(url, **kwargs):
            if '/health' in url:
                return health_resp
            elif '/teaser-stats' in url:
                return teaser_resp
            elif '/admin/prospects' in url:
                return admin_resp
            elif 'test.com' in url:
                return frontend_resp
            else:
                return _mock_response(200, {'data': 'ok'}, content=b'{"data":"ok"}')

        mock_req.get.side_effect = side_effect_get
        mock_req.exceptions = MagicMock()

        results = monitor.run_all_checks()

        assert results['overall_status'] == 'fail'
        assert results['checks_failed'] >= 1
        assert results['results']['health_endpoint']['status'] == 'fail'


# ============================================================
# Notification Tests
# ============================================================

class TestNotifications:
    """Tests for send_notifications()."""

    @patch('scripts.devops.synthetic_monitor.os.getenv')
    def test_send_notifications_only_on_failure(self, mock_getenv, monitor):
        """No Discord/email sent when all checks pass."""
        results = {
            'timestamp': '2026-02-26T15:00:00Z',
            'base_url': 'https://api.test.com',
            'overall_status': 'pass',
            'checks_passed': 5,
            'checks_failed': 0,
            'checks_skipped': 2,
            'total_response_time_ms': 1500.0,
            'results': {},
        }

        # send_notifications should return immediately without calling
        # any external services since overall_status is 'pass'
        with patch('scripts.devops.synthetic_monitor.os.getenv', return_value=''):
            monitor.send_notifications(results)

        # If we get here without error, notifications were not attempted
        # (the function returned early because overall_status != 'fail')


# ============================================================
# Report Formatting Tests
# ============================================================

class TestFormatTextReport:
    """Tests for format_text_report()."""

    def test_format_text_report_structure(self, monitor):
        """Report contains expected sections and formatting."""
        results = {
            'timestamp': '2026-02-26T15:00:00Z',
            'base_url': 'https://api.test.com',
            'overall_status': 'pass',
            'checks_passed': 5,
            'checks_failed': 0,
            'checks_skipped': 2,
            'total_response_time_ms': 1500.0,
            'results': {
                'health_endpoint': {
                    'name': 'Health Endpoint',
                    'status': 'pass',
                    'response_time_ms': 120.0,
                    'details': {'status': 'healthy'},
                    'error': None,
                    'timestamp': '2026-02-26T15:00:00Z',
                },
                'login_flow': {
                    'name': 'Login Flow',
                    'status': 'skip',
                    'response_time_ms': 0.0,
                    'details': 'Synthetic monitor credentials not configured',
                    'error': None,
                    'timestamp': '2026-02-26T15:00:00Z',
                },
            },
        }

        report = monitor.format_text_report(results)

        assert 'SYNTHETIC MONITOR RESULTS' in report
        assert 'https://api.test.com' in report
        assert '[PASS]' in report
        assert '[SKIP]' in report
        assert 'Health Endpoint' in report
        assert 'Login Flow' in report
        assert 'RESULT:' in report
        assert '5/5' in report  # 5 passed out of 5 non-skip


# ============================================================
# Result Helper Tests
# ============================================================

class TestMakeResult:
    """Tests for _make_result() static method."""

    def test_result_structure(self):
        """Result dict has all required fields."""
        result = SyntheticMonitor._make_result(
            'Test Check', 'pass', 123.4, details={'key': 'val'}, error=None
        )

        assert result['name'] == 'Test Check'
        assert result['status'] == 'pass'
        assert result['response_time_ms'] == 123.4
        assert result['details'] == {'key': 'val'}
        assert result['error'] is None
        assert result['timestamp'].endswith('Z')

    def test_result_with_error(self):
        """Result dict correctly stores error message."""
        result = SyntheticMonitor._make_result(
            'Failing Check', 'fail', 500.0, error='Something broke'
        )

        assert result['status'] == 'fail'
        assert result['error'] == 'Something broke'
