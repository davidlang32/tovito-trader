"""
Email Adapter - Bridges to actual email service location
"""
import sys
from pathlib import Path

# Add src/automation to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src' / 'automation'))

try:
    from email_service import send_email as _send_email
    
    def send_email_with_attachment(to_email, subject, body, attachment_path, attachment_name):
        """Wrapper for email service"""
        return _send_email(
            to_email=to_email,
            subject=subject,
            message=body,
            html=False,
            attachments=[attachment_path]
        )
    
except ImportError as e:
    print(f"⚠️  Could not import email service: {e}")
    
    def send_email_with_attachment(to_email, subject, body, attachment_path, attachment_name):
        """Fallback when email service unavailable"""
        print(f"❌ Email service not available")
        return False