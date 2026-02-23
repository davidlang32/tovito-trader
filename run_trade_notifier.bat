@echo off
REM ============================================================
REM TOVITO TRADER - Discord Trade Notifier
REM Polls brokerages every 5 minutes and posts trades to Discord
REM Run manually or via Task Scheduler at market open
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
echo ============================================================ >> logs\trade_notifier_scheduler.log
echo Trade Notifier started at %date% %time% >> logs\trade_notifier_scheduler.log

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
    echo ERROR: Python not found >> logs\trade_notifier_scheduler.log
    echo ERROR: Python not found
    exit /b 1
)

echo Using Python: %PYTHON_EXE% >> logs\trade_notifier_scheduler.log
echo Using Python: %PYTHON_EXE%

REM Run trade notifier (persistent process — runs until stopped)
echo Running discord_trade_notifier.py... >> logs\trade_notifier_scheduler.log
echo Running discord_trade_notifier.py...
%PYTHON_EXE% scripts\trading\discord_trade_notifier.py 2>> logs\trade_notifier_scheduler.log
set RESULT=%errorlevel%

REM Log result
if %RESULT% equ 0 (
    echo Trade Notifier: Exited normally >> logs\trade_notifier_scheduler.log
    echo Trade Notifier: Exited normally
) else (
    echo Trade Notifier: Exited with error code %RESULT% >> logs\trade_notifier_scheduler.log
    echo Trade Notifier: Exited with error code %RESULT%
)

echo Trade Notifier stopped at %date% %time% >> logs\trade_notifier_scheduler.log
echo ============================================================ >> logs\trade_notifier_scheduler.log

exit /b %RESULT%
