@echo off
REM ============================================================
REM Tovito Trader - Automated Monthly Report Sender
REM Generates previous month's reports and emails to all investors
REM ============================================================

cd /d C:\tovito-trader

REM Find Python
set PYTHON_EXE=
if exist "C:\Python314\python.exe" (
    set PYTHON_EXE=C:\Python314\python.exe
) else if exist "C:\Python313\python.exe" (
    set PYTHON_EXE=C:\Python313\python.exe
) else (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_EXE=python
    )
)

if "%PYTHON_EXE%"=="" (
    echo ERROR: Python not found
    exit /b 1
)

%PYTHON_EXE% scripts\reporting\generate_monthly_report.py --previous-month --email

REM Exit with the exit code from Python script
exit /b %errorlevel%
