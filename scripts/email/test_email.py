"""
Email System Test Script

Tests email configuration and sends a test email to verify SMTP settings.

Usage:
    python scripts/test_email.py
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("❌ ERROR: python-dotenv not installed")
    print("   Install with: pip install python-dotenv")
    sys.exit(1)

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def test_email_configuration():
    """Test email system configuration"""
    
    print("=" * 70)
    print("EMAIL SYSTEM TEST")
    print("=" * 70)
    print()
    
    # Load configuration from .env
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT')
    smtp_username = os.getenv('SMTP_USERNAME')
    smtp_password = os.getenv('SMTP_PASSWORD')
    smtp_from_email = os.getenv('SMTP_FROM_EMAIL')
    smtp_from_name = os.getenv('SMTP_FROM_NAME', 'Tovito Trader')
    admin_email = os.getenv('ADMIN_EMAIL')
    
    # Validate configuration
    print("📧 Checking configuration...")
    print()
    
    missing_vars = []
    if not smtp_server:
        missing_vars.append('SMTP_SERVER')
    if not smtp_port:
        missing_vars.append('SMTP_PORT')
    if not smtp_username:
        missing_vars.append('SMTP_USERNAME')
    if not smtp_password:
        missing_vars.append('SMTP_PASSWORD')
    if not smtp_from_email:
        missing_vars.append('SMTP_FROM_EMAIL')
    if not admin_email:
        missing_vars.append('ADMIN_EMAIL')
    
    if missing_vars:
        print("❌ ERROR: Missing configuration in .env file:")
        for var in missing_vars:
            print(f"   - {var}")
        print()
        print("Please add these variables to your .env file.")
        print("See EMAIL_CONFIGURATION_GUIDE.md for instructions.")
        sys.exit(1)
    
    # Show configuration (mask password)
    print("✅ Configuration loaded:")
    print(f"   SMTP Server: {smtp_server}")
    print(f"   SMTP Port: {smtp_port}")
    print(f"   Username: {smtp_username}")
    print(f"   Password: {'*' * len(smtp_password)}")
    print(f"   From Email: {smtp_from_email}")
    print(f"   From Name: {smtp_from_name}")
    print(f"   Test Email To: {admin_email}")
    print()
    
    # Test SMTP connection
    print("🔌 Testing SMTP connection...")
    try:
        smtp_port_int = int(smtp_port)
        server = smtplib.SMTP(smtp_server, smtp_port_int, timeout=10)
        server.starttls()
        server.login(smtp_username, smtp_password)
        print("   ✅ Connection successful!")
        print("   ✅ Authentication successful!")
        server.quit()
    except smtplib.SMTPAuthenticationError as e:
        print("   ❌ Authentication failed!")
        print(f"   Error: {e}")
        print()
        print("💡 Common causes:")
        print("   1. Using regular password instead of App Password")
        print("   2. App Password has spaces (remove them)")
        print("   3. 2-Step Verification not enabled on Gmail")
        print()
        print("See EMAIL_CONFIGURATION_GUIDE.md for setup instructions.")
        sys.exit(1)
    except Exception as e:
        print("   ❌ Connection failed!")
        print(f"   Error: {e}")
        print()
        print("💡 Check:")
        print("   1. SMTP server and port are correct")
        print("   2. Internet connection is working")
        print("   3. Firewall not blocking port 587")
        sys.exit(1)
    
    print()
    
    # Send test email
    print("📨 Sending test email...")
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"✅ Tovito Trader - Email System Test"
        msg['From'] = f"{smtp_from_name} <{smtp_from_email}>"
        msg['To'] = admin_email
        
        # Email body
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        text_body = f"""
EMAIL SYSTEM TEST - SUCCESS!

This is a test email from your Tovito Trader system.

If you're reading this, your email configuration is working correctly!

Test Details:
════════════════════════════════════════
Timestamp:      {timestamp}
From:           {smtp_from_email}
SMTP Server:    {smtp_server}
SMTP Port:      {smtp_port}

Next Steps:
────────────────────────────────────────
1. ✅ Email system configured successfully
2. ✅ Test contribution confirmation email
3. ✅ Test withdrawal confirmation email
4. ✅ Add investor emails to database
5. ✅ Go live!

Questions or Issues?
────────────────────────────────────────
Review the EMAIL_CONFIGURATION_GUIDE.md for troubleshooting.

Best regards,
Tovito Trader System
"""
        
        # Attach text body
        text_part = MIMEText(text_body, 'plain')
        msg.attach(text_part)
        
        # Send email
        server = smtplib.SMTP(smtp_server, smtp_port_int)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
        server.quit()
        
        print("   ✅ Email sent successfully!")
        print()
        
    except Exception as e:
        print("   ❌ Failed to send email!")
        print(f"   Error: {e}")
        sys.exit(1)
    
    # Success
    print("=" * 70)
    print("✅ EMAIL TEST COMPLETE!")
    print("=" * 70)
    print()
    print(f"📬 Check your inbox: {admin_email}")
    print(f"   Subject: ✅ Tovito Trader - Email System Test")
    print()
    print("If you don't see it:")
    print("   1. Check spam/junk folder")
    print("   2. Wait 1-2 minutes (may be delayed)")
    print("   3. Mark as 'Not Spam' if needed")
    print("   4. Add sender to contacts")
    print()
    print("Next Steps:")
    print("   • Test contribution email: python scripts\\process_contribution.py")
    print("   • Test withdrawal email: python scripts\\process_withdrawal.py")
    print("   • Add investor emails: python scripts\\update_investor_emails.py")
    print()
    print("🎉 Your email system is ready!")
    print()


if __name__ == "__main__":
    try:
        test_email_configuration()
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)