@echo off
REM ============================================================
REM TOVITO TRADER - Dependency Check Script
REM Schedule: Weekly on Monday at 9:00 AM
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
echo ============================================================ >> logs\dependency_check.log
echo Dependency check started at %date% %time% >> logs\dependency_check.log
echo Working directory: %cd% >> logs\dependency_check.log

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
    REM Fall back to PATH
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_EXE=python
    )
)

if "%PYTHON_EXE%"=="" (
    echo ERROR: Python not found >> logs\dependency_check.log
    echo ERROR: Python not found
    exit /b 1
)

echo Using Python: %PYTHON_EXE% >> logs\dependency_check.log
echo Using Python: %PYTHON_EXE%
%PYTHON_EXE% --version
%PYTHON_EXE% --version >> logs\dependency_check.log 2>&1

REM Check if the script exists
if not exist "scripts\devops\dependency_monitor.py" (
    echo ERROR: scripts\devops\dependency_monitor.py not found >> logs\dependency_check.log
    echo ERROR: scripts\devops\dependency_monitor.py not found
    exit /b 1
)

REM Run the dependency monitor script (capture both stdout and stderr to log)
echo Running dependency_monitor.py... >> logs\dependency_check.log
echo Running dependency_monitor.py...
echo.
%PYTHON_EXE% scripts\devops\dependency_monitor.py 2>> logs\dependency_check.log
set SCRIPT_ERROR=%errorlevel%

REM Log result
echo.
if %SCRIPT_ERROR% equ 0 (
    echo SUCCESS: Script completed successfully >> logs\dependency_check.log
    echo SUCCESS: Script completed successfully
) else (
    echo ERROR: Script failed with error code %SCRIPT_ERROR% >> logs\dependency_check.log
    echo ERROR: Script failed with error code %SCRIPT_ERROR%
    echo Check logs\dependency_check.log for Python traceback >> logs\dependency_check.log
)

REM Log completion
echo Dependency check completed at %date% %time% >> logs\dependency_check.log
echo ============================================================ >> logs\dependency_check.log

exit /b %SCRIPT_ERROR%
