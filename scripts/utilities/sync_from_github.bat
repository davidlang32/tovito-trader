@echo off
REM ============================================================
REM Tovito Trader - Auto-sync from GitHub
REM ============================================================
REM
REM Purpose:  Pulls latest code from GitHub main branch
REM Schedule: Every 30 minutes via Task Scheduler
REM
REM This script keeps the management laptop's codebase in sync
REM with the primary development laptop. It handles:
REM   - Git pull from origin/main
REM   - Auto-install Python deps if requirements.txt changed
REM   - Auto-install npm deps if package.json changed
REM
REM NOTE: This only syncs CODE. For non-code items (database,
REM .env, logs, reports), see sync_non_code_items.bat
REM ============================================================

setlocal EnableDelayedExpansion

set PROJECT=C:\tovito-trader
set LOGFILE=%PROJECT%\logs\github_sync.log

REM Ensure logs directory exists
if not exist "%PROJECT%\logs" mkdir "%PROJECT%\logs"

REM --------------------------------------------------------
REM Find Python (same resolution as other .bat launchers)
REM --------------------------------------------------------
set PYTHON=
for %%P in (
    "C:\Python314\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) do (
    if exist %%P (
        set PYTHON=%%~P
        goto :found_python
    )
)
REM Fall back to PATH
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set PYTHON=python
) else (
    echo [%date% %time%] [ERROR] Python not found >> "%LOGFILE%"
    exit /b 1
)
:found_python

REM --------------------------------------------------------
REM Check if git is available
REM --------------------------------------------------------
where git >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] [ERROR] Git not found in PATH >> "%LOGFILE%"
    exit /b 1
)

REM --------------------------------------------------------
REM Navigate to project directory
REM --------------------------------------------------------
cd /d "%PROJECT%"
if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] [ERROR] Cannot access %PROJECT% >> "%LOGFILE%"
    exit /b 1
)

REM --------------------------------------------------------
REM Check for uncommitted local changes
REM --------------------------------------------------------
git status --porcelain 2>nul > "%TEMP%\tovito_git_status.txt"
for %%A in ("%TEMP%\tovito_git_status.txt") do (
    if %%~zA GTR 0 (
        echo [%date% %time%] [WARN] Local changes detected - stashing >> "%LOGFILE%"
        git stash >> "%LOGFILE%" 2>&1
    )
)

REM --------------------------------------------------------
REM Fetch and check if there are updates
REM --------------------------------------------------------
git fetch origin main >> "%LOGFILE%" 2>&1

REM Compare local HEAD with remote
for /f "tokens=*" %%A in ('git rev-parse HEAD 2^>nul') do set LOCAL_HEAD=%%A
for /f "tokens=*" %%A in ('git rev-parse origin/main 2^>nul') do set REMOTE_HEAD=%%A

if "%LOCAL_HEAD%"=="%REMOTE_HEAD%" (
    REM No changes - skip pull to reduce log noise
    REM Only log once per hour to avoid filling the log
    exit /b 0
)

REM --------------------------------------------------------
REM Pull latest changes
REM --------------------------------------------------------
echo ================================================== >> "%LOGFILE%"
echo [%date% %time%] Updates available - pulling from origin/main >> "%LOGFILE%"

REM Remember current HEAD for diffing
for /f "tokens=*" %%A in ('git rev-parse HEAD 2^>nul') do set BEFORE_HEAD=%%A

git pull origin main >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] [ERROR] Git pull failed with exit code %ERRORLEVEL% >> "%LOGFILE%"
    echo [%date% %time%] Attempting reset to origin/main >> "%LOGFILE%"
    git reset --hard origin/main >> "%LOGFILE%" 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [%date% %time%] [ERROR] Reset also failed - manual intervention needed >> "%LOGFILE%"
        exit /b 1
    )
)

echo [%date% %time%] [OK] Pull successful >> "%LOGFILE%"

REM --------------------------------------------------------
REM Show what changed (for the log)
REM --------------------------------------------------------
echo [%date% %time%] Changed files: >> "%LOGFILE%"
git diff --name-only %BEFORE_HEAD%..HEAD >> "%LOGFILE%" 2>&1

REM --------------------------------------------------------
REM Auto-install Python dependencies if requirements changed
REM --------------------------------------------------------
git diff --name-only %BEFORE_HEAD%..HEAD 2>nul | findstr /i "requirements.txt requirements-full.txt" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [%date% %time%] [INFO] Python requirements changed - reinstalling >> "%LOGFILE%"
    "%PYTHON%" -m pip install -r requirements-full.txt >> "%LOGFILE%" 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo [%date% %time%] [OK] pip install completed >> "%LOGFILE%"
    ) else (
        echo [%date% %time%] [WARN] pip install had issues (exit code %ERRORLEVEL%) >> "%LOGFILE%"
    )
)

REM --------------------------------------------------------
REM Auto-install npm dependencies if package.json changed
REM --------------------------------------------------------
git diff --name-only %BEFORE_HEAD%..HEAD 2>nul | findstr /i "package.json package-lock.json" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [%date% %time%] [INFO] npm packages changed - reinstalling >> "%LOGFILE%"
    cd /d "%PROJECT%\apps\investor_portal\frontend\investor_portal"
    call npm install >> "%LOGFILE%" 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo [%date% %time%] [OK] npm install completed >> "%LOGFILE%"
    ) else (
        echo [%date% %time%] [WARN] npm install had issues (exit code %ERRORLEVEL%) >> "%LOGFILE%"
    )
    cd /d "%PROJECT%"
)

REM --------------------------------------------------------
REM Run database migrations if migration scripts changed
REM --------------------------------------------------------
git diff --name-only %BEFORE_HEAD%..HEAD 2>nul | findstr /i "scripts/setup/migrate_" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [%date% %time%] [INFO] Migration scripts changed - check if new migrations need to run >> "%LOGFILE%"
    echo [%date% %time%] [INFO] Review changed migration files and run manually if needed >> "%LOGFILE%"
    git diff --name-only %BEFORE_HEAD%..HEAD 2>nul | findstr /i "scripts/setup/migrate_" >> "%LOGFILE%" 2>&1
)

echo [%date% %time%] Sync complete >> "%LOGFILE%"
exit /b 0
