@echo off
REM Tovito Trader Dashboard Launcher
REM Double-click this file to start the dashboard

cd /d "%~dp0"

echo ========================================
echo   TOVITO TRADER DASHBOARD
echo ========================================
echo.
echo Starting dashboard...
echo.

REM Try to find Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH
    echo Please install Python and add to PATH
    pause
    exit /b 1
)

REM Launch the dashboard
python tovito_dashboard.py %*

REM If there was an error, pause to show it
if %errorlevel% neq 0 (
    echo.
    echo Dashboard closed with error code: %errorlevel%
    pause
)
