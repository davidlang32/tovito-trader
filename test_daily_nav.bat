@echo off
REM ============================================================
REM TOVITO TRADER - Test Daily NAV Update
REM Run this manually to see what's happening
REM ============================================================

echo ============================================================
echo TOVITO TRADER - Daily NAV Test
echo ============================================================
echo.

REM Change to project directory
cd /d C:\tovito-trader
echo Working directory: %cd%
echo.

REM Check Python
echo Checking Python...
python --version
if %errorlevel% neq 0 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)
echo.

REM Check if script exists
echo Checking for daily NAV scripts...
if exist "scripts\daily_nav_enhanced.py" (
    echo FOUND: scripts\daily_nav_enhanced.py [PREFERRED]
    set NAV_SCRIPT=scripts\daily_nav_enhanced.py
) else if exist "scripts\daily_runner.py" (
    echo FOUND: scripts\daily_runner.py [FALLBACK]
    set NAV_SCRIPT=scripts\daily_runner.py
) else (
    echo ERROR: No daily NAV script found!
    echo.
    echo Listing scripts folder:
    dir scripts\*.py
    pause
    exit /b 1
)
echo.

REM Check .env file
echo Checking .env file...
if exist ".env" (
    echo FOUND: .env file
) else (
    echo WARNING: .env file not found
)
echo.

REM Run the script with visible output
echo ============================================================
echo Running %NAV_SCRIPT%...
echo ============================================================
echo.

python %NAV_SCRIPT%

echo.
echo ============================================================
echo Script completed with error level: %errorlevel%
echo ============================================================
echo.

REM Show latest log entries
echo Latest log entries:
echo.
if exist "logs\daily_runner.log" (
    type logs\daily_runner.log | more
) else (
    echo No daily_runner.log found
)

echo.
pause
