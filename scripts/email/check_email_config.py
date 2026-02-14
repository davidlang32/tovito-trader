"""
Check Email Configuration for Daily NAV Enhanced

Quick diagnostic to see why emails aren't sending from daily_nav_enhanced.py
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("EMAIL CONFIGURATION CHECK")
print("=" * 70)
print()

# Check environment variables
print("1. Environment Variables:")
print("-" * 70)

email_vars = {
    'ENABLE_EMAIL': os.getenv('ENABLE_EMAIL'),
    'SMTP_SERVER': os.getenv('SMTP_SERVER'),
    'SMTP_PORT': os.getenv('SMTP_PORT'),
    'SMTP_USERNAME': os.getenv('SMTP_USERNAME'),
    'SMTP_PASSWORD': os.getenv('SMTP_PASSWORD', 'NOT_SET')[:4] + '****',
    'SMTP_FROM_EMAIL': os.getenv('SMTP_FROM_EMAIL'),
    'ADMIN_EMAIL': os.getenv('ADMIN_EMAIL'),
}

for key, value in email_vars.items():
    if value:
        print(f"   ✅ {key}: {value}")
    else:
        print(f"   ❌ {key}: NOT SET")

print()

# Check if email service can be imported
print("2. Email Service Import:")
print("-" * 70)

try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.automation.email_service import send_email
    print("   ✅ Email service imported successfully")
    EMAIL_AVAILABLE = True
except ImportError as e:
    print(f"   ❌ Cannot import email service: {e}")
    EMAIL_AVAILABLE = False

print()

# Test send if available
if EMAIL_AVAILABLE and os.getenv('ADMIN_EMAIL'):
    print("3. Sending Test Email:")
    print("-" * 70)
    
    try:
        result = send_email(
            to_email=os.getenv('ADMIN_EMAIL'),
            subject="Test from Email Config Check",
            message="This is a test from check_email_config.py to verify daily NAV emails work."
        )
        print("   ✅ Email sent successfully!")
        print(f"   Check {os.getenv('ADMIN_EMAIL')} for message")
    except Exception as e:
        print(f"   ❌ Email send failed: {e}")
        import traceback
        traceback.print_exc()

print()
print("=" * 70)
print("DIAGNOSIS COMPLETE")
print("=" * 70)
