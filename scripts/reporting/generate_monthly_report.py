"""
Generate Monthly Account Statements with PDF and Email Capability
ENHANCED VERSION - Includes all data fields from original reports

Creates professional PDF reports and emails them to investors.

Usage:
    python scripts/generate_monthly_report.py --month 1 --year 2026
    python scripts/generate_monthly_report.py --month 1 --year 2026 --email
    python scripts/generate_monthly_report.py --month 1 --year 2026 --investor 20260101-01A --email
"""

import sqlite3
import argparse
from pathlib import Path
from datetime import datetime
import sys
import os

# Add scripts/ directory to path for imports (email_adapter.py lives there)
sys.path.insert(0, str(Path(__file__).parent.parent))

# Add project root to path for src/ imports (charts, brokerage)
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Try to import PDF library
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
        Image as RLImage
    )
    from reportlab.lib import colors
    HAS_PDF = True
except ImportError:
    HAS_PDF = False
    print("⚠️  reportlab not installed - will generate text reports only")
    print("   To enable PDF: pip install reportlab")

# Try to import chart generation
try:
    from src.reporting.charts import (
        generate_nav_chart,
        generate_investor_value_chart,
        generate_holdings_chart,
        generate_benchmark_chart,
    )
    HAS_CHARTS = True
except ImportError:
    HAS_CHARTS = False

# Try to import email service
try:
    from email_adapter import send_email_with_attachment
    HAS_EMAIL = True
except ImportError:
    HAS_EMAIL = False


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def get_investor_info(cursor, investor_id):
    """Get investor information"""
    cursor.execute("""
        SELECT investor_id, name, email, current_shares, net_investment
        FROM investors
        WHERE investor_id = ? AND status = 'Active'
    """, (investor_id,))
    return cursor.fetchone()


def get_active_investors(cursor):
    """Get all active investors"""
    cursor.execute("""
        SELECT investor_id, name, email
        FROM investors
        WHERE status = 'Active'
        ORDER BY investor_id
    """)
    return cursor.fetchall()


def get_current_nav(cursor):
    """Get current NAV"""
    cursor.execute("""
        SELECT nav_per_share, total_portfolio_value, date
        FROM daily_nav
        ORDER BY date DESC
        LIMIT 1
    """)
    return cursor.fetchone()


def get_month_start_nav(cursor, year, month):
    """Get NAV at start of month (January 1 for first month)"""
    if month == 1:
        # Get January 1st NAV
        cursor.execute("""
            SELECT nav_per_share
            FROM daily_nav
            WHERE date = ?
            LIMIT 1
        """, (f'{year}-01-01',))
    else:
        # Get last day of previous month
        cursor.execute("""
            SELECT nav_per_share
            FROM daily_nav
            WHERE strftime('%Y', date) = ?
            AND strftime('%m', date) = ?
            ORDER BY date DESC
            LIMIT 1
        """, (str(year), f"{month-1:02d}"))
    
    result = cursor.fetchone()
    return result[0] if result else None


def get_monthly_transactions(cursor, investor_id, month, year):
    """Get transactions for the month with NAV at time of transaction"""
    cursor.execute("""
        SELECT 
            t.date, 
            t.transaction_type, 
            t.amount, 
            t.shares_transacted,
            (SELECT nav_per_share FROM daily_nav WHERE date <= t.date ORDER BY date DESC LIMIT 1) as nav_at_time
        FROM transactions t
        WHERE t.investor_id = ?
        AND strftime('%Y', t.date) = ?
        AND strftime('%m', t.date) = ?
        ORDER BY t.date
    """, (investor_id, str(year), f"{month:02d}"))
    return cursor.fetchall()


def get_monthly_contribution_withdrawal_totals(cursor, investor_id, month, year):
    """Get total contributions and withdrawals for the month"""
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN transaction_type IN ('Initial', 'Contribution') THEN amount ELSE 0 END), 0) as contributions,
            COALESCE(SUM(CASE WHEN transaction_type = 'Withdrawal' THEN ABS(amount) ELSE 0 END), 0) as withdrawals
        FROM transactions
        WHERE investor_id = ?
        AND strftime('%Y', date) = ?
        AND strftime('%m', date) = ?
    """, (investor_id, str(year), f"{month:02d}"))
    
    result = cursor.fetchone()
    contributions = result[0] if result and result[0] is not None else 0
    withdrawals = result[1] if result and result[1] is not None else 0
    return (contributions, withdrawals)


def get_portfolio_allocation(cursor, investor_id, current_value, total_portfolio_value):
    """Calculate investor's % of total portfolio"""
    if total_portfolio_value > 0:
        return (current_value / total_portfolio_value) * 100
    return 0


