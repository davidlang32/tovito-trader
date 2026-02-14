"""
Authentication Routes (Updated with Email Verification)
=========================================================

POST /auth/initiate       - Start first-time setup (sends verification email)
POST /auth/verify         - Complete setup with token and password
POST /auth/login          - Login with email/password
POST /auth/refresh        - Refresh access token
POST /auth/forgot-password - Request password reset
POST /auth/reset-password  - Reset password with token
GET  /auth/me             - Get current user info
"""

import os
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

# Add project root for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ..dependencies import (
    create_access_token, 
    create_refresh_token, 
    verify_token,
    get_current_user,
    CurrentUser
)
from ..services.auth_service import (
    initiate_verification,
    complete_verification,
    authenticate_user,
    initiate_password_reset,
    complete_password_reset
)
from ..models.database import get_investor_by_id


router = APIRouter()


# ============================================================
# Request/Response Models
# ============================================================

class InitiateRequest(BaseModel):
    """First-time setup request"""
    email: EmailStr


class InitiateResponse(BaseModel):
    """First-time setup response"""
    message: str
    email_sent: bool


class VerifyRequest(BaseModel):
    """Complete verification request"""
    token: str
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")


class LoginRequest(BaseModel):
    """Login request body"""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Login response with tokens"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    investor_name: str


class RefreshRequest(BaseModel):
    """Token refresh request"""
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request"""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password request"""
    token: str
    new_password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    """Current user info"""
    investor_id: str
    name: str
    email: str
    status: str
    join_date: str


class MessageResponse(BaseModel):
    """Simple message response"""
    message: str


# ============================================================
# Email Sending (Background Task)
# ============================================================

def send_verification_email(email: str, name: str, token: str):
    """Send verification email (runs in background)"""
    try:
        # Import the email service from the project
        from scripts.email.email_service import send_email
        
        # Build verification URL (would be your portal URL in production)
        # For local dev, just log the token
        verify_url = f"http://localhost:3000/verify?token={token}"
        
        subject = "Tovito Trader - Set Up Your Account"
        body = f"""
Hello {name},

Welcome to the Tovito Trader Investor Portal!

Click the link below to set up your password:
{verify_url}

This link expires in 24 hours.

If you didn't request this, please ignore this email.

Best regards,
Tovito Trader
"""
        
        send_email(
            to_email=email,
            subject=subject,
            body=body
        )
        print(f"✅ Verification email sent to {email}")
        
    except Exception as e:
        # Log error but don't fail the request
        print(f"⚠️ Failed to send verification email: {e}")
        print(f"   Token for {email}: {token}")


def send_reset_email(email: str, name: str, token: str):
    """Send password reset email (runs in background)"""
    try:
        from scripts.email.email_service import send_email
        
        reset_url = f"http://localhost:3000/reset-password?token={token}"
        
        subject = "Tovito Trader - Password Reset"
        body = f"""
Hello {name},

You requested a password reset for your Tovito Trader account.

Click the link below to reset your password:
{reset_url}

This link expires in 1 hour.

If you didn't request this, please ignore this email.

Best regards,
Tovito Trader
"""
        
        send_email(
            to_email=email,
            subject=subject,
            body=body
        )
        print(f"✅ Password reset email sent to {email}")
        
    except Exception as e:
        print(f"⚠️ Failed to send reset email: {e}")
        print(f"   Token for {email}: {token}")


# ============================================================
# Routes
# ============================================================

@router.post("/initiate", response_model=InitiateResponse)
async def initiate_setup(request: InitiateRequest, background_tasks: BackgroundTasks):
    """
    Start first-time account setup.
    
    For investors who haven't set up their password yet.
    Sends a verification email with a link to set password.
    """
    success, message, data = initiate_verification(request.email)
    
    if not success:
        # Check if they should use normal login
        if "already set up" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account already set up. Please use the login form."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # Send email in background
    if data:
        background_tasks.add_task(
            send_verification_email,
            data["email"],
            data["name"],
            data["token"]
        )
    
    return InitiateResponse(
        message="Check your email for a verification link.",
        email_sent=True
    )


@router.post("/verify", response_model=TokenResponse)
async def verify_and_set_password(request: VerifyRequest):
    """
    Complete email verification and set password.
    
    Called when user clicks the verification link and submits their new password.
    Returns JWT tokens on success (user is logged in).
    """
    success, message, data = complete_verification(request.token, request.password)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # Create tokens (auto-login after verification)
    access_token = create_access_token(
        investor_id=data["investor_id"],
        email=data["email"]
    )
    refresh_token = create_refresh_token(investor_id=data["investor_id"])
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=30 * 60,
        investor_name=data["name"]
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Login with email and password.
    
    Returns JWT access token and refresh token.
    """
    success, message, data = authenticate_user(request.email, request.password)
    
    if not success:
        # Check for specific error types
        if "not set up" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        if "locked" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=message
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create tokens
    access_token = create_access_token(
        investor_id=data["investor_id"],
        email=data["email"]
    )
    refresh_token = create_refresh_token(investor_id=data["investor_id"])
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=30 * 60,
        investor_name=data["name"]
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest):
    """
    Get a new access token using refresh token.
    
    Use this when access token expires to avoid re-login.
    """
    # Verify refresh token
    token_data = verify_token(request.refresh_token, "refresh")
    
    # Get investor to verify still active
    investor = get_investor_by_id(token_data.investor_id)
    
    if investor is None or investor.get("status") != "Active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account not found or inactive"
        )
    
    # Create new tokens
    access_token = create_access_token(
        investor_id=investor["investor_id"],
        email=investor.get("email", "")
    )
    new_refresh_token = create_refresh_token(investor_id=investor["investor_id"])
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=30 * 60,
        investor_name=investor["name"]
    )


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(request: ForgotPasswordRequest, background_tasks: BackgroundTasks):
    """
    Request a password reset link.
    
    Always returns success to prevent email enumeration.
    """
    success, message, data = initiate_password_reset(request.email)
    
    # Send email in background if we have data
    if data and data.get("token"):
        background_tasks.add_task(
            send_reset_email,
            data["email"],
            data["name"],
            data["token"]
        )
    
    # Always return success message (don't reveal if email exists)
    return MessageResponse(
        message="If that email is registered, you'll receive a password reset link."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(request: ResetPasswordRequest):
    """
    Reset password using the token from email.
    """
    success, message = complete_password_reset(request.token, request.new_password)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return MessageResponse(message=message)


@router.post("/logout", response_model=MessageResponse)
async def logout(user: CurrentUser = Depends(get_current_user)):
    """
    Logout - invalidate tokens.
    
    Note: With stateless JWT, tokens remain valid until expiration.
    Client should discard tokens.
    """
    return MessageResponse(message="Logged out successfully. Please discard your tokens.")


@router.get("/me", response_model=UserResponse)
async def get_me(user: CurrentUser = Depends(get_current_user)):
    """
    Get current user information.
    
    Requires valid access token.
    """
    investor = get_investor_by_id(user.investor_id)
    
    if investor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        investor_id=investor["investor_id"],
        name=investor["name"],
        email=investor.get("email", ""),
        status=investor.get("status", "Unknown"),
        join_date=str(investor.get("join_date", ""))
    )
