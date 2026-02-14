#!/usr/bin/env python3
"""
Manually Verify Investor
=========================

Sets up an investor account without email verification.
Useful for testing and initial setup.

Usage:
    python verify_investor.py --email dlang32@gmail.com --password "MySecure#Pass1"
    python verify_investor.py --list   # Show all investors and their auth status
    
Password Requirements:
    - 8-72 characters
    - At least one uppercase letter
    - At least one lowercase letter  
    - At least one number
    - At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
"""

import argparse
import sqlite3
import re
from pathlib import Path
import bcrypt

# Database path - find relative to script or current directory
SCRIPT_DIR = Path(__file__).parent
if (SCRIPT_DIR / 'data' / 'tovito.db').exists():
    DB_PATH = SCRIPT_DIR / 'data' / 'tovito.db'
elif (Path.cwd() / 'data' / 'tovito.db').exists():
    DB_PATH = Path.cwd() / 'data' / 'tovito.db'
else:
    DB_PATH = Path('data') / 'tovito.db'


# ============================================================
# PASSWORD VALIDATION
# ============================================================

PASSWORD_RULES = """
Password Requirements:
  - 8-72 characters long
  - At least one uppercase letter (A-Z)
  - At least one lowercase letter (a-z)
  - At least one number (0-9)
  - At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
"""

def validate_password(password: str) -> tuple:
    """
    Validate password against industry standard rules.
    
    Returns:
        (is_valid, error_message)
    """
    errors = []
    
    # Length check (bcrypt max is 72 bytes)
    if len(password) < 8:
        errors.append("Must be at least 8 characters")
    if len(password) > 72:
        errors.append("Must be 72 characters or less")
    
    # Uppercase check
    if not re.search(r'[A-Z]', password):
        errors.append("Must contain at least one uppercase letter (A-Z)")
    
    # Lowercase check
    if not re.search(r'[a-z]', password):
        errors.append("Must contain at least one lowercase letter (a-z)")
    
    # Number check
    if not re.search(r'[0-9]', password):
        errors.append("Must contain at least one number (0-9)")
    
    # Special character check
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
        errors.append("Must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)")
    
    if errors:
        return False, "\n  - ".join([""] + errors)
    
    return True, ""


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    # Encode to bytes, hash, decode back to string for storage
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)  # 12 rounds is a good balance of security/speed
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password_hash(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# ============================================================
# DATABASE FUNCTIONS
# ============================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def list_investors():
    """List all investors and their auth status"""
    print("\n" + "="*80)
    print(" INVESTOR AUTH STATUS")
    print("="*80 + "\n")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if auth table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='investor_auth'
    """)
    if not cursor.fetchone():
        print("  ⚠️  Auth table not found. Run migrate_add_auth_table.py first.")
        conn.close()
        return
    
    cursor.execute("""
        SELECT i.investor_id, i.name, i.email, i.status,
               a.email_verified, a.password_hash IS NOT NULL as has_password, a.last_login
        FROM investors i
        LEFT JOIN investor_auth a ON i.investor_id = a.investor_id
        ORDER BY i.name
    """)
    
    print(f"  {'Name':<20} {'Email':<30} {'Verified':<10} {'Has PW':<10} {'Last Login':<20}")
    print("  " + "-"*90)
    
    for row in cursor.fetchall():
        verified = "✅" if row["email_verified"] else "❌"
        has_pw = "✅" if row["has_password"] else "❌"
        last_login = row["last_login"] or "Never"
        email = row['email'] or 'N/A'
        print(f"  {row['name']:<20} {email:<30} {verified:<10} {has_pw:<10} {last_login:<20}")
    
    conn.close()


def setup_investor(email: str, password: str):
    """Manually verify an investor and set their password"""
    print(f"\n🔧 Setting up account for: {email}")
    
    # Validate password
    is_valid, error_msg = validate_password(password)
    if not is_valid:
        print(f"\n❌ Password does not meet requirements:{error_msg}")
        print(PASSWORD_RULES)
        return False
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if auth table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='investor_auth'
        """)
        if not cursor.fetchone():
            print("❌ Auth table not found. Run migrate_add_auth_table.py first.")
            return False
        
        # Find investor
        cursor.execute("""
            SELECT investor_id, name
            FROM investors
            WHERE email = ?
        """, (email,))
        
        investor = cursor.fetchone()
        
        if investor is None:
            print(f"❌ No investor found with email: {email}")
            return False
        
        investor_id = investor["investor_id"]
        name = investor["name"]
        
        # Hash password using bcrypt directly
        password_hash = hash_password(password)
        
        # Ensure auth record exists
        cursor.execute("""
            INSERT INTO investor_auth (investor_id, password_hash, email_verified)
            VALUES (?, ?, 1)
            ON CONFLICT(investor_id) DO UPDATE SET
                password_hash = excluded.password_hash,
                email_verified = 1,
                verification_token = NULL,
                verification_token_expires = NULL,
                failed_attempts = 0,
                locked_until = NULL,
                updated_at = CURRENT_TIMESTAMP
        """, (investor_id, password_hash))
        
        conn.commit()
        
        print(f"\n✅ Account set up successfully!")
        print(f"   Name: {name}")
        print(f"   Investor ID: {investor_id}")
        print(f"   Email: {email}")
        print(f"\n   Login at: http://localhost:8000/docs")
        print(f"   Use POST /auth/login with email and password")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Manually verify investor account',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=PASSWORD_RULES
    )
    parser.add_argument('--email', help='Investor email')
    parser.add_argument('--password', help='Password to set')
    parser.add_argument('--list', action='store_true', help='List all investors')
    args = parser.parse_args()
    
    if args.list:
        list_investors()
    elif args.email and args.password:
        setup_investor(args.email, args.password)
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python verify_investor.py --list")
        print('  python verify_investor.py --email dlang32@gmail.com --password "MySecure#Pass1"')


if __name__ == '__main__':
    main()