# ============================================================
# CHART DATA QUERIES
# ============================================================

def get_nav_history_for_chart(cursor, max_days=365):
    """
    Get NAV history for the NAV time series chart.

    Returns up to max_days of NAV records ordered by date.

    Returns:
        list of dicts: [{'date': 'YYYY-MM-DD', 'nav_per_share': float}, ...]
    """
    cursor.execute("""
        SELECT date, nav_per_share
        FROM daily_nav
        ORDER BY date DESC
        LIMIT ?
    """, (max_days,))

    rows = cursor.fetchall()
    # Reverse to get chronological order
    return [{'date': row[0], 'nav_per_share': row[1]} for row in reversed(rows)]


def get_trade_counts_by_date(cursor, max_days=365):
    """
    Get daily trade counts for chart secondary Y-axis.

    Only counts actual trades (category='Trade'), not ACH/dividends.

    Returns:
        list of dicts: [{'date': 'YYYY-MM-DD', 'trade_count': int}, ...]
    """
    try:
        cursor.execute("""
            SELECT date, COUNT(*) as trade_count
            FROM trades
            WHERE category = 'Trade'
            GROUP BY date
            ORDER BY date DESC
            LIMIT ?
        """, (max_days,))

        rows = cursor.fetchall()
        return [{'date': row[0], 'trade_count': row[1]} for row in reversed(rows)]
    except Exception:
        # Trades table may not exist yet if migration hasn't run
        return []


def get_investor_transaction_history(cursor, investor_id):
    """
    Get all transactions for an investor (for chart event markers
    and share history reconstruction).

    Returns:
        list of dicts with 'date', 'transaction_type', 'amount', 'shares_transacted'
    """
    cursor.execute("""
        SELECT date, transaction_type, amount, shares_transacted
        FROM transactions
        WHERE investor_id = ?
        ORDER BY date
    """, (investor_id,))

    return [
        {
            'date': row[0],
            'transaction_type': row[1],
            'amount': row[2],
            'shares_transacted': row[3],
        }
        for row in cursor.fetchall()
    ]


def get_current_positions(cursor):
    """
    Get current positions from the most recent holdings snapshot.

    Falls back to empty list if no snapshots exist yet.

    Returns:
        list of dicts with position data for the holdings chart
    """
    try:
        # Get the most recent snapshot date
        cursor.execute("""
            SELECT snapshot_id, date, source
            FROM holdings_snapshots
            ORDER BY date DESC, snapshot_id DESC
            LIMIT 1
        """)
        latest = cursor.fetchone()

        if not latest:
            return []

        latest_date = latest[1]

        # Get all snapshots for this date (could be multiple brokerages)
        cursor.execute("""
            SELECT snapshot_id FROM holdings_snapshots
            WHERE date = ?
        """, (latest_date,))

        snapshot_ids = [row[0] for row in cursor.fetchall()]

        if not snapshot_ids:
            return []

        # Get all positions from these snapshots
        placeholders = ','.join('?' * len(snapshot_ids))
        cursor.execute(f"""
            SELECT symbol, underlying_symbol, quantity, instrument_type,
                   average_open_price, close_price, market_value,
                   cost_basis, unrealized_pl, option_type, strike,
                   expiration_date, multiplier
            FROM position_snapshots
            WHERE snapshot_id IN ({placeholders})
        """, snapshot_ids)

        return [
            {
                'symbol': row[0],
                'underlying_symbol': row[1],
                'quantity': row[2],
                'instrument_type': row[3],
                'average_open_price': row[4],
                'close_price': row[5],
                'market_value': row[6],
                'cost_basis': row[7],
                'unrealized_pl': row[8],
                'option_type': row[9],
                'strike': row[10],
                'expiration_date': row[11],
                'multiplier': row[12],
            }
            for row in cursor.fetchall()
        ]

    except Exception:
        # Holdings tables may not exist yet
        return []


