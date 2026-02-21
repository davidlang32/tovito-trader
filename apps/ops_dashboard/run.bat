@echo off
REM ============================================================
REM TOVITO TRADER - Operations Health Dashboard
REM Launches the Streamlit ops dashboard on port 8502
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
echo ============================================================ >> logs\ops_dashboard.log
echo Ops Dashboard started at %date% %time% >> logs\ops_dashboard.log

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
    echo ERROR: Python not found >> logs\ops_dashboard.log
    echo ERROR: Python not found
    exit /b 1
)

echo Using Python: %PYTHON_EXE% >> logs\ops_dashboard.log
echo Using Python: %PYTHON_EXE%

REM Launch Streamlit on port 8502
echo Starting Operations Dashboard on http://localhost:8502 ...
%PYTHON_EXE% -m streamlit run apps\ops_dashboard\app.py --server.port 8502
set RESULT=%errorlevel%

echo Ops Dashboard stopped at %date% %time% >> logs\ops_dashboard.log
echo ============================================================ >> logs\ops_dashboard.log

exit /b %RESULT%
