"""
Tovito Trader - Fund API
=========================

REST API for the Investor Portal.
Provides secure, authenticated access to fund data.

Run locally (from project root C:\\tovito-trader):
    python -m uvicorn apps.investor_portal.api.main:app --reload --port 8000

API Docs:
    http://localhost:8000/docs
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os
import time

from .config import settings, CORS_ORIGINS, get_database_path
from .routes import auth, investor, nav, fund_flow, profile, referral, reports, analysis, public, admin


def _print_startup_banner():
    """Print clear environment banner on API startup.

    Makes it immediately obvious which environment and database the API
    is using.  Warns loudly if production database detected outside of
    production mode.
    """
    env = settings.ENV.upper()
    db_path = get_database_path()
    db_exists = db_path.exists()

    # Banner
    print("")
    print("=" * 60)
    if env == "PRODUCTION":
        print(f"   TOVITO TRADER API  --  PRODUCTION")
    else:
        print(f"   TOVITO TRADER API  --  {env} MODE")
    print("=" * 60)
    print(f"   Database:    {settings.DATABASE_PATH}")
    print(f"   DB exists:   {db_exists}")
    print(f"   Portal URL:  {settings.PORTAL_BASE_URL}")
    print(f"   Email:       {'enabled' if settings.ADMIN_EMAIL else 'disabled'}")
    print("=" * 60)

    # Safety warnings
    if env != "PRODUCTION" and "dev_" not in settings.DATABASE_PATH:
        print("")
        print("   [WARN] *** NON-DEV DATABASE IN NON-PRODUCTION MODE ***")
        print(f"   [WARN] DATABASE_PATH={settings.DATABASE_PATH}")
        print("   [WARN] Expected 'dev_' prefix for non-production.")
        print("   [WARN] Set TOVITO_ENV=production or use dev_tovito.db")
        print("")

    if not db_exists:
        print("")
        print(f"   [WARN] Database file not found: {db_path}")
        print("   [WARN] Run: python scripts/setup/setup_test_database.py --env dev")
        print("")

    print("")


# Lifespan for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    _print_startup_banner()
    _ensure_db_views()
    _refresh_benchmark_cache()
    _validate_encryption()
    _run_data_migrations()
    yield
    # Shutdown
    print("[STOP] Fund API shutting down...")


def _ensure_db_views():
    """Drop and recreate SQL views on every startup.

    Views are defined in schema_v2.py but only created during full
    database initialization.  The API needs them at runtime (e.g.
    v_monthly_performance for /analysis/monthly-performance).

    We drop-then-create (not just CREATE IF NOT EXISTS) so that
    schema changes to views are picked up on deploy without needing
    a manual migration.  Views contain no data, so this is safe.
    """
    try:
        from src.database.schema_v2 import VIEWS
        from .models.database import get_connection

        conn = get_connection()
        cursor = conn.cursor()
        try:
            for view_name, view_sql in VIEWS.items():
                cursor.execute(f"DROP VIEW IF EXISTS {view_name}")
                cursor.execute(view_sql)
            conn.commit()
            print(f"   [OK] Database views verified ({len(VIEWS)} views)")
        finally:
            conn.close()
    except Exception as e:
        # Non-fatal — log and continue
        try:
            print(f"   [WARN] Could not verify database views: {e}")
        except UnicodeEncodeError:
            print(f"   [WARN] Could not verify database views: {ascii(str(e))}")


def _refresh_benchmark_cache():
    """Refresh benchmark price cache on startup (non-fatal).

    The daily NAV pipeline runs on Windows and populates the cache,
    but Railway may have stale data.  This ensures the cache is
    reasonably fresh whenever the API starts or redeploys.
    """
    try:
        from pathlib import Path
        from src.market_data.benchmarks import refresh_benchmark_cache
        from .config import get_database_path

        db_path = Path(get_database_path())
        stats = refresh_benchmark_cache(db_path, lookback_days=400)
        total = sum(stats.values())
        print(f"   [OK] Benchmark cache refreshed ({total} new prices)")
    except ImportError:
        print("   [WARN] yfinance not available - benchmark cache not refreshed")
    except Exception as e:
        # Non-fatal — log and continue
        try:
            print(f"   [WARN] Benchmark cache refresh failed: {e}")
        except UnicodeEncodeError:
            print(f"   [WARN] Benchmark cache refresh failed: {ascii(str(e))}")


def _validate_encryption():
    """Validate encryption key on startup (non-fatal).

    Tests that ENCRYPTION_KEY is set and can perform a round-trip
    encrypt/decrypt.  Essential for early detection of misconfigured
    keys -- without this, a wrong key silently starts the API and
    only fails when a profile endpoint is first accessed.
    """
    try:
        encryption_key = os.getenv('ENCRYPTION_KEY', '')
        if not encryption_key:
            print("   [WARN] Encryption: ENCRYPTION_KEY not set -- profile features disabled")
            return

        from src.utils.encryption import FieldEncryptor
        enc = FieldEncryptor(encryption_key)
        test_val = "encryption-startup-test"
        result = enc.decrypt(enc.encrypt(test_val))
        if result == test_val:
            legacy_count = enc.legacy_key_count
            if legacy_count > 0:
                print(f"   [OK] Encryption: verified (current key + {legacy_count} legacy key(s))")
            else:
                print("   [OK] Encryption: verified")
        else:
            print("   [WARN] Encryption: round-trip verification failed")
    except Exception as e:
        try:
            print(f"   [WARN] Encryption validation failed: {e}")
        except UnicodeEncodeError:
            print(f"   [WARN] Encryption validation failed: {ascii(str(e))}")


def _run_data_migrations():
    """Run one-time data migrations on startup (non-fatal).

    These are idempotent operations that fix data issues discovered
    in production.  Safe to run repeatedly — they check before acting.
    """
    try:
        from .models.database import get_connection

        conn = get_connection()
        cursor = conn.cursor()
        try:
            migrations_applied = 0

            # Phase 10: Soft-delete test transactions (IDs 1, 2)
            # These are +100/-100 test entries from Jan 14 that net to zero
            cursor.execute("""
                UPDATE transactions
                SET is_deleted = 1
                WHERE transaction_id IN (1, 2)
                  AND ABS(amount) = 100
                  AND (is_deleted IS NULL OR is_deleted = 0)
            """)
            if cursor.rowcount > 0:
                conn.commit()
                print(f"   [OK] Data migration: soft-deleted {cursor.rowcount} test transactions")
                migrations_applied += 1

            # Phase 15: Add prospect email verification columns
            cursor.execute("PRAGMA table_info(prospects)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            prospect_cols = [
                ("email_verified", "INTEGER DEFAULT 0"),
                ("verification_token", "TEXT"),
                ("verification_token_expires", "TIMESTAMP"),
            ]
            for col_name, col_def in prospect_cols:
                if col_name not in existing_cols:
                    cursor.execute(
                        f"ALTER TABLE prospects ADD COLUMN {col_name} {col_def}"
                    )
                    migrations_applied += 1
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_prospects_verification_token
                ON prospects(verification_token)
            """)
            if migrations_applied > 0:
                conn.commit()

            # Phase 13: Create plan_daily_performance table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS plan_daily_performance (
                    date TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    market_value REAL NOT NULL,
                    cost_basis REAL NOT NULL,
                    unrealized_pl REAL NOT NULL,
                    allocation_pct REAL NOT NULL,
                    position_count INTEGER NOT NULL,
                    PRIMARY KEY (date, plan_id)
                )
            """)
            # Check if table was just created (no rows = new table)
            cursor.execute("SELECT COUNT(*) FROM plan_daily_performance")
            # Table exists now either way — commit any pending changes
            conn.commit()

            # Phase 19: Create pii_access_log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pii_access_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    investor_id TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    access_type TEXT NOT NULL CHECK (access_type IN ('read', 'write')),
                    performed_by TEXT NOT NULL DEFAULT 'system',
                    ip_address TEXT,
                    context TEXT
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pii_access_investor
                ON pii_access_log(investor_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pii_access_timestamp
                ON pii_access_log(timestamp)
            """)
            conn.commit()

            if migrations_applied == 0:
                print("   [OK] Data migrations: nothing to do")
        finally:
            conn.close()
    except Exception as e:
        try:
            print(f"   [WARN] Data migration failed: {e}")
        except UnicodeEncodeError:
            print(f"   [WARN] Data migration failed: {ascii(str(e))}")


