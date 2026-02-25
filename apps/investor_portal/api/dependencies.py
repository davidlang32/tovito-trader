"""
Authentication Dependencies
============================

JWT token validation and user extraction.
Used by all protected endpoints.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

from .config import settings


# Security scheme
security = HTTPBearer()


class TokenData(BaseModel):
    """Data extracted from JWT token"""
    investor_id: str
    email: str
    exp: datetime


class CurrentUser(BaseModel):
    """Current authenticated user"""
    investor_id: str
    email: str
    name: str


def create_access_token(investor_id: str, email: str) -> str:
    """Create a new JWT access token"""
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": investor_id,
        "email": email,
        "exp": expire,
        "type": "access"
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(investor_id: str) -> str:
    """Create a new JWT refresh token"""
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": investor_id,
        "exp": expire,
        "type": "refresh"
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str, token_type: str = "access") -> TokenData:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Check token type
        if payload.get("type") != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        investor_id = payload.get("sub")
        email = payload.get("email", "")
        exp = datetime.fromtimestamp(payload.get("exp", 0))
        
        if investor_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        return TokenData(investor_id=investor_id, email=email, exp=exp)
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> CurrentUser:
    """
    Dependency to get current authenticated user.
    
    Usage:
        @app.get("/protected")
        async def protected_route(user: CurrentUser = Depends(get_current_user)):
            return {"investor_id": user.investor_id}
    """
    token = credentials.credentials
    token_data = verify_token(token, "access")
    
    # Get user details from database
    from .models.database import get_investor_by_id
    investor = get_investor_by_id(token_data.investor_id)
    
    if investor is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if investor.get("status") != "Active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active"
        )
    
    return CurrentUser(
        investor_id=token_data.investor_id,
        email=token_data.email,
        name=investor.get("name", "")
    )


async def verify_admin_key(
    x_admin_key: str = Header(..., alias="X-Admin-Key")
) -> bool:
    """
    Verify admin API key for server-to-server endpoints.

    Used by automation scripts (e.g., production sync) that run
    unattended via Task Scheduler. Uses a static API key from
    env var instead of JWT since there is no interactive login.

    Header: X-Admin-Key: <key>
    """
    if not settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API key not configured"
        )
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key"
        )
    return True
