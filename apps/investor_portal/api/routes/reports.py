"""
Report Generation Routes
========================

POST /reports/monthly     - Generate monthly statement on demand
POST /reports/custom      - Generate custom date-range report
POST /reports/ytd         - Generate year-to-date summary
GET  /reports/status/{id} - Check generation status
GET  /reports/download/{id} - Download generated report
"""

import logging
import sqlite3
import threading
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..dependencies import get_current_user, CurrentUser
from ..config import get_database_path

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory job tracking (MVP — sufficient for single-server deployment)
_report_jobs = {}
_jobs_lock = threading.Lock()

# Maximum concurrent jobs per investor (prevent abuse)
MAX_JOBS_PER_INVESTOR = 3


# ============================================================
# Request / Response Models
# ============================================================

class MonthlyReportRequest(BaseModel):
    """Request to generate a monthly statement"""
    month: int = Field(..., ge=1, le=12, description="Month (1-12)")
    year: int = Field(..., ge=2026, le=2030, description="Year")


class CustomReportRequest(BaseModel):
    """Request to generate a custom date-range report"""
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")


class ReportJobResponse(BaseModel):
    """Response when a report job is created"""
    job_id: str
    status: str
    message: str
    download_url: Optional[str] = None


class ReportStatusResponse(BaseModel):
    """Response when checking job status"""
    job_id: str
    status: str
    message: str
    download_url: Optional[str] = None


# ============================================================
# Background Report Generation
# ============================================================

def _generate_monthly_task(job_id: str, db_path: Path, investor_id: str,
                           month: int, year: int):
    """Background task: generate monthly PDF report."""
    try:
        with _jobs_lock:
            _report_jobs[job_id]['status'] = 'generating'

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Import the report generation function from the CLI script
        import sys
        scripts_dir = db_path.parent.parent / 'scripts' / 'reporting'
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        project_root = db_path.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from generate_monthly_report import generate_monthly_report

        result = generate_monthly_report(cursor, investor_id, month, year, use_pdf=True)
        conn.close()

        if result:
            report_path, _, _ = result
            with _jobs_lock:
                _report_jobs[job_id]['status'] = 'completed'
                _report_jobs[job_id]['path'] = str(report_path)
                _report_jobs[job_id]['message'] = f'Report ready for {month}/{year}'
        else:
            with _jobs_lock:
                _report_jobs[job_id]['status'] = 'failed'
                _report_jobs[job_id]['message'] = 'Report generation returned no data'

    except Exception as e:
        logger.error("Report generation failed for job %s: %s", job_id, e)
        with _jobs_lock:
            _report_jobs[job_id]['status'] = 'failed'
            _report_jobs[job_id]['message'] = f'Generation failed: {str(e)[:200]}'


