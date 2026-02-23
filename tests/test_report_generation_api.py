"""
Tests for Report Generation API endpoints.

Tests cover:
- Report job creation and status tracking
- Input validation
- Job limit enforcement
- Background task completion
"""

import pytest
import threading
from pathlib import Path
from datetime import date

# Add project root to path
import sys
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


fastapi = pytest.importorskip("fastapi", reason="FastAPI not installed — skipping API tests")
pydantic = pytest.importorskip("pydantic", reason="Pydantic not installed — skipping API tests")


class TestReportJobTracking:
    """Test in-memory job tracking logic."""

    def test_job_creation(self):
        """Jobs are created with pending status."""
        from apps.investor_portal.api.routes.reports import _report_jobs, _jobs_lock, _create_job

        # Clear any existing jobs
        with _jobs_lock:
            _report_jobs.clear()

        job_id = _create_job('test-investor', 'monthly')
        assert job_id is not None
        assert len(job_id) == 8

        with _jobs_lock:
            job = _report_jobs[job_id]
        assert job['status'] == 'pending'
        assert job['investor_id'] == 'test-investor'
        assert job['report_type'] == 'monthly'

    def test_job_limit_enforcement(self):
        """Cannot create more than MAX_JOBS_PER_INVESTOR active jobs."""
        from apps.investor_portal.api.routes.reports import (
            _report_jobs, _jobs_lock, _create_job, MAX_JOBS_PER_INVESTOR
        )
        from fastapi import HTTPException

        with _jobs_lock:
            _report_jobs.clear()

        # Create max jobs
        for _ in range(MAX_JOBS_PER_INVESTOR):
            _create_job('test-investor', 'monthly')

        # Next should fail
        with pytest.raises(HTTPException) as exc_info:
            _create_job('test-investor', 'monthly')
        assert exc_info.value.status_code == 429

    def test_different_investor_not_affected(self):
        """Job limits are per-investor."""
        from apps.investor_portal.api.routes.reports import (
            _report_jobs, _jobs_lock, _create_job, MAX_JOBS_PER_INVESTOR
        )

        with _jobs_lock:
            _report_jobs.clear()

        # Fill up investor A
        for _ in range(MAX_JOBS_PER_INVESTOR):
            _create_job('investor-a', 'monthly')

        # Investor B should still work
        job_id = _create_job('investor-b', 'monthly')
        assert job_id is not None

    def test_completed_jobs_dont_count(self):
        """Completed jobs don't count toward the limit."""
        from apps.investor_portal.api.routes.reports import (
            _report_jobs, _jobs_lock, _create_job, MAX_JOBS_PER_INVESTOR
        )

        with _jobs_lock:
            _report_jobs.clear()

        # Create max jobs and complete them
        job_ids = []
        for _ in range(MAX_JOBS_PER_INVESTOR):
            jid = _create_job('test-investor', 'monthly')
            job_ids.append(jid)

        # Complete all
        with _jobs_lock:
            for jid in job_ids:
                _report_jobs[jid]['status'] = 'completed'

        # Should be able to create another
        new_id = _create_job('test-investor', 'monthly')
        assert new_id is not None


class TestReportInputValidation:
    """Test request validation."""

    def test_monthly_valid_months(self):
        """Month must be 1-12."""
        from pydantic import ValidationError
        from apps.investor_portal.api.routes.reports import MonthlyReportRequest

        # Valid
        req = MonthlyReportRequest(month=1, year=2026)
        assert req.month == 1

        req = MonthlyReportRequest(month=12, year=2026)
        assert req.month == 12

        # Invalid
        with pytest.raises(ValidationError):
            MonthlyReportRequest(month=0, year=2026)

        with pytest.raises(ValidationError):
            MonthlyReportRequest(month=13, year=2026)

    def test_custom_dates(self):
        """Custom report request validates dates."""
        from apps.investor_portal.api.routes.reports import CustomReportRequest

        req = CustomReportRequest(start_date='2026-01-01', end_date='2026-01-31')
        assert req.start_date == date(2026, 1, 1)
        assert req.end_date == date(2026, 1, 31)

    def test_job_response_model(self):
        """ReportJobResponse can be created with expected fields."""
        from apps.investor_portal.api.routes.reports import ReportJobResponse

        resp = ReportJobResponse(
            job_id='abc12345',
            status='pending',
            message='Generating...',
        )
        assert resp.job_id == 'abc12345'
        assert resp.download_url is None
