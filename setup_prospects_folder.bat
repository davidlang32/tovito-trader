@echo off
REM Setup Prospects Folder Structure (Optional)

echo ======================================
echo TOVITO TRADER - PROSPECTS SETUP
echo ======================================
echo.
echo This will create a dedicated prospects folder for better organization.
echo Your current prospects.csv will be moved there.
echo.
echo Press Ctrl+C to cancel, or
pause

echo.
echo Creating prospects folder...
if not exist "C:\tovito-trader\prospects" mkdir "C:\tovito-trader\prospects"
echo   Created: C:\tovito-trader\prospects\
echo.

REM Move existing prospects.csv if it exists
if exist "C:\tovito-trader\prospects.csv" (
    echo Moving prospects.csv to prospects folder...
    move "C:\tovito-trader\prospects.csv" "C:\tovito-trader\prospects\prospects.csv"
    echo   Moved: prospects.csv -^> prospects\prospects.csv
    echo.
)

echo.
echo ======================================
echo SETUP COMPLETE!
echo ======================================
echo.
echo Your prospects folder: C:\tovito-trader\prospects\
echo.
echo Now use:
echo   python scripts\send_prospect_report.py --month 1 --year 2026 --prospects prospects\prospects.csv
echo.
echo Or just:
echo   python scripts\send_prospect_report.py --month 1 --year 2026 --prospects prospects.csv
echo.
echo (Script will find it in prospects folder automatically!)
echo.
pause
