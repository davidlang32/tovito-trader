"""
Fund API Configuration
=======================

Loads settings from environment variables.

Environment selection:
- TOVITO_ENV env var selects the environment (default: development)
- Looks for config/.env.{TOVITO_ENV} first (e.g., config/.env.development)
- Falls back to root .env if env-specific file not found
- On Railway: TOVITO_ENV=production, no config folder, uses env vars directly
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings


def _load_env_file():
    """Load the correct .env file based on TOVITO_ENV.

    Priority:
    1. config/.env.{TOVITO_ENV} (e.g., config/.env.development)
    2. Root .env (fallback — production secrets on local machine)
    3. OS environment variables (Railway sets these directly)
    """
    env_name = os.getenv("TOVITO_ENV", "development")

    # API is at apps/investor_portal/api/, project root is 3 levels up
    project_root = Path(__file__).parent.parent.parent.parent
    env_specific = project_root / "config" / f".env.{env_name}"
    env_root = project_root / ".env"

    if env_specific.exists():
        load_dotenv(env_specific, override=True)
    elif env_root.exists():
        load_dotenv(env_root, override=True)
    # else: rely on OS-level env vars (Railway, CI, etc.)


# Load environment-specific .env BEFORE Settings class reads os.getenv()
_load_env_file()


def _build_cors_origins() -> List[str]:
    """Build CORS origins list from env var + hardcoded defaults.

    CORS_ORIGINS env var is a comma-separated string (not JSON).
    Always includes localhost dev origins and production domains.
    """
    env_origins = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "").split(",")
        if o.strip()
    ]
    default_origins = [
        "http://localhost:3000",       # React dev server
        "http://localhost:3001",       # React dev server (fallback port)
        "http://localhost:5173",       # Vite dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",
        "https://tovitotrader.com",    # Production portal
        "https://www.tovitotrader.com",
    ]
    # Deduplicate while preserving order
    seen = set()
    result = []
    for origin in env_origins + default_origins:
        if origin not in seen:
            seen.add(origin)
            result.append(origin)
    return result


class Settings(BaseSettings):
    """API Settings from environment"""

    # Environment
    ENV: str = os.getenv("TOVITO_ENV", "development")

    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/dev_tovito.db")

    # JWT Settings
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "CHANGE-THIS-IN-PRODUCTION-use-openssl-rand-hex-32")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    LOGIN_ATTEMPT_LIMIT: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # Business Rules
    TAX_RATE: float = float(os.getenv("TAX_RATE", "0.37"))

    # Portal URL (for email links — verification, password reset)
    PORTAL_BASE_URL: str = os.getenv("PORTAL_BASE_URL", "http://localhost:3000")

    # Email notifications (for withdrawal requests)
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "")

    # Admin API key (for server-to-server sync from automation laptop)
    ADMIN_API_KEY: str = os.getenv("ADMIN_API_KEY", "")

    class Config:
        env_file = ".env"
        extra = "ignore"


# Singleton settings instance
settings = Settings()

# CORS origins — built separately to avoid pydantic-settings trying to
# JSON-parse the comma-separated CORS_ORIGINS env var as a List[str]
CORS_ORIGINS = _build_cors_origins()


def get_database_path() -> Path:
    """Get absolute path to database"""
    db_path = Path(settings.DATABASE_PATH)
    if db_path.is_absolute():
        return db_path
    
    # Relative to project root
    # API is in apps/investor_portal/api/, so go up 3 levels
    project_root = Path(__file__).parent.parent.parent.parent
    return project_root / db_path
