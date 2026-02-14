"""
Fund API Configuration
=======================

Loads settings from environment variables.
"""

import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """API Settings from environment"""
    
    # Environment
    ENV: str = os.getenv("TOVITO_ENV", "development")
    
    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/tovito.db")
    
    # JWT Settings
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "CHANGE-THIS-IN-PRODUCTION-use-openssl-rand-hex-32")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS (allowed origins for portal)
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",      # React dev server
        "http://localhost:5173",      # Vite dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "https://portal.tovitotrader.com",  # Production portal
    ]
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    LOGIN_ATTEMPT_LIMIT: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    
    # Business Rules
    TAX_RATE: float = float(os.getenv("TAX_RATE", "0.37"))
    
    # Email notifications (for withdrawal requests)
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "")
    
    class Config:
        env_file = ".env"
        extra = "ignore"


# Singleton settings instance
settings = Settings()


def get_database_path() -> Path:
    """Get absolute path to database"""
    db_path = Path(settings.DATABASE_PATH)
    if db_path.is_absolute():
        return db_path
    
    # Relative to project root
    # API is in apps/investor_portal/api/, so go up 3 levels
    project_root = Path(__file__).parent.parent.parent.parent
    return project_root / db_path
