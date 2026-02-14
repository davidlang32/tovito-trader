@echo off
REM ============================================================
REM TOVITO TRADER - Daily NAV Update Script
REM ============================================================

REM Change to project directory FIRST
cd /d C:\tovito-trader
if %errorlevel% neq 0 (
    echo ERROR: Could not change to C:\tovito-trader
    exit /b 1
)

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Log start time
echo ============================================================ >> logs\task_scheduler.log
echo Daily automation started at %date% %time% >> logs\task_scheduler.log
echo Working directory: %cd% >> logs\task_scheduler.log

REM Find Python - try multiple locations
set PYTHON_EXE=
if exist "C:\Users\dlang\AppData\Local\Programs\Python\Python313\python.exe" (
    set PYTHON_EXE=C:\Users\dlang\AppData\Local\Programs\Python\Python313\python.exe
) else if exist "C:\Users\dlang\AppData\Local\Programs\Python\Python312\python.exe" (
    set PYTHON_EXE=C:\Users\dlang\AppData\Local\Programs\Python\Python312\python.exe
) else if exist "C:\Users\dlang\AppData\Local\Programs\Python\Python311\python.exe" (
    set PYTHON_EXE=C:\Users\dlang\AppData\Local\Programs\Python\Python311\python.exe
) else if exist "C:\Python313\python.exe" (
    set PYTHON_EXE=C:\Python313\python.exe
) else if exist "C:\Python312\python.exe" (
    set PYTHON_EXE=C:\Python312\python.exe
) else if exist "C:\Python311\python.exe" (
    set PYTHON_EXE=C:\Python311\python.exe
) else (
    REM Fall back to PATH
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_EXE=python
    )
)

if "%PYTHON_EXE%"=="" (
    echo ERROR: Python not found >> logs\task_scheduler.log
    echo ERROR: Python not found
    exit /b 1
)

echo Using Python: %PYTHON_EXE% >> logs\task_scheduler.log
echo Using Python: %PYTHON_EXE%
%PYTHON_EXE% --version
%PYTHON_EXE% --version >> logs\task_scheduler.log 2>&1

REM Check if the script exists
if not exist "scripts\daily_nav_enhanced.py" (
    echo ERROR: scripts\daily_nav_enhanced.py not found >> logs\task_scheduler.log
    echo ERROR: scripts\daily_nav_enhanced.py not found
    exit /b 1
)

REM Run the daily NAV script
echo Running daily_nav_enhanced.py... >> logs\task_scheduler.log
echo Running daily_nav_enhanced.py...
echo.
%PYTHON_EXE% scripts\daily_nav_enhanced.py
set SCRIPT_ERROR=%errorlevel%

REM Log result
echo.
if %SCRIPT_ERROR% equ 0 (
    echo SUCCESS: Script completed successfully >> logs\task_scheduler.log
    echo SUCCESS: Script completed successfully
) else (
    echo ERROR: Script failed with error code %SCRIPT_ERROR% >> logs\task_scheduler.log
    echo ERROR: Script failed with error code %SCRIPT_ERROR%
)

REM Log completion
echo Daily automation completed at %date% %time% >> logs\task_scheduler.log
echo ============================================================ >> logs\task_scheduler.log

exit /b %SCRIPT_ERROR%