# Create FastAPI app
app = FastAPI(
    title="Tovito Trader Fund API",
    description="Secure API for the Investor Portal",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENV != "production" else None,  # Disable docs in prod
    redoc_url="/redoc" if settings.ENV != "production" else None,
)


# CORS middleware (configure for your portal domain)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Add security headers to all API responses.

    These headers protect against common web vulnerabilities:
    - X-Content-Type-Options: prevents MIME-type sniffing
    - X-Frame-Options: prevents clickjacking
    - X-XSS-Protection: enables browser XSS filtering
    - Referrer-Policy: limits referrer information leakage
    - Permissions-Policy: restricts browser feature access
    - Cache-Control: prevents caching of API responses
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    return response


# Request timing middleware
@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time * 1000, 2)) + "ms"
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the error (in production, send to monitoring)
    # Use ascii repr to avoid Windows cp1252 encoding crashes
    try:
        print(f"[ERROR] Unhandled error: {exc}")
    except UnicodeEncodeError:
        print(f"[ERROR] Unhandled error: {ascii(str(exc))}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(investor.router, prefix="/investor", tags=["Investor"])
app.include_router(nav.router, prefix="/nav", tags=["NAV"])
app.include_router(fund_flow.router, prefix="/fund-flow", tags=["Fund Flow"])
app.include_router(profile.router, prefix="/profile", tags=["Profile"])
app.include_router(referral.router, prefix="/referral", tags=["Referral"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])
app.include_router(analysis.router, prefix="/analysis", tags=["Analysis"])
app.include_router(public.router, prefix="/public", tags=["Public"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.ENV
    }


# Root endpoint
@app.get("/", tags=["System"])
async def root():
    """API root - returns basic info"""
    return {
        "name": "Tovito Trader Fund API",
        "version": "1.0.0",
        "docs": "/docs" if settings.ENV != "production" else "disabled"
    }
