"""
Authentication Service
=======================

Handles:
- Email verification flow (first-time login)
- Password hashing with bcrypt
- Token generation and validation
- Login attempt tracking and lockout
"""

import secrets
import sqlite3
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from pathlib import Path

import bcrypt

# Token settings
VERIFICATION_TOKEN_HOURS = 24
RESET_TOKEN_HOURS = 1
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def get_project_root() -> Path:
    """Get project root directory"""
    # Try multiple approaches to find project root
    # 1. Look for data/tovito.db relative to current working directory
    if (Path.cwd() / 'data' / 'tovito.db').exists():
        return Path.cwd()
    
    # 2. Go up from this file's location
    current = Path(__file__).parent
    for _ in range(10):
        if (current / 'data' / 'tovito.db').exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    
    # 3. Default to current working directory
    return Path.cwd()


def get_connection():
    """Get database connection"""
    db_path = get_project_root() / "data" / "tovito.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# PASSWORD VALIDATION
# ============================================================

def validate_password(password: str) -> Tuple[bool, str]:
    """
    Validate password against industry standard rules.
    
    Requirements:
    - 8-72 characters long
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one number (0-9)
    - At least one special character
    
    Returns:
        (is_valid, error_message)
    """
    errors = []
    
    if len(password) < 8:
        errors.append("Must be at least 8 characters")
    if len(password) > 72:
        errors.append("Must be 72 characters or less")
    if not re.search(r'[A-Z]', password):
        errors.append("Must contain at least one uppercase letter")
    if not re.search(r'[a-z]', password):
        errors.append("Must contain at least one lowercase letter")
    if not re.search(r'[0-9]', password):
        errors.append("Must contain at least one number")
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
        errors.append("Must contain at least one special character")
    
    if errors:
        return False, "; ".join(errors)
    
    return True, ""


# ============================================================
# PASSWORD HASHING (using bcrypt directly)
# ============================================================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


# ============================================================
# TOKEN GENERATION
# ============================================================

def generate_token() -> str:
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)


# ============================================================
# EMAIL VERIFICATION FLOW
# ============================================================

def initiate_verification(email: str) -> Tuple[bool, str, Optional[Dict]]:
    """
    Start the email verification process for first-time login.
    
    Returns:
        (success, message, data)
        - data includes verification_token if successful
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if investor exists
        cursor.execute("""
            SELECT i.investor_id, i.name, i.email, i.status,
                   a.email_verified, a.password_hash
            FROM investors i
            LEFT JOIN investor_auth a ON i.investor_id = a.investor_id
            WHERE i.email = ?
        """, (email,))
        
        row = cursor.fetchone()
        
        if row is None:
            return False, "Email not found in our records", None
        
        investor_id, name, inv_email, status, verified, password_hash = row
        
        if status != 'Active':
            return False, "Account is not active", None
        
        # If already verified and has password, they should use normal login
        if verified and password_hash:
            return False, "Account already set up. Please use login.", None
        
        # Generate verification token
        token = generate_token()
        expires = datetime.utcnow() + timedelta(hours=VERIFICATION_TOKEN_HOURS)
        
        # Ensure auth record exists and update with token
        cursor.execute("""
            INSERT INTO investor_auth (investor_id, verification_token, verification_token_expires)
            VALUES (?, ?, ?)
            ON CONFLICT(investor_id) DO UPDATE SET
                verification_token = excluded.verification_token,
                verification_token_expires = excluded.verification_token_expires,
                updated_at = CURRENT_TIMESTAMP
        """, (investor_id, token, expires.isoformat()))
        
        conn.commit()
        
        return True, "Verification email will be sent", {
            "investor_id": investor_id,
            "name": name,
            "email": inv_email,
            "token": token,
            "expires": expires.isoformat()
        }
        
    finally:
        conn.close()


def complete_verification(token: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
    """
    Complete email verification and set password.
    
    Returns:
        (success, message, data)
        - data includes investor info if successful
    """
    # Validate password
    is_valid, error_msg = validate_password(password)
    if not is_valid:
        return False, f"Password requirements not met: {error_msg}", None
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Find the token
        cursor.execute("""
            SELECT a.investor_id, a.verification_token_expires,
                   i.name, i.email
            FROM investor_auth a
            JOIN investors i ON a.investor_id = i.investor_id
            WHERE a.verification_token = ?
        """, (token,))
        
        row = cursor.fetchone()
        
        if row is None:
            return False, "Invalid or expired verification link", None
        
        investor_id, expires_str, name, email = row
        
        # Check expiration
        if expires_str:
            expires = datetime.fromisoformat(expires_str)
            if datetime.utcnow() > expires:
                return False, "Verification link has expired. Please request a new one.", None
        
        # Hash password and update
        password_hash = hash_password(password)
        
        cursor.execute("""
            UPDATE investor_auth
            SET password_hash = ?,
                email_verified = 1,
                verification_token = NULL,
                verification_token_expires = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE investor_id = ?
        """, (password_hash, investor_id))
        
        conn.commit()
        
        return True, "Account setup complete", {
            "investor_id": investor_id,
            "name": name,
            "email": email
        }
        
    finally:
        conn.close()


# ============================================================
# LOGIN
# ============================================================

def authenticate_user(email: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
    """
    Authenticate user with email and password.
    
    Returns:
        (success, message, data)
        - data includes investor info if successful
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get investor and auth info
        cursor.execute("""
            SELECT i.investor_id, i.name, i.email, i.status,
                   a.password_hash, a.email_verified,
                   a.failed_attempts, a.locked_until
            FROM investors i
            LEFT JOIN investor_auth a ON i.investor_id = a.investor_id
            WHERE i.email = ?
        """, (email,))
        
        row = cursor.fetchone()
        
        if row is None:
            return False, "Invalid email or password", None
        
        (investor_id, name, inv_email, status, 
         password_hash, verified, failed_attempts, locked_until) = row
        
        if status != 'Active':
            return False, "Account is not active", None
        
        # Check if account is locked
        if locked_until:
            lock_time = datetime.fromisoformat(locked_until)
            if datetime.utcnow() < lock_time:
                remaining = (lock_time - datetime.utcnow()).seconds // 60
                return False, f"Account locked. Try again in {remaining} minutes.", None
        
        # Check if account is set up
        if not verified or not password_hash:
            return False, "Account not set up. Please use 'First time login' to set your password.", None
        
        # Verify password
        if not verify_password(password, password_hash):
            # Increment failed attempts
            new_attempts = (failed_attempts or 0) + 1
            
            if new_attempts >= MAX_FAILED_ATTEMPTS:
                # Lock account
                lock_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
                cursor.execute("""
                    UPDATE investor_auth
                    SET failed_attempts = ?,
                        locked_until = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE investor_id = ?
                """, (new_attempts, lock_until.isoformat(), investor_id))
                conn.commit()
                return False, f"Too many failed attempts. Account locked for {LOCKOUT_MINUTES} minutes.", None
            else:
                cursor.execute("""
                    UPDATE investor_auth
                    SET failed_attempts = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE investor_id = ?
                """, (new_attempts, investor_id))
                conn.commit()
                remaining = MAX_FAILED_ATTEMPTS - new_attempts
                return False, f"Invalid email or password. {remaining} attempts remaining.", None
        
        # Success - reset failed attempts and update last login
        cursor.execute("""
            UPDATE investor_auth
            SET failed_attempts = 0,
                locked_until = NULL,
                last_login = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE investor_id = ?
        """, (investor_id,))
        conn.commit()
        
        return True, "Login successful", {
            "investor_id": investor_id,
            "name": name,
            "email": inv_email
        }
        
    finally:
        conn.close()


