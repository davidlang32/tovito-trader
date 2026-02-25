@echo off
REM ============================================================
REM Tovito Trader - Weekly Maintenance Restart
REM ============================================================
REM
REM Purpose:  Gracefully restart the management laptop weekly
REM Schedule: Sunday at 3:00 AM via Task Scheduler
REM
REM This script:
REM   1. Logs the restart event
REM   2. Stops any running Python processes cleanly
REM   3. Restarts Windows (applies pending updates)
REM
REM After reboot, Task Scheduler tasks resume on their next
REM scheduled time automatically. No manual intervention needed.
REM
REM Windows Update Tip: Set active hours (9 AM - 6 PM) in
REM   Settings > Windows Update > Advanced options
REM   so Windows won't auto-restart during market hours.
REM   This Sunday 3 AM restart picks up any pending updates.
REM ============================================================

setlocal

set PROJECT=C:\tovito-trader
set LOGFILE=%PROJECT%\logs\maintenance.log

REM Ensure logs directory exists
if not exist "%PROJECT%\logs" mkdir "%PROJECT%\logs"

echo ================================================== >> "%LOGFILE%"
echo [%date% %time%] Weekly maintenance restart initiated >> "%LOGFILE%"

REM --------------------------------------------------------
REM Stop running Python processes gracefully
REM --------------------------------------------------------
echo [%date% %time%] Stopping Python processes... >> "%LOGFILE%"

REM First try graceful termination
tasklist /FI "IMAGENAME eq python.exe" 2>nul | findstr /i "python" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [%date% %time%] Found running Python processes - terminating >> "%LOGFILE%"
    taskkill /F /IM python.exe /T >nul 2>&1
    echo [%date% %time%] Python processes terminated >> "%LOGFILE%"
) else (
    echo [%date% %time%] No Python processes running >> "%LOGFILE%"
)

REM Also stop any Node processes (frontend dev server)
tasklist /FI "IMAGENAME eq node.exe" 2>nul | findstr /i "node" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [%date% %time%] Stopping Node.js processes >> "%LOGFILE%"
    taskkill /F /IM node.exe /T >nul 2>&1
)

REM --------------------------------------------------------
REM Wait for processes to clean up
REM --------------------------------------------------------
echo [%date% %time%] Waiting 10 seconds for cleanup... >> "%LOGFILE%"
timeout /t 10 /nobreak >nul

REM --------------------------------------------------------
REM Create a database backup before restart (safety measure)
REM --------------------------------------------------------
set PYTHON=
for %%P in (
    "C:\Python314\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
) do (
    if exist %%P (
        set PYTHON=%%~P
        goto :found_py
    )
)
set PYTHON=python
:found_py

if exist "%PROJECT%\data\tovito.db" (
    echo [%date% %time%] Creating pre-restart database backup... >> "%LOGFILE%"
    if exist "%PROJECT%\scripts\utilities\backup_database.py" (
        "%PYTHON%" "%PROJECT%\scripts\utilities\backup_database.py" >> "%LOGFILE%" 2>&1
        echo [%date% %time%] Backup complete >> "%LOGFILE%"
    ) else (
        REM Simple copy fallback if backup script not found
        copy "%PROJECT%\data\tovito.db" "%PROJECT%\data\backups\tovito_pre_restart_%date:~-4%%date:~4,2%%date:~7,2%.db" >nul 2>&1
        echo [%date% %time%] Simple backup copy done >> "%LOGFILE%"
    )
)

REM --------------------------------------------------------
REM Restart the computer
REM --------------------------------------------------------
echo [%date% %time%] Restarting now (30 second warning)... >> "%LOGFILE%"

REM /r = restart, /t 30 = 30 second delay, /c = comment shown to user
shutdown /r /t 30 /c "Tovito Trader: Weekly maintenance restart. System will restart in 30 seconds."

echo [%date% %time%] Restart command issued >> "%LOGFILE%"
exit /b 0
