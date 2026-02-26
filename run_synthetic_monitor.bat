@echo off
REM ============================================================
REM TOVITO TRADER - Synthetic Monitor
REM Validates production API and frontend from external perspective
REM Schedule: Every 4 hours on OPS-AUTOMATION
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
echo ============================================================ >> logs\synthetic_monitor_scheduler.log
echo Synthetic Monitor started at %date% %time% >> logs\synthetic_monitor_scheduler.log

REM Find Python - try multiple locations (newest first)
set PYTHON_EXE=
if exist "C:\Python314\python.exe" (
    set PYTHON_EXE=C:\Python314\python.exe
) else if exist "C:\Python313\python.exe" (
    set PYTHON_EXE=C:\Python313\python.exe
) else if exist "C:\Python312\python.exe" (
    set PYTHON_EXE=C:\Python312\python.exe
) else if exist "C:\Python311\python.exe" (
    set PYTHON_EXE=C:\Python311\python.exe
) else if exist "C:\Users\dlang\AppData\Local\Programs\Python\Python314\python.exe" (
    set PYTHON_EXE=C:\Users\dlang\AppData\Local\Programs\Python\Python314\python.exe
) else if exist "C:\Users\dlang\AppData\Local\Programs\Python\Python313\python.exe" (
    set PYTHON_EXE=C:\Users\dlang\AppData\Local\Programs\Python\Python313\python.exe
) else if exist "C:\Users\dlang\AppData\Local\Programs\Python\Python312\python.exe" (
    set PYTHON_EXE=C:\Users\dlang\AppData\Local\Programs\Python\Python312\python.exe
) else if exist "C:\Users\dlang\AppData\Local\Programs\Python\Python311\python.exe" (
    set PYTHON_EXE=C:\Users\dlang\AppData\Local\Programs\Python\Python311\python.exe
) else (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_EXE=python
    )
)

if "%PYTHON_EXE%"=="" (
    echo ERROR: Python not found >> logs\synthetic_monitor_scheduler.log
    echo ERROR: Python not found
    exit /b 1
)

echo Using Python: %PYTHON_EXE% >> logs\synthetic_monitor_scheduler.log
echo Using Python: %PYTHON_EXE%

REM Run synthetic monitor
echo Running synthetic_monitor.py... >> logs\synthetic_monitor_scheduler.log
echo Running synthetic_monitor.py...
%PYTHON_EXE% scripts\devops\synthetic_monitor.py 2>> logs\synthetic_monitor_scheduler.log
set RESULT=%errorlevel%

REM Log result
if %RESULT% equ 0 (
    echo Synthetic Monitor: All checks passed >> logs\synthetic_monitor_scheduler.log
    echo Synthetic Monitor: All checks passed
) else (
    echo Synthetic Monitor: One or more checks failed (code %RESULT%) >> logs\synthetic_monitor_scheduler.log
    echo Synthetic Monitor: One or more checks failed (code %RESULT%)
)

echo Synthetic Monitor completed at %date% %time% >> logs\synthetic_monitor_scheduler.log
echo ============================================================ >> logs\synthetic_monitor_scheduler.log

exit /b %RESULT%
