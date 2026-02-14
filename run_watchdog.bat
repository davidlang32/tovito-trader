@echo off
REM ============================================================
REM TOVITO TRADER - Watchdog Monitor
REM Schedule to run 1 hour AFTER daily NAV task
REM ============================================================

REM Change to project directory
cd /d C:\tovito-trader
if %errorlevel% neq 0 (
    echo ERROR: Could not change to C:\tovito-trader
    exit /b 1
)

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Log start
echo ============================================================ >> logs\watchdog_scheduler.log
echo Watchdog started at %date% %time% >> logs\watchdog_scheduler.log

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
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_EXE=python
    )
)

if "%PYTHON_EXE%"=="" (
    echo ERROR: Python not found >> logs\watchdog_scheduler.log
    echo ERROR: Python not found
    exit /b 1
)

echo Using Python: %PYTHON_EXE% >> logs\watchdog_scheduler.log
echo Using Python: %PYTHON_EXE%

REM Run watchdog monitor
echo Running watchdog_monitor.py...
%PYTHON_EXE% scripts\watchdog_monitor.py
set RESULT=%errorlevel%

REM Log result
if %RESULT% equ 0 (
    echo Watchdog: All checks passed >> logs\watchdog_scheduler.log
    echo Watchdog: All checks passed
) else (
    echo Watchdog: ISSUES DETECTED - check watchdog.log >> logs\watchdog_scheduler.log
    echo Watchdog: ISSUES DETECTED - check watchdog.log
)

echo Watchdog completed at %date% %time% >> logs\watchdog_scheduler.log
echo ============================================================ >> logs\watchdog_scheduler.log

exit /b %RESULT%
