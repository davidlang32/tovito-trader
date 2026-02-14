@echo off
REM ============================================================
REM TOVITO TRADER - SCRIPT ORGANIZATION BATCH FILE
REM Organizes all scripts into logical folders
REM ============================================================

echo ============================================================
echo TOVITO TRADER - SCRIPT ORGANIZATION
echo ============================================================
echo.
echo This will organize your scripts into folders:
echo   02_investor
echo   03_reporting
echo   04_trading
echo   05_validation
echo   06_tax
echo   07_email
echo   08_setup
echo   09_prospects
echo   10_utilities
echo   99_archive
echo.
echo Files will stay in root: daily_runner.py, nav_helper.py, email_adapter.py
echo.

pause

echo.
echo ============================================================
echo CREATING FOLDERS...
echo ============================================================

mkdir 02_investor 2>nul
mkdir 03_reporting 2>nul
mkdir 04_trading 2>nul
mkdir 05_validation 2>nul
mkdir 06_tax 2>nul
mkdir 07_email 2>nul
mkdir 08_setup 2>nul
mkdir 09_prospects 2>nul
mkdir 10_utilities 2>nul
mkdir 99_archive 2>nul

echo Done!
echo.

echo ============================================================
echo MOVING FILES TO 02_INVESTOR...
echo ============================================================

move assign_pending_contribution.py 02_investor\ 2>nul
move check_pending_withdrawals.py 02_investor\ 2>nul
move request_withdrawal.py 02_investor\ 2>nul
move submit_withdrawal_request.py 02_investor\ 2>nul
move view_pending_withdrawals.py 02_investor\ 2>nul
move process_withdrawal_enhanced.py 02_investor\ 2>nul

echo Done!
echo.

echo ============================================================
echo MOVING FILES TO 04_TRADING...
echo ============================================================

move sync_tradier_transactions.py 04_trading\ 2>nul

echo Done!
echo.

echo ============================================================
echo MOVING FILES TO 05_VALIDATION...
echo ============================================================

move validate_reconciliation.py 05_validation\ 2>nul
move system_health_check.py 05_validation\ 2>nul

echo Done!
echo.

echo ============================================================
echo MOVING FILES TO 06_TAX...
echo ============================================================

move quarterly_tax_payment.py 06_tax\ 2>nul
move yearend_tax_reconciliation.py 06_tax\ 2>nul

echo Done!
echo.

echo ============================================================
echo MOVING FILES TO 07_EMAIL...
echo ============================================================

move email_service.py 07_email\ 2>nul
move test_email.py 07_email\ 2>nul
move check_email_config.py 07_email\ 2>nul
move check_email_exports.py 07_email\ 2>nul

echo Done!
echo.

echo ============================================================
echo MOVING FILES TO 08_SETUP...
echo ============================================================

move migrate_*.py 08_setup\ 2>nul
move setup_test_database.py 08_setup\ 2>nul
move check_database_schema.py 08_setup\ 2>nul
move run_tests.py 08_setup\ 2>nul
move organize_scripts.py 08_setup\ 2>nul

echo Done!
echo.

echo ============================================================
echo MOVING FILES TO 09_PROSPECTS...
echo ============================================================

move add_prospect.py 09_prospects\ 2>nul
move import_prospects.py 09_prospects\ 2>nul
move list_prospects.py 09_prospects\ 2>nul
move send_prospect_report.py 09_prospects\ 2>nul
move view_communications.py 09_prospects\ 2>nul

echo Done!
echo.

echo ============================================================
echo MOVING FILES TO 10_UTILITIES...
echo ============================================================

move backup_database.py 10_utilities\ 2>nul
move reverse_transaction.py 10_utilities\ 2>nul
move update_investor_emails.py 10_utilities\ 2>nul
move view_investor_emails.py 10_utilities\ 2>nul
move view_logs.py 10_utilities\ 2>nul
move view_positions.py 10_utilities\ 2>nul

echo Done!
echo.

echo ============================================================
echo MOVING FILES TO 99_ARCHIVE...
echo ============================================================

move add_warning_suppression.py 99_archive\ 2>nul
move daily_nav_enhanced.py 99_archive\ 2>nul
move find_email_service.py 99_archive\ 2>nul
move organize_files.py 99_archive\ 2>nul
move process_contribution_historical.py 99_archive\ 2>nul
move process_withdrawal_historical.py 99_archive\ 2>nul
move show_test_email_usage.py 99_archive\ 2>nul

echo Done!
echo.

echo ============================================================
echo ORGANIZATION COMPLETE!
echo ============================================================
echo.
echo Files remaining in scripts root:
dir *.py /b
echo.
echo Folders created:
dir /b /ad
echo.
echo ============================================================
echo SUCCESS! Your scripts are now organized.
echo See COMPLETE_ORGANIZATION_PLAN.md for details.
echo ============================================================
echo.

pause
