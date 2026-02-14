@echo off
REM Weekly Validation Batch File
REM Sets UTF-8 encoding to handle emoji characters

REM Set UTF-8 code page
chcp 65001 >nul 2>&1

REM Set Python to use UTF-8
set PYTHONIOENCODING=utf-8

REM Change to project directory
cd C:\tovito-trader

REM Create/append to log file
echo ============================================================ >> logs\weekly_validation.log
echo WEEKLY VALIDATION - %date% %time% >> logs\weekly_validation.log
echo ============================================================ >> logs\weekly_validation.log

REM Run validation script
python scripts\validate_reconciliation.py --verbose >> logs\weekly_validation.log 2>&1

REM Add blank line for readability
echo. >> logs\weekly_validation.log

REM Reset code page
chcp 437 >nul 2>&1
