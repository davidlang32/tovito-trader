@echo off
REM ============================================================
REM Tovito Trader - Investor Portal Startup
REM ============================================================
REM
REM This starts the React development server.
REM Make sure the API is running first:
REM   python -m uvicorn apps.investor_portal.api.main:app --port 8000
REM
REM ============================================================

cd /d %~dp0

echo.
echo ============================================================
echo  Tovito Trader - Investor Portal
echo ============================================================
echo.
echo  Portal URL: http://localhost:3000
echo  API URL:    http://localhost:8000
echo.
echo  Make sure the API is running first!
echo ============================================================
echo.

REM Check if node_modules exists
if not exist "node_modules" (
    echo Installing dependencies...
    npm install
    echo.
)

echo Starting development server...
npm run dev
