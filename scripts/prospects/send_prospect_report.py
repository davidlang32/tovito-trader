"""
Send Prospect Report - Fund Performance Report for Potential Investors

Generates a professional fund-level performance report and emails to prospects.

Features:
- Fund performance overview (no individual investor details)
- CSV-based prospect list
- Personalized emails with PDF attachment
- Database logging of all communications
- Admin summary email

Usage:
    python scripts/send_prospect_report.py --month 1 --year 2026 --prospects prospects.csv
    python scripts/send_prospect_report.py --month 1 --year 2026 --prospects prospects.csv --test-email

CSV format:
    Name,Email
    John Doe,john@example.com
    Jane Smith,jane@example.com
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
import csv
import os
import argparse
from pathlib import Path
from datetime import datetime
from fpdf import FPDF
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Email service
try:
    from src.automation.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError as e:
    EMAIL_AVAILABLE = False
    print(f"⚠️  Email service not available: {e}")
    send_email = None


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def get_fund_stats(cursor, month, year):
    """Get fund-level statistics"""
    
    # Get month start and end dates
    from calendar import monthrange
    _, last_day = monthrange(year, month)
    
    month_start = f"{year}-{month:02d}-01"
    month_end = f"{year}-{month:02d}-{last_day:02d}"
    
    # Get NAV at start and end of month
    cursor.execute("""
        SELECT nav_per_share, total_portfolio_value, total_shares
        FROM nav_history
        WHERE date <= ?
        ORDER BY date DESC
        LIMIT 1
    """, (month_start,))
    start = cursor.fetchone()
    
    cursor.execute("""
        SELECT nav_per_share, total_portfolio_value, total_shares, date
        FROM nav_history
        WHERE date <= ?
        ORDER BY date DESC
        LIMIT 1
    """, (month_end,))
    end = cursor.fetchone()
    
    if not start or not end:
        return None
    
    start_nav, _, _ = start
    end_nav, portfolio_value, total_shares, last_date = end
    
    # Calculate returns
    monthly_return = ((end_nav - start_nav) / start_nav) * 100
    
    # Get YTD return (from Jan 1 to month end)
    ytd_start = f"{year}-01-01"
    cursor.execute("""
        SELECT nav_per_share
        FROM nav_history
        WHERE date >= ?
        ORDER BY date ASC
        LIMIT 1
    """, (ytd_start,))
    ytd_start_nav = cursor.fetchone()
    
    if ytd_start_nav:
        ytd_return = ((end_nav - ytd_start_nav[0]) / ytd_start_nav[0]) * 100
    else:
        ytd_return = monthly_return
    
    # Get number of active investors
    cursor.execute("SELECT COUNT(*) FROM investors WHERE status = 'Active'")
    num_investors = cursor.fetchone()[0]
    
    # Get inception date
    cursor.execute("SELECT MIN(date) FROM nav_history")
    inception_date = cursor.fetchone()[0]
    
    # Calculate inception return if possible
    cursor.execute("""
        SELECT nav_per_share FROM nav_history
        WHERE date = ?
    """, (inception_date,))
    inception_nav = cursor.fetchone()
    
    if inception_nav:
        inception_return = ((end_nav - inception_nav[0]) / inception_nav[0]) * 100
    else:
        inception_return = ytd_return
    
    return {
        'month': month,
        'year': year,
        'last_date': last_date,
        'nav_per_share': end_nav,
        'portfolio_value': portfolio_value,
        'total_shares': total_shares,
        'monthly_return': monthly_return,
        'ytd_return': ytd_return,
        'inception_return': inception_return,
        'num_investors': num_investors,
        'inception_date': inception_date
    }


class ProspectReport(FPDF):
    """PDF report generator for prospects"""
    
    def __init__(self, stats):
        super().__init__()
        self.stats = stats
        
    def header(self):
        """Page header"""
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Tovito Trader Fund', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(0, 5, 'Fund Performance Report', 0, 1, 'C')
        month_name = datetime(self.stats['year'], self.stats['month'], 1).strftime('%B %Y')
        self.cell(0, 5, month_name, 0, 1, 'C')
        self.ln(5)
        
    def footer(self):
        """Page footer"""
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')


def generate_prospect_report(stats, output_path):
    """Generate prospect PDF report"""
    
    pdf = ProspectReport(stats)
    pdf.add_page()
    
    # Fund Overview Section
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Fund Overview', 0, 1)
    pdf.set_font('Arial', '', 10)
    
    pdf.cell(0, 6, f"Net Asset Value (NAV): ${stats['nav_per_share']:.4f} per share", 0, 1)
    pdf.cell(0, 6, f"Total Assets Under Management: ${stats['portfolio_value']:,.2f}", 0, 1)
    pdf.cell(0, 6, f"Number of Investors: {stats['num_investors']}", 0, 1)
    pdf.cell(0, 6, f"Inception Date: {stats['inception_date']}", 0, 1)
    pdf.cell(0, 6, f"Last Update: {stats['last_date']}", 0, 1)
    pdf.ln(5)
    
    # Performance Section
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Performance', 0, 1)
    pdf.set_font('Arial', 'B', 10)
    
    # Monthly return
    color = (0, 128, 0) if stats['monthly_return'] >= 0 else (255, 0, 0)
    pdf.set_text_color(*color)
    pdf.cell(0, 6, f"Monthly Return: {stats['monthly_return']:+.2f}%", 0, 1)
    
    # YTD return
    color = (0, 128, 0) if stats['ytd_return'] >= 0 else (255, 0, 0)
    pdf.set_text_color(*color)
    pdf.cell(0, 6, f"Year-to-Date Return: {stats['ytd_return']:+.2f}%", 0, 1)
    
    # Inception return
    color = (0, 128, 0) if stats['inception_return'] >= 0 else (255, 0, 0)
    pdf.set_text_color(*color)
    pdf.cell(0, 6, f"Since Inception Return: {stats['inception_return']:+.2f}%", 0, 1)
    
    pdf.set_text_color(0, 0, 0)  # Reset to black
    pdf.ln(5)
    
    # Investment Strategy Section
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Investment Strategy', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 5, 
        "Tovito Trader employs an active, short-term trading strategy focused on "
        "maximizing returns through strategic market positioning and risk management. "
        "The fund utilizes professional trading platforms and sophisticated analysis "
        "to identify opportunities in volatile market conditions."
    )
    pdf.ln(3)
    
    # Fee Structure Section
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Fee Structure', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 5,
        "Current Status: Evaluation Period\n"
        "Management Fees: No management fees during evaluation period (minimum 1 year)\n"
        "Trading Costs: All brokerage fees and commissions deducted directly from portfolio\n"
        "Tax Structure: Pass-through to fund manager (37% federal rate)\n"
        "Minimum Investment: Contact for details"
    )
    pdf.ln(3)
    
    # Risk Disclosure
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Risk Disclosure', 0, 1)
    pdf.set_font('Arial', 'I', 9)
    pdf.multi_cell(0, 5,
        "Investment in the fund involves risk, including possible loss of principal. "
        "Past performance does not guarantee future results. Short-term trading strategies "
        "involve higher turnover and may result in higher tax liability. Investors should "
        "carefully consider their investment objectives and risk tolerance before investing."
    )
    pdf.ln(3)
    
    # Contact Information
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Contact Information', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, 'Fund Manager: David Lang', 0, 1)
    pdf.cell(0, 6, 'Email: david.lang@tovitotrader.com', 0, 1)
    pdf.cell(0, 6, 'Website: www.tovitotrader.com', 0, 1)
    
    # Save PDF
    pdf.output(str(output_path))
    return True


def send_prospect_email(prospect_name, prospect_email, report_path, period, test_mode=False, admin_email=None):
    """Send report to prospect with PDF attached"""
    
    if not EMAIL_AVAILABLE:
        return False, "Email service not available"
    
    # Determine recipient
    if test_mode and admin_email:
        to_email = admin_email
        subject = f"[TEST] Tovito Trader Fund - {period} Performance Report (for {prospect_name})"
    else:
        to_email = prospect_email
        subject = f"Tovito Trader Fund - {period} Performance Report"
    
    message = f"""Dear {prospect_name},