def generate_pdf_report(investor_info, nav_info, transactions, month, year, output_path):
    """Generate comprehensive PDF report"""
    
    if not HAS_PDF:
        return None
    
    investor_id, name, email, shares, net_investment = investor_info
    nav_per_share, total_portfolio, nav_date = nav_info
    
    # Calculate values
    current_value = shares * nav_per_share
    unrealized_gain = current_value - net_investment
    return_pct = (unrealized_gain / net_investment * 100) if net_investment > 0 else 0
    
    # Get month start NAV
    conn = sqlite3.connect(get_database_path())
    cursor = conn.cursor()
    start_nav = get_month_start_nav(cursor, year, month)
    
    # Get monthly totals
    contributions, withdrawals = get_monthly_contribution_withdrawal_totals(cursor, investor_id, month, year)
    
    # Calculate NAV change
    nav_change_pct = 0
    if start_nav and start_nav > 0:
        nav_change_pct = ((nav_per_share - start_nav) / start_nav) * 100
    
    # Get portfolio allocation
    portfolio_allocation = get_portfolio_allocation(cursor, investor_id, current_value, total_portfolio)
    
    # Calculate tax
    tax_rate = 0.37
    tax_liability = unrealized_gain * tax_rate if unrealized_gain > 0 else 0
    after_tax_value = current_value - tax_liability
    
    conn.close()
    
    # Create PDF
    doc = SimpleDocTemplate(str(output_path), pagesize=letter,
                           topMargin=0.75*inch, bottomMargin=0.75*inch)
    elements = []
    styles = getSampleStyleSheet()
    
    month_name = datetime(year, month, 1).strftime('%B %Y')
    
    # ===== PAGE 1 =====
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=10,
        alignment=1  # Center
    )
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#444444'),
        spaceAfter=30,
        alignment=1
    )
    
    elements.append(Paragraph("TOVITO TRADER", title_style))
    elements.append(Paragraph("MONTHLY ACCOUNT STATEMENT", subtitle_style))
    elements.append(Paragraph(f"Period: {month_name}", styles['Heading3']))
    elements.append(Spacer(1, 0.2*inch))
    
    # Investor info
    investor_style = ParagraphStyle(
        'Investor',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#222222')
    )
    elements.append(Paragraph(f"<b>{name} ({investor_id})</b>", investor_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # ACCOUNT SUMMARY
    section_style = ParagraphStyle(
        'Section',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=10
    )
    elements.append(Paragraph("<b>ACCOUNT SUMMARY</b>", section_style))
    
    summary_data = [
        ['Current Shares:', f'{shares:,.4f}'],
        ['Net Investment:', f'${net_investment:,.2f}'],
        ['Current Value:', f'${current_value:,.2f}'],
        ['Total Gain/Loss:', f'${unrealized_gain:+,.2f} ({return_pct:+.2f}%)']
    ]
    
    summary_table = Table(summary_data, colWidths=[2.5*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # PERFORMANCE METRICS
    elements.append(Paragraph("<b>PERFORMANCE METRICS</b>", section_style))
    
    performance_data = [
        ['Starting NAV (January 1):', f'${start_nav:.4f}' if start_nav else 'N/A'],
        [f'Ending NAV ({month_name}):', f'${nav_per_share:.4f}'],
        ['NAV Change:', f'{nav_change_pct:+.2f}%'],
        ['Contributions This Month:', f'${contributions:,.2f}'],
        ['Withdrawals This Month:', f'${withdrawals:,.2f}']
    ]
    
    performance_table = Table(performance_data, colWidths=[2.5*inch, 2*inch])
    performance_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(performance_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # TRANSACTIONS THIS MONTH
    elements.append(Paragraph("<b>TRANSACTIONS THIS MONTH</b>", section_style))
    
    if transactions:
        trans_data = [['Date', 'Type', 'Amount', 'Shares', 'NAV']]
        for date, trans_type, amount, shares_trans, nav_at_time in transactions:
            trans_data.append([
                date,
                trans_type,
                f'${amount:,.2f}',
                f'{shares_trans:,.4f}' if shares_trans else '',
                f'${nav_at_time:.4f}' if nav_at_time else ''
            ])
        
        trans_table = Table(trans_data, colWidths=[1*inch, 1.3*inch, 1*inch, 1*inch, 0.9*inch])
        trans_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(trans_table)
    else:
        elements.append(Paragraph("No transactions this month", styles['Normal']))
    
    elements.append(Spacer(1, 0.3*inch))
    
    # TAX SUMMARY
    elements.append(Paragraph("<b>TAX SUMMARY</b>", section_style))
    
    eligible_withdrawal = after_tax_value

    tax_data = [
        ['Unrealized Gains:', f'${unrealized_gain:,.2f}'],
        ['Estimated Tax Liability (37%):', f'${tax_liability:,.2f}'],
        ['After-Tax Value:', f'${after_tax_value:,.2f}'],
        ['Eligible Withdrawal:', f'${eligible_withdrawal:,.2f}'],
    ]

    tax_table = Table(tax_data, colWidths=[2.5*inch, 2*inch])
    tax_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(tax_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # PORTFOLIO ALLOCATION
    elements.append(Paragraph("<b>PORTFOLIO ALLOCATION</b>", section_style))
    
    allocation_data = [
        ['Your Position:', f'{portfolio_allocation:.2f}% of total portfolio']
    ]
    
    allocation_table = Table(allocation_data, colWidths=[2.5*inch, 2*inch])
    allocation_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(allocation_table)
    
    # Footer for page 1
    elements.append(Spacer(1, 0.3*inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=1
    )

    # ===== CHART PAGES =====
    # Generate charts and insert as new pages between summary and disclaimer.
    # Gracefully skip if matplotlib is not installed or data is unavailable.
    chart_files = []  # Track temp files for cleanup
    page_num = 1

    if HAS_CHARTS and HAS_PDF:
        try:
            # Fetch chart data using a separate connection
            chart_conn = sqlite3.connect(get_database_path())
            chart_cursor = chart_conn.cursor()

            nav_history = get_nav_history_for_chart(chart_cursor)
            trade_counts = get_trade_counts_by_date(chart_cursor)
            investor_txns = get_investor_transaction_history(chart_cursor, investor_id)
            positions = get_current_positions(chart_cursor)

            chart_conn.close()

            has_chart_data = bool(nav_history) or bool(positions)

            if has_chart_data:
                # ===== PAGE 2: Performance Charts =====
                elements.append(PageBreak())
                page_num += 1

                elements.append(Paragraph("TOVITO TRADER", title_style))
                elements.append(Paragraph("PERFORMANCE CHARTS", subtitle_style))
                elements.append(Spacer(1, 0.2*inch))

                # NAV Performance Chart
                if nav_history:
                    try:
                        nav_chart_path = generate_nav_chart(
                            nav_history,
                            trade_counts=trade_counts if trade_counts else None,
                        )
                        chart_files.append(nav_chart_path)
                        elements.append(RLImage(
                            str(nav_chart_path),
                            width=6.5*inch,
                            height=3.5*inch,
                        ))
                        elements.append(Spacer(1, 0.2*inch))
                    except Exception as e:
                        elements.append(Paragraph(
                            f"<i>NAV chart unavailable: {e}</i>",
                            styles['Normal']
                        ))

                # Benchmark Comparison Chart
                if nav_history:
                    try:
                        from src.market_data.benchmarks import get_benchmark_data
                        benchmark_data = get_benchmark_data(
                            get_database_path(), days=365,
                        )
                        has_benchmarks = any(
                            len(v) > 0 for v in benchmark_data.values()
                        )
                        if has_benchmarks:
                            benchmark_chart_path = generate_benchmark_chart(
                                nav_history, benchmark_data,
                            )
                            chart_files.append(benchmark_chart_path)
                            elements.append(RLImage(
                                str(benchmark_chart_path),
                                width=6.5*inch,
                                height=3.5*inch,
                            ))
                            elements.append(Spacer(1, 0.2*inch))
                    except Exception as e:
                        elements.append(Paragraph(
                            f"<i>Benchmark chart unavailable: {e}</i>",
                            styles['Normal']
                        ))

                # Investor Account Value Chart
                if nav_history and shares > 0:
                    try:
                        value_chart_path = generate_investor_value_chart(
                            nav_history,
                            investor_shares=shares,
                            investor_transactions=investor_txns if investor_txns else None,
                        )
                        chart_files.append(value_chart_path)
                        elements.append(RLImage(
                            str(value_chart_path),
                            width=6.5*inch,
                            height=3.5*inch,
                        ))
                    except Exception as e:
                        elements.append(Paragraph(
                            f"<i>Account value chart unavailable: {e}</i>",
                            styles['Normal']
                        ))

                # ===== PAGE 3: Holdings Chart (if positions exist) =====
                if positions:
                    elements.append(PageBreak())
                    page_num += 1

                    elements.append(Paragraph("TOVITO TRADER", title_style))
                    elements.append(Paragraph("CURRENT HOLDINGS", subtitle_style))
                    elements.append(Spacer(1, 0.2*inch))

                    try:
                        holdings_chart_path = generate_holdings_chart(positions)
                        chart_files.append(holdings_chart_path)
                        elements.append(RLImage(
                            str(holdings_chart_path),
                            width=6.5*inch,
                            height=4.0*inch,
                        ))
                    except Exception as e:
                        elements.append(Paragraph(
                            f"<i>Holdings chart unavailable: {e}</i>",
                            styles['Normal']
                        ))

        except Exception as e:
            # Chart generation failed entirely — continue without charts
            print(f"  Charts skipped: {e}")

    # ===== FINAL PAGE: Disclaimer =====
    elements.append(PageBreak())
    page_num += 1

    elements.append(Paragraph("TOVITO TRADER", title_style))
    elements.append(Paragraph("MONTHLY ACCOUNT STATEMENT", subtitle_style))
    elements.append(Paragraph(f"Period: {month_name}", styles['Heading3']))
    elements.append(Spacer(1, 0.5*inch))

    # Disclaimer
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        alignment=4  # Justify
    )

    disclaimer_text = """
    This statement is for informational purposes only. Returns shown are gross returns before taxes.
    Tax liability is estimated at 37% (federal income tax rate) and represents the amount that will be
    withheld from your account for tax remittance. No action is required from you for tax filing - all
    gains pass through to the fund manager's income and are reported on their tax return.
    """

    elements.append(Paragraph(disclaimer_text, disclaimer_style))
    elements.append(Spacer(1, 0.5*inch))

    # Report generation info
    elements.append(Paragraph(f"<b>Report generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))

    # Build PDF
    doc.build(elements)

    # Cleanup temporary chart files
    for chart_file in chart_files:
        try:
            chart_file.unlink()
        except Exception:
            pass

    return output_path


def generate_text_report(investor_info, nav_info, transactions, month, year, output_path):
    """Generate comprehensive text report (fallback)"""
    
    investor_id, name, email, shares, net_investment = investor_info
    nav_per_share, total_portfolio, nav_date = nav_info
    
    # Calculate values
    current_value = shares * nav_per_share
    unrealized_gain = current_value - net_investment
    return_pct = (unrealized_gain / net_investment * 100) if net_investment > 0 else 0
    
    # Get additional data
    conn = sqlite3.connect(get_database_path())
    cursor = conn.cursor()
    start_nav = get_month_start_nav(cursor, year, month)
    contributions, withdrawals = get_monthly_contribution_withdrawal_totals(cursor, investor_id, month, year)
    
    nav_change_pct = 0
    if start_nav and start_nav > 0:
        nav_change_pct = ((nav_per_share - start_nav) / start_nav) * 100
    
    portfolio_allocation = get_portfolio_allocation(cursor, investor_id, current_value, total_portfolio)
    
    tax_rate = 0.37
    tax_liability = unrealized_gain * tax_rate if unrealized_gain > 0 else 0
    after_tax_value = current_value - tax_liability
    
    conn.close()
    
    month_name = datetime(year, month, 1).strftime('%B %Y')
    
    report = []
    report.append("=" * 80)
    report.append("TOVITO TRADER")
    report.append("MONTHLY ACCOUNT STATEMENT")
    report.append(f"Period: {month_name}")
    report.append("=" * 80)
    report.append("")
    report.append(f"{name} ({investor_id})")
    report.append("")
    
    report.append("ACCOUNT SUMMARY")
    report.append(f"Current Shares:          {shares:,.4f}")
    report.append(f"Net Investment:          ${net_investment:,.2f}")
    report.append(f"Current Value:           ${current_value:,.2f}")
    report.append(f"Total Gain/Loss:         ${unrealized_gain:+,.2f} ({return_pct:+.2f}%)")
    report.append("")
    
    report.append("PERFORMANCE METRICS")
    report.append(f"Starting NAV (January 1): ${start_nav:.4f}" if start_nav else "Starting NAV: N/A")
    report.append(f"Ending NAV ({month_name}): ${nav_per_share:.4f}")
    report.append(f"NAV Change:              {nav_change_pct:+.2f}%")
    report.append(f"Contributions This Month: ${contributions:,.2f}")
    report.append(f"Withdrawals This Month:   ${withdrawals:,.2f}")
    report.append("")
    
    if transactions:
        report.append("TRANSACTIONS THIS MONTH")
        report.append(f"{'Date':<12} {'Type':<15} {'Amount':<15} {'Shares':<15} {'NAV':<10}")
        report.append("-" * 80)
        for date, trans_type, amount, shares_trans, nav_at_time in transactions:
            shares_str = f"{shares_trans:,.4f}" if shares_trans else ""
            nav_str = f"${nav_at_time:.4f}" if nav_at_time else ""
            report.append(f"{date:<12} {trans_type:<15} ${amount:<14,.2f} {shares_str:<15} {nav_str:<10}")
        report.append("")
    else:
        report.append("TRANSACTIONS THIS MONTH")
        report.append("No transactions this month")
        report.append("")
    
    report.append("TAX SUMMARY")
    report.append(f"Unrealized Gains:              ${unrealized_gain:,.2f}")
    report.append(f"Estimated Tax Liability (37%): ${tax_liability:,.2f}")
    report.append(f"After-Tax Value:               ${after_tax_value:,.2f}")
    report.append(f"Eligible Withdrawal:           ${after_tax_value:,.2f}")
    report.append("")
    
    report.append("PORTFOLIO ALLOCATION")
    report.append(f"Your Position: {portfolio_allocation:.2f}% of total portfolio")
    report.append("")
    
    report.append("-" * 80)
    report.append("This statement is for informational purposes only. Returns shown are gross returns")
    report.append("before taxes. Tax liability is estimated at 37% (federal income tax rate) and")
    report.append("represents the amount that will be withheld from your account for tax remittance.")
    report.append("No action is required from you for tax filing - all gains pass through to the")
    report.append("fund manager's income and are reported on their tax return.")
    report.append("")
    report.append(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 80)
    
    # Save to file
    with open(output_path, 'w') as f:
        f.write('\n'.join(report))
    
    return output_path


def generate_monthly_report(cursor, investor_id, month, year, use_pdf=True):
    """
    Generate comprehensive monthly report for investor
    
    Returns: (report_path, investor_name, investor_email) or None if failed
    """
    
    # Get investor info
    investor_info = get_investor_info(cursor, investor_id)
    if not investor_info:
        print(f"❌ Investor {investor_id} not found or inactive")
        return None
    
    # Get current NAV
    nav_info = get_current_nav(cursor)
    if not nav_info:
        print(f"❌ No NAV data found")
        return None
    
    # Get transactions
    transactions = get_monthly_transactions(cursor, investor_id, month, year)
    
    # Create output directory
    output_dir = Path(__file__).parent.parent.parent / 'data' / 'reports'
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Generate report
    _, name, email, _, _ = investor_info
    
    if use_pdf and HAS_PDF:
        filename = f"monthly_statement_{investor_id}_{year}{month:02d}.pdf"
        output_path = output_dir / filename
        result = generate_pdf_report(investor_info, nav_info, transactions, month, year, output_path)
    else:
        filename = f"monthly_statement_{investor_id}_{year}{month:02d}.txt"
        output_path = output_dir / filename
        result = generate_text_report(investor_info, nav_info, transactions, month, year, output_path)
    
    if result:
        print(f"✅ Report generated: {output_path}")
        return output_path, name, email
    else:
        return None


def send_monthly_report(report_path, investor_name, investor_email, month, year):
    """Send monthly report via email"""
    
    if not HAS_EMAIL:
        print("❌ Email service not available")
        print("   Make sure email_adapter.py exists and is configured")
        return False
    
    if not investor_email:
        print(f"❌ No email address for {investor_name}")
        return False
    
    month_name = datetime(year, month, 1).strftime('%B %Y')
    
    subject = f"Tovito Trader - Monthly Statement - {month_name}"
    
    body = f"""Dear {investor_name},

Attached is your monthly account statement for {month_name}.

Summary:
• View your current position
• Review this month's transactions
• Track your investment returns

If you have any questions, please don't hesitate to reach out.

Best regards,
Tovito Trader Team

---
This is an automated message. Please do not reply directly to this email.
"""
    
    print(f"📧 Sending report to {investor_name} ({investor_email})...")
    
    try:
        file_extension = report_path.suffix
        attachment_name = f"Monthly_Statement_{month_name.replace(' ', '_')}{file_extension}"
        
        success = send_email_with_attachment(
            to_email=investor_email,
            subject=subject,
            body=body,
            attachment_path=str(report_path),
            attachment_name=attachment_name
        )
        
        if success:
            print(f"✅ Email sent successfully to {investor_email}")
            return True
        else:
            print(f"❌ Failed to send email to {investor_email}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description='Generate comprehensive monthly account statements')
    parser.add_argument('--month', type=int, help='Month (1-12) - defaults to current month')
    parser.add_argument('--year', type=int, help='Year (e.g., 2026) - defaults to current year')
    parser.add_argument('--investor', type=str, help='Specific investor ID (optional, generates for all if omitted)')
    parser.add_argument('--email', action='store_true', help='Send report via email')
    parser.add_argument('--text', action='store_true', help='Generate text report instead of PDF')
    parser.add_argument('--previous-month', action='store_true', help='Generate for previous month (useful for automation on 1st of month)')
    
    args = parser.parse_args()
    
    # Determine month and year
    now = datetime.now()
    
    if args.previous_month:
        # Use previous month (useful when running on 1st of new month)
        if now.month == 1:
            month = 12
            year = now.year - 1
        else:
            month = now.month - 1
            year = now.year
    else:
        # Use provided values or default to current
        month = args.month if args.month is not None else now.month
        year = args.year if args.year is not None else now.year
    
    # Validate month
    if not 1 <= month <= 12:
        print("❌ Month must be between 1 and 12")
        return
    
    try:
        db_path = get_database_path()
        
        if not db_path.exists():
            print(f"❌ Database not found: {db_path}")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 80)
        print("MONTHLY REPORT GENERATOR (ENHANCED)")
        print("=" * 80)
        print(f"Period: {datetime(year, month, 1).strftime('%B %Y')}")
        if HAS_PDF and not args.text:
            print("Format: PDF")
        else:
            print("Format: Text")
        if args.email:
            print("Mode: Generate and Email")
        else:
            print("Mode: Generate Only")
        print()
        
        # Determine which investors to process
        if args.investor:
            investors = [(args.investor, None, None)]
            print(f"Processing single investor: {args.investor}")
        else:
            investors = get_active_investors(cursor)
            print(f"Processing {len(investors)} active investors")
        
        print()
        
        # Generate reports
        generated_count = 0
        emailed_count = 0
        
        for investor_data in investors:
            investor_id = investor_data[0]
            
            result = generate_monthly_report(
                cursor, 
                investor_id, 
                month,
                year,
                use_pdf=(not args.text)
            )
            
            if result:
                report_path, name, email = result
                generated_count += 1
                
                # Send email if requested
                if args.email:
                    if send_monthly_report(report_path, name, email, month, year):
                        emailed_count += 1
                    print()
        
        # Summary
        print()
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Reports generated: {generated_count}")
        if args.email:
            print(f"Emails sent: {emailed_count}")
            if emailed_count < generated_count:
                print(f"⚠️  {generated_count - emailed_count} email(s) failed")
        print()
        
        if not args.email:
            print("💡 To email these reports, add --email flag:")
            print(f"   python scripts/generate_monthly_report.py --email")
        
        if not HAS_PDF:
            print()
            print("💡 To generate PDF reports, install reportlab:")
            print("   pip install reportlab")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
