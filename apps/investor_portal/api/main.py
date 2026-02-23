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
import time

from .config import settings, CORS_ORIGINS
from .routes import auth, investor, nav, fund_flow, profile, referral, reports, analysis


# Lifespan for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"[START] Fund API starting...")
    print(f"   Environment: {settings.ENV}")
    print(f"   Database: {settings.DATABASE_PATH}")
    yield
    # Shutdown
    print("[STOP] Fund API shutting down...")


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