Thank you for your interest in Tovito Trader Fund!

Please find attached our fund performance report for {period}. This report provides an overview of our investment strategy, recent performance, and fee structure.

Key Highlights:
• Active short-term trading strategy
• Professional portfolio management
• Transparent performance tracking
• Currently in evaluation period (no management fees)

If you would like to learn more about investment opportunities or have any questions, please don't hesitate to reach out.

We look forward to the possibility of working with you.

Best regards,
David Lang
Fund Manager
Tovito Trader

---
david.lang@tovitotrader.com
www.tovitotrader.com

This is an automated message. Please do not reply directly to this email.
"""
    
    try:
        result = send_email(
            to_email=to_email,
            subject=subject,
            message=message,
            attachments=[str(report_path)]
        )
        
        if result:
            return True, None
        else:
            return False, "Email send failed"
            
    except Exception as e:
        return False, str(e)


def log_communication(cursor, prospect_id, period, status, error_msg=None):
    """Log communication to database"""
    
    cursor.execute("""
        INSERT INTO prospect_communications 
        (prospect_id, date, communication_type, subject, report_period, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        prospect_id,
        datetime.now().date().isoformat(),
        'Prospect Report',
        f'Fund Performance Report - {period}',
        period,
        status,
        error_msg
    ))
    
    # Update last_contact_date on prospect
    cursor.execute("""
        UPDATE prospects
        SET last_contact_date = ?, updated_at = ?
        WHERE id = ?
    """, (datetime.now().date().isoformat(), datetime.now().isoformat(), prospect_id))