def _generate_custom_task(job_id: str, db_path: Path, investor_id: str,
                          start_date: str, end_date: str):
    """Background task: generate custom date-range PDF report."""
    try:
        with _jobs_lock:
            _report_jobs[job_id]['status'] = 'generating'

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        import sys
        project_root = db_path.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        # Get investor info
        cursor.execute("""
            SELECT investor_id, name, email, current_shares, net_investment
            FROM investors WHERE investor_id = ? AND status = 'Active'
        """, (investor_id,))
        investor_info = cursor.fetchone()
        if not investor_info:
            raise ValueError("Investor not found or inactive")

        # Get NAV data for the period
        cursor.execute("""
            SELECT date, nav_per_share, daily_change_percent
            FROM daily_nav
            WHERE date BETWEEN ? AND ?
            ORDER BY date ASC
        """, (start_date, end_date))
        nav_rows = [dict(r) for r in cursor.fetchall()]

        if not nav_rows:
            raise ValueError("No NAV data for the requested period")

        # Get transactions in period
        cursor.execute("""
            SELECT date, transaction_type, amount, shares_transacted, share_price
            FROM transactions
            WHERE investor_id = ? AND date BETWEEN ? AND ?
            AND (is_deleted IS NULL OR is_deleted = 0)
            ORDER BY date
        """, (investor_id, start_date, end_date))
        transactions = [dict(r) for r in cursor.fetchall()]

        conn.close()

        # Generate a simple PDF using the chart functions
        from src.reporting.charts import generate_benchmark_chart
        from src.market_data.benchmarks import get_benchmark_data

        benchmark_data = get_benchmark_data(
            db_path, days=0, start_date=start_date, end_date=end_date
        )

        chart_path = generate_benchmark_chart(nav_rows, benchmark_data)

        # Build output path
        output_dir = db_path.parent / 'reports'
        output_dir.mkdir(exist_ok=True, parents=True)

        s = start_date.replace('-', '')
        e = end_date.replace('-', '')
        filename = f"custom_report_{investor_id}_{s}_{e}.pdf"
        output_path = output_dir / filename

        # Generate PDF using ReportLab
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
                Image as RLImage
            )
            from reportlab.lib import colors as rl_colors

            doc = SimpleDocTemplate(str(output_path), pagesize=letter,
                                    topMargin=0.75 * inch, bottomMargin=0.75 * inch)
            styles = getSampleStyleSheet()
            elements = []

            # Title
            elements.append(Paragraph(
                "TOVITO TRADER CUSTOM REPORT",
                styles['Title']
            ))
            elements.append(Paragraph(
                f"Period: {start_date} to {end_date}",
                styles['Normal']
            ))
            elements.append(Spacer(1, 0.25 * inch))

            # Account summary
            name = investor_info['name']
            shares = investor_info['current_shares'] or 0
            start_nav = nav_rows[0]['nav_per_share']
            end_nav = nav_rows[-1]['nav_per_share']
            period_return = ((end_nav / start_nav) - 1) * 100 if start_nav else 0
            current_value = shares * end_nav

            summary_data = [
                ['Investor', name],
                ['Period', f"{start_date} to {end_date}"],
                ['Start NAV', f"${start_nav:.4f}"],
                ['End NAV', f"${end_nav:.4f}"],
                ['Period Return', f"{period_return:+.2f}%"],
                ['Current Shares', f"{shares:.4f}"],
                ['Current Value', f"${current_value:,.2f}"],
                ['Trading Days', str(len(nav_rows))],
            ]

            t = Table(summary_data, colWidths=[2.5 * inch, 4 * inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), rl_colors.Color(0.95, 0.95, 0.95)),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, rl_colors.Color(0.8, 0.8, 0.8)),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 0.3 * inch))

            # Transactions in period
            if transactions:
                elements.append(Paragraph("Transactions", styles['Heading2']))
                txn_data = [['Date', 'Type', 'Amount', 'Shares']]
                for txn in transactions:
                    txn_data.append([
                        txn['date'],
                        txn['transaction_type'],
                        f"${abs(txn['amount']):,.2f}",
                        f"{txn.get('shares_transacted', 0):.4f}",
                    ])
                tt = Table(txn_data, colWidths=[1.5 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch])
                tt.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), rl_colors.Color(0.12, 0.23, 0.37)),
                    ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.white),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 0.5, rl_colors.Color(0.8, 0.8, 0.8)),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                elements.append(tt)
                elements.append(Spacer(1, 0.3 * inch))

            # Chart
            if chart_path and chart_path.exists():
                elements.append(Paragraph("Performance vs. Benchmarks", styles['Heading2']))
                elements.append(RLImage(str(chart_path), width=6.5 * inch, height=3.5 * inch))
                chart_path.unlink(missing_ok=True)

            # Disclaimer
            elements.append(Spacer(1, 0.5 * inch))
            elements.append(Paragraph(
                f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
                "Tax policy: 37% on realized gains, settled quarterly.",
                styles['Normal']
            ))

            doc.build(elements)

        except ImportError:
            # Fallback: text report
            with open(output_path.with_suffix('.txt'), 'w') as f:
                f.write(f"Custom Report: {start_date} to {end_date}\n")
                f.write(f"Start NAV: ${nav_rows[0]['nav_per_share']:.4f}\n")
                f.write(f"End NAV: ${nav_rows[-1]['nav_per_share']:.4f}\n")
                f.write(f"Period Return: {period_return:+.2f}%\n")
            output_path = output_path.with_suffix('.txt')

        with _jobs_lock:
            _report_jobs[job_id]['status'] = 'completed'
            _report_jobs[job_id]['path'] = str(output_path)
            _report_jobs[job_id]['message'] = f'Report ready ({start_date} to {end_date})'

    except Exception as e:
        logger.error("Custom report failed for job %s: %s", job_id, e)
        with _jobs_lock:
            _report_jobs[job_id]['status'] = 'failed'
            _report_jobs[job_id]['message'] = f'Generation failed: {str(e)[:200]}'


