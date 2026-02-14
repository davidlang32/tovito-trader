@echo off
REM ============================================================
REM Fund API Regression Test Runner
REM ============================================================
REM
REM Usage:
REM   run_api_tests.bat                    - Run all tests
REM   run_api_tests.bat --verbose          - Detailed output
REM   run_api_tests.bat --report           - Generate HTML report
REM   run_api_tests.bat --section auth     - Test only auth
REM
REM Environment:
REM   Set TEST_PASSWORD before running, or edit this file
REM ============================================================

cd /d %~dp0

REM Set your test credentials here (or use environment variables)
if "%TEST_EMAIL%"=="" set TEST_EMAIL=dlang32@gmail.com
if "%TEST_PASSWORD%"=="" (
    echo.
    echo ============================================================
    echo  ERROR: TEST_PASSWORD not set
    echo ============================================================
    echo.
    echo  Please set your test password:
    echo.
    echo    set TEST_PASSWORD=YourPassword123!
    echo    run_api_tests.bat
    echo.
    echo  Or edit this batch file to set it directly.
    echo ============================================================
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Running Fund API Regression Tests
echo ============================================================
echo.

python test_api_regression.py --email %TEST_EMAIL% --password "%TEST_PASSWORD%" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ============================================================
    echo  TESTS FAILED - See output above
    echo ============================================================
) else (
    echo.
    echo ============================================================
    echo  ALL TESTS PASSED
    echo ============================================================
)

pause
