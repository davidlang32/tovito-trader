@echo off
REM ============================================================
REM Tovito Trader - Weekly Validation
REM Sets UTF-8 encoding to handle emoji characters
REM ============================================================

REM Set UTF-8 code page
chcp 65001 >nul 2>&1

REM Set Python to use UTF-8
set PYTHONIOENCODING=utf-8

REM Change to project directory
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
    echo ERROR: Python not found >> logs\weekly_validation.log
    exit /b 1
)

REM Create/append to log file
echo ============================================================ >> logs\weekly_validation.log
echo WEEKLY VALIDATION - %date% %time% >> logs\weekly_validation.log
echo Using Python: %PYTHON_EXE% >> logs\weekly_validation.log
echo ============================================================ >> logs\weekly_validation.log

REM Run validation script
%PYTHON_EXE% scripts\validation\validate_reconciliation.py --verbose >> logs\weekly_validation.log 2>&1

REM Add blank line for readability
echo. >> logs\weekly_validation.log

REM Reset code page
chcp 437 >nul 2>&1
