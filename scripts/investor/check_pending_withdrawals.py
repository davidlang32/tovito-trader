"""
Check for Pending Withdrawal Requests

Part of daily automation - checks for pending withdrawal requests
and sends email alert to admin if any exist.

Usage:
    python scripts/check_pending_withdrawals.py
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)

import sqlite3
import sys
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Email service
try:
    from src.automation.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False


def get_database_path():
    """Get database path"""
    return Path(__file__).parent.parent.parent / 'data' / 'tovito.db'


def check_pending_withdrawals():
    """Check for pending withdrawal requests"""
    
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get pending requests
        cursor.execute("""
            SELECT 
                wr.id,
                wr.request_date,
                i.name,
                wr.requested_amount,
                wr.request_method
            FROM withdrawal_requests wr
            JOIN investors i ON wr.investor_id = i.investor_id
            WHERE wr.status = 'Pending'
            ORDER BY wr.request_date
        """)
        
        pending = cursor.fetchall()
        
        if not pending:
            print("No pending withdrawal requests.")
            return True
        
        print(f"⚠️  {len(pending)} pending withdrawal request(s):")
        print()
        
        total_amount = 0
        request_list = []
        
        for req_id, date, name, amount, method in pending:
            print(f"  • Request #{req_id}: {name} - ${amount:,.2f} ({date}, via {method})")
            total_amount += amount
            request_list.append(f"  • #{req_id}: {name} - ${amount:,.2f} ({date}, {method})")
        
        print()
        print(f"Total requested: ${total_amount:,.2f}")
        print()
        
        # Send email alert to admin
        if EMAIL_AVAILABLE and len(pending) > 0:
            admin_email = os.getenv('ADMIN_EMAIL', 'dlang32@gmail.com')
            
            subject = f"⚠️  {len(pending)} Pending Withdrawal Request(s) - Action Required"
            
            request_details = "\n".join(request_list)
            
            message = f"""You have {len(pending)} pending withdrawal request(s) requiring approval.

PENDING REQUESTS:
{request_details}

Total Requested: ${total_amount:,.2f}

ACTION REQUIRED:
Review and process these withdrawal requests:

    python scripts\\process_withdrawal_enhanced.py

Or view details:

    python scripts\\view_pending_withdrawals.py

---
Tovito Trader Daily Automation
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            print("📧 Sending email alert...")
            if send_email(admin_email, subject, message):
                print("   ✅ Alert email sent to admin")
            else:
                print("   ⚠️  Failed to send alert email")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = check_pending_withdrawals()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
