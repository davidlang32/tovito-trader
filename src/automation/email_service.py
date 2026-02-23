"""
Email Service
Handles all email communications: reports, newsletters, alerts

Provides both:
- EmailService class for advanced use
- send_email() function for simple use

Every send attempt is recorded in the email_logs table for audit trail.
"""

import smtplib
import os
import sys
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
from typing import List, Optional
from dotenv import load_dotenv

# Add project root to path (for when running this file directly)
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

load_dotenv()


class EmailService:
    """Email delivery service (advanced interface).

    Every send attempt is logged to the email_logs table for audit trail.
    """

    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_user = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.email_from = os.getenv('SMTP_FROM_EMAIL', self.smtp_user)
        self.from_name = os.getenv('SMTP_FROM_NAME', 'Tovito Trader')

        if not self.smtp_user or not self.smtp_password:
            print("WARNING: Email credentials not configured - emails will not be sent")

    def _log_email(self, recipient: str, subject: str, email_type: str,
                   status: str, error_message: str = None):
        """Record email send attempt in email_logs table.

        Never raises -- logging failures are printed but don't break
        the calling workflow.
        """
        try:
            from src.database.models import Database, EmailLog
            db = Database()
            session = db.get_session()
            try:
                log = EmailLog(
                    recipient=recipient,
                    subject=subject[:200],  # Respect column length
                    email_type=email_type,
                    status=status,
                    error_message=str(error_message)[:500] if error_message else None,
                )
                session.add(log)
                session.commit()
            finally:
                session.close()
        except Exception as e:
            print(f"  [WARN] Could not log email to database: {e}")

    def send_email(self, to_email: str, subject: str, message: str,
                   html: bool = False, attachments: Optional[List[str]] = None,
                   email_type: str = 'General') -> bool:
        """
        Send an email and log the attempt.

        Args:
            to_email: Recipient email address
            subject: Email subject
            message: Email body (plain text or HTML)
            html: True if message is HTML
            attachments: List of file paths to attach
            email_type: Category for email_logs (e.g. MonthlyReport, Alert)

        Returns:
            bool: True if sent successfully
        """
        if not self.smtp_user or not self.smtp_password:
            self._log_email(to_email, subject, email_type, 'Failed',
                            'SMTP credentials not configured')
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.email_from}>"
            msg['To'] = to_email
            msg['Subject'] = subject

            # Add body
            if html:
                msg.attach(MIMEText(message, 'html'))
            else:
                msg.attach(MIMEText(message, 'plain'))

            # Add attachments if any
            if attachments:
                for filepath in attachments:
                    if os.path.exists(filepath):
                        with open(filepath, 'rb') as f:
                            attachment = MIMEApplication(f.read())
                            attachment.add_header(
                                'Content-Disposition',
                                'attachment',
                                filename=os.path.basename(filepath)
                            )
                            msg.attach(attachment)

            # Send email
            # Port 465 uses SSL directly; port 587 uses STARTTLS
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                    server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)

            # Log success
            self._log_email(to_email, subject, email_type, 'Sent')
            return True

        except Exception as e:
            print(f"      Email error: {e}")
            self._log_email(to_email, subject, email_type, 'Failed', str(e))
            return False
    
    def send_alert_email(self, recipient: str, subject: str, message: str) -> bool:
        """Send alert/notification email"""

        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #dc3545;">Tovito Trader Alert</h2>
                <p><strong>{subject}</strong></p>
                <p>{message}</p>
                <hr>
                <p style="font-size: 12px; color: #666;">
                    Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
                    This is an automated alert from Tovito Trader system.
                </p>
            </body>
        </html>
        """

        return self.send_email(recipient, f"Alert: {subject}", html_body,
                               html=True, email_type='Alert')


# ===== SIMPLE INTERFACE FOR EASY USE =====

def send_email(to_email: str, subject: str, message: str,
               html: bool = False, attachments: Optional[List[str]] = None,
               email_type: str = 'General') -> bool:
    """
    Simple email sending function (uses EmailService internally).

    Args:
        to_email: Recipient email address
        subject: Email subject
        message: Email body (plain text or HTML)
        html: True if message is HTML
        attachments: List of file paths to attach
        email_type: Category for email_logs (MonthlyReport, Alert, etc.)

    Returns:
        bool: True if sent successfully

    Example:
        send_email('investor@example.com', 'Monthly Report', 'Your report is ready',
                   email_type='MonthlyReport')
    """
    service = EmailService()
    return service.send_email(to_email, subject, message, html, attachments,
                              email_type=email_type)


def send_alert(to_email: str, subject: str, message: str) -> bool:
    """
    Send alert email (uses EmailService internally)
    
    Args:
        to_email: Recipient email address
        subject: Alert subject
        message: Alert message
        
    Returns:
        bool: True if sent successfully
    """
    service = EmailService()
    return service.send_alert_email(to_email, subject, message)


# Test function
if __name__ == "__main__":
    """Test email service"""
    
    test_recipient = os.getenv('ADMIN_EMAIL', 'dlang32@gmail.com')
    
    print(f"Testing email service...")
    print(f"Sending test email to: {test_recipient}")
    print()
    
    # Test simple interface
    success = send_email(
        to_email=test_recipient,
        subject="✅ Tovito Trader - Email Service Test",
        message="This is a test email from the updated email service.\n\nBoth class and function interfaces are working!",
        html=False
    )
    
    if success:
        print("✅ Email sent successfully!")
    else:
        print("⚠️  Email not sent (check configuration)")