# ============================================================
# PASSWORD RESET
# ============================================================

def initiate_password_reset(email: str) -> Tuple[bool, str, Optional[Dict]]:
    """
    Start password reset flow.
    
    Returns:
        (success, message, data)
        - data includes reset token if successful
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if investor exists and is verified
        cursor.execute("""
            SELECT i.investor_id, i.name, i.email,
                   a.email_verified
            FROM investors i
            LEFT JOIN investor_auth a ON i.investor_id = a.investor_id
            WHERE i.email = ? AND i.status = 'Active'
        """, (email,))
        
        row = cursor.fetchone()
        
        if row is None:
            # Don't reveal if email exists
            return True, "If that email exists, a reset link will be sent.", None
        
        investor_id, name, inv_email, verified = row
        
        if not verified:
            return False, "Account not set up yet. Please use 'First time login'.", None
        
        # Generate reset token
        token = generate_token()
        expires = datetime.utcnow() + timedelta(hours=RESET_TOKEN_HOURS)
        
        cursor.execute("""
            UPDATE investor_auth
            SET reset_token = ?,
                reset_token_expires = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE investor_id = ?
        """, (token, expires.isoformat(), investor_id))
        
        conn.commit()
        
        return True, "Reset link will be sent", {
            "investor_id": investor_id,
            "name": name,
            "email": inv_email,
            "token": token,
            "expires": expires.isoformat()
        }
        
    finally:
        conn.close()


def complete_password_reset(token: str, new_password: str) -> Tuple[bool, str]:
    """
    Complete password reset with token.
    
    Returns:
        (success, message)
    """
    # Validate password
    is_valid, error_msg = validate_password(new_password)
    if not is_valid:
        return False, f"Password requirements not met: {error_msg}"
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Find the token
        cursor.execute("""
            SELECT investor_id, reset_token_expires
            FROM investor_auth
            WHERE reset_token = ?
        """, (token,))
        
        row = cursor.fetchone()
        
        if row is None:
            return False, "Invalid or expired reset link"
        
        investor_id, expires_str = row
        
        # Check expiration
        if expires_str:
            expires = datetime.fromisoformat(expires_str)
            if datetime.utcnow() > expires:
                return False, "Reset link has expired. Please request a new one."
        
        # Update password
        password_hash = hash_password(new_password)
        
        cursor.execute("""
            UPDATE investor_auth
            SET password_hash = ?,
                reset_token = NULL,
                reset_token_expires = NULL,
                failed_attempts = 0,
                locked_until = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE investor_id = ?
        """, (password_hash, investor_id))
        
        conn.commit()
        
        return True, "Password reset successful. You can now log in."
        
    finally:
        conn.close()


# ============================================================
# UTILITY
# ============================================================

def check_auth_status(investor_id: str) -> Dict:
    """Check authentication status for an investor"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT email_verified, password_hash IS NOT NULL as has_password,
                   last_login, failed_attempts, locked_until
            FROM investor_auth
            WHERE investor_id = ?
        """, (investor_id,))
        
        row = cursor.fetchone()
        
        if row is None:
            return {"status": "not_registered"}
        
        return {
            "status": "active" if row[0] and row[1] else "pending_setup",
            "email_verified": bool(row[0]),
            "has_password": bool(row[1]),
            "last_login": row[2],
            "failed_attempts": row[3] or 0,
            "is_locked": row[4] is not None and datetime.fromisoformat(row[4]) > datetime.utcnow()
        }
        
    finally:
        conn.close()