def send_admin_summary(prospects_sent, period, report_path, admin_email):
    """Send summary email to admin"""
    
    if not EMAIL_AVAILABLE:
        return
    
    prospect_list = "\n".join([f"  • {name} ({email})" for name, email in prospects_sent])
    
    subject = f"Prospect Report Sent - {period} ({len(prospects_sent)} prospects)"
    
    message = f"""Prospect Report Distribution Summary

Report Period: {period}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Sent: {len(prospects_sent)}

Recipients:
{prospect_list}

The fund performance report has been successfully distributed to all prospects listed above.

A copy of the report is attached for your records.

---
Tovito Trader Automated System
"""
    
    send_email(
        to_email=admin_email,
        subject=subject,
        message=message,
        attachments=[str(report_path)]
    )


def find_prospects_file(csv_file):
    """Find prospects CSV file in multiple locations"""
    
    # Try these locations in order:
    locations = [
        Path(csv_file),  # Exact path provided
        Path.cwd() / csv_file,  # Current directory
        Path(__file__).parent.parent / csv_file,  # Project root
        Path(__file__).parent.parent.parent / 'data' / csv_file,  # data folder
        Path(__file__).parent.parent / 'prospects' / csv_file,  # prospects folder
    ]
    
    for location in locations:
        if location.exists():
            return location
    
    return None


