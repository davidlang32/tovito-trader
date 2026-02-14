@echo off
REM Tovito Trader - Automated Monthly Report Sender
REM Generates previous month's reports and emails to all investors

cd C:\tovito-trader
python scripts\03_reporting\generate_monthly_report.py --previous-month --email

REM Exit with the exit code from Python script
exit /b %errorlevel%