def _generate_ytd_task(job_id: str, db_path: Path, investor_id: str, year: int):
    """Background task: generate YTD summary by calling monthly for each month."""
    try:
        today = date.today()
        start = f"{year}-01-01"
        end = str(today) if year == today.year else f"{year}-12-31"

        # Delegate to custom report logic
        _generate_custom_task(job_id, db_path, investor_id, start, end)

        # Update message to reflect YTD
        with _jobs_lock:
            if _report_jobs[job_id]['status'] == 'completed':
                _report_jobs[job_id]['message'] = f'YTD report ready ({year})'

    except Exception as e:
        logger.error("YTD report failed for job %s: %s", job_id, e)
        with _jobs_lock:
            _report_jobs[job_id]['status'] = 'failed'
            _report_jobs[job_id]['message'] = f'Generation failed: {str(e)[:200]}'


# ============================================================
# Helper: create a job and check limits
# ============================================================

def _create_job(investor_id: str, report_type: str) -> str:
    """Create a new job entry. Raises if too many active jobs."""
    with _jobs_lock:
        active = sum(
            1 for j in _report_jobs.values()
            if j.get('investor_id') == investor_id
            and j['status'] in ('pending', 'generating')
        )
        if active >= MAX_JOBS_PER_INVESTOR:
            raise HTTPException(
                status_code=429,
                detail="Too many report jobs in progress. Please wait."
            )

        job_id = uuid.uuid4().hex[:8]
        _report_jobs[job_id] = {
            'status': 'pending',
            'message': 'Queued for generation...',
            'path': None,
            'investor_id': investor_id,
            'report_type': report_type,
            'created_at': datetime.now().isoformat(),
        }
        return job_id


# ============================================================
# Routes
# ============================================================

@router.post("/monthly", response_model=ReportJobResponse, status_code=202)
async def generate_monthly(
    request: MonthlyReportRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Generate a monthly statement for the authenticated investor.

    Returns 202 Accepted with a job_id. Poll /reports/status/{job_id}
    for completion, then download via /reports/download/{job_id}.
    """
    job_id = _create_job(user.investor_id, 'monthly')

    db_path = get_database_path()
    background_tasks.add_task(
        _generate_monthly_task, job_id, db_path,
        user.investor_id, request.month, request.year
    )

    return ReportJobResponse(
        job_id=job_id,
        status='pending',
        message=f'Generating {request.month}/{request.year} statement...',
    )


@router.post("/custom", response_model=ReportJobResponse, status_code=202)
async def generate_custom(
    request: CustomReportRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Generate a custom date-range report for the authenticated investor.
    """
    if request.end_date <= request.start_date:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")

    job_id = _create_job(user.investor_id, 'custom')

    db_path = get_database_path()
    background_tasks.add_task(
        _generate_custom_task, job_id, db_path,
        user.investor_id, str(request.start_date), str(request.end_date)
    )

    return ReportJobResponse(
        job_id=job_id,
        status='pending',
        message=f'Generating report ({request.start_date} to {request.end_date})...',
    )


@router.post("/ytd", response_model=ReportJobResponse, status_code=202)
async def generate_ytd(
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    year: int = None,
):
    """
    Generate a year-to-date summary report for the authenticated investor.
    """
    if year is None:
        year = date.today().year

    job_id = _create_job(user.investor_id, 'ytd')

    db_path = get_database_path()
    background_tasks.add_task(
        _generate_ytd_task, job_id, db_path,
        user.investor_id, year
    )

    return ReportJobResponse(
        job_id=job_id,
        status='pending',
        message=f'Generating {year} YTD report...',
    )


@router.get("/status/{job_id}", response_model=ReportStatusResponse)
async def get_report_status(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Check report generation status.
    """
    with _jobs_lock:
        job = _report_jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get('investor_id') != user.investor_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    download_url = f"/reports/download/{job_id}" if job['status'] == 'completed' else None

    return ReportStatusResponse(
        job_id=job_id,
        status=job['status'],
        message=job['message'],
        download_url=download_url,
    )


@router.get("/download/{job_id}")
async def download_report(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Download a generated report PDF.
    """
    with _jobs_lock:
        job = _report_jobs.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get('investor_id') != user.investor_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if job['status'] != 'completed':
        raise HTTPException(status_code=409, detail="Report not ready yet")

    report_path = Path(job['path'])
    if not report_path.exists():
        raise HTTPException(status_code=410, detail="Report file no longer available")

    return FileResponse(
        path=str(report_path),
        media_type='application/pdf',
        filename=report_path.name,
    )