def main():
    parser = argparse.ArgumentParser(description='Send prospect reports')
    parser.add_argument('--month', type=int, required=True, help='Month (1-12)')
    parser.add_argument('--year', type=int, required=True, help='Year (e.g., 2026)')
    parser.add_argument('--prospects', required=True, help='CSV file with prospects')
    parser.add_argument('--test-email', action='store_true', help='Send all emails to admin for testing')
    
    args = parser.parse_args()
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    # Find prospects CSV file
    csv_path = find_prospects_file(args.prospects)
    
    if not csv_path:
        print(f"❌ Prospects file not found: {args.prospects}")
        print()
        print("Searched in:")
        print(f"  • {Path(args.prospects).absolute()}")
        print(f"  • {Path.cwd() / args.prospects}")
        print(f"  • {Path(__file__).parent.parent / args.prospects}")
        print(f"  • {Path(__file__).parent.parent.parent / 'data' / args.prospects}")
        print()
        print("💡 Tip: Place prospects.csv in C:\\tovito-trader\\ (project root)")
        return False
    
    print(f"Found prospects file: {csv_path}")
    print()
    prospects = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('Name') and row.get('Email'):
                    prospects.append({
                        'name': row['Name'].strip(),
                        'email': row['Email'].strip()
                    })
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return False
    
    if not prospects:
        print("❌ No valid prospects found in CSV")
        return False
    
    print("=" * 70)
    print("SEND PROSPECT REPORTS")
    print("=" * 70)
    print()
    print(f"Period: {datetime(args.year, args.month, 1).strftime('%B %Y')}")
    print(f"Prospects: {len(prospects)}")
    if args.test_email:
        print("Mode: TEST (all emails to admin)")
    else:
        print("Mode: LIVE (emails to prospects)")
    print()
    
    # List prospects
    for i, p in enumerate(prospects, 1):
        print(f"  {i}. {p['name']} <{p['email']}>")
    print()
    
    confirm = input("Send reports? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y']:
        print("Cancelled.")
        return False
    
    print()
    
    # Get database connection
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get fund statistics
        print("📊 Generating fund statistics...")
        stats = get_fund_stats(cursor, args.month, args.year)
        
        if not stats:
            print("❌ Could not generate fund statistics")
            return False
        
        print(f"   NAV: ${stats['nav_per_share']:.4f}")
        print(f"   Monthly Return: {stats['monthly_return']:+.2f}%")
        print(f"   YTD Return: {stats['ytd_return']:+.2f}%")
        print()
        
        # Generate PDF
        print("📄 Generating PDF report...")
        reports_dir = Path(__file__).parent.parent / 'reports'
        reports_dir.mkdir(exist_ok=True)
        
        period = datetime(args.year, args.month, 1).strftime('%Y_%m')
        report_path = reports_dir / f"Prospect_Report_{period}.pdf"
        
        generate_prospect_report(stats, report_path)
        print(f"   ✅ PDF created: {report_path.name}")
        print()
        
        # Get admin email
        import os
        from dotenv import load_dotenv
        load_dotenv()
        admin_email = os.getenv('ADMIN_EMAIL', 'dlang32@gmail.com')
        
        # Send emails
        print("📧 Sending emails...")
        print()
        
        sent_count = 0
        failed_count = 0
        prospects_sent = []
        
        period_str = datetime(args.year, args.month, 1).strftime('%B %Y')
        
        for prospect in prospects:
            # Get or create prospect in database
            cursor.execute("SELECT id FROM prospects WHERE email = ?", (prospect['email'],))
            existing = cursor.fetchone()
            
            if existing:
                prospect_id = existing[0]
            else:
                # Add prospect to database
                cursor.execute("""
                    INSERT INTO prospects (name, email, date_added, source)
                    VALUES (?, ?, ?, ?)
                """, (prospect['name'], prospect['email'], datetime.now().date().isoformat(), 'Prospect Report Distribution'))
                prospect_id = cursor.lastrowid
            
            # Send email
            success, error = send_prospect_email(
                prospect['name'],
                prospect['email'],
                report_path,
                period_str,
                test_mode=args.test_email,
                admin_email=admin_email
            )
            
            if success:
                sent_count += 1
                prospects_sent.append((prospect['name'], prospect['email']))
                status = 'Sent'
                error_msg = None
                print(f"   ✅ Sent to: {prospect['name']}")
            else:
                failed_count += 1
                status = 'Failed'
                error_msg = error
                print(f"   ❌ Failed: {prospect['name']} - {error}")
            
            # Log to database
            log_communication(cursor, prospect_id, period_str, status, error_msg)
        
        conn.commit()
        
        # Send admin summary
        if sent_count > 0 and not args.test_email:
            print()
            print("📧 Sending admin summary...")
            send_admin_summary(prospects_sent, period_str, report_path, admin_email)
            print("   ✅ Admin summary sent")
        
        print()
        print("=" * 70)
        print("COMPLETE")
        print("=" * 70)
        print(f"  Sent: {sent_count}")
        print(f"  Failed: {failed_count}")
        print(f"  Report: {report_path}")
        print()
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
