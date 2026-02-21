"""
TastyTrade Connection Test
============================
Standalone script to verify TastyTrade API connectivity and account access.
Run this before switching production to TastyTrade.

Usage:
    python scripts/validation/test_tastytrade_connection.py

Exit codes:
    0 = All tests passed
    1 = One or more tests failed
"""

import sys
import os
from pathlib import Path

# Ensure project root is in path
PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from dotenv import load_dotenv
load_dotenv(PROJECT_DIR / ".env")


def main():
    """Run all TastyTrade connection tests."""
    print("=" * 60)
    print("TastyTrade Connection Test")
    print("=" * 60)
    print()

    passed = 0
    failed = 0

    # ---- Step 1: Check environment variables ----
    print("Step 1: Checking environment variables...")

    client_id = os.getenv('TASTYTRADE_CLIENT_SECRET')
    refresh_token = os.getenv('TASTYTRADE_REFRESH_TOKEN')
    account_id = os.getenv('TASTYTRADE_ACCOUNT_ID')

    if not client_id:
        print("  [FAIL] TASTYTRADE_CLIENT_SECRET not set in .env")
        failed += 1
    else:
        print("  [OK] TASTYTRADE_CLIENT_SECRET configured")
        passed += 1

    if not refresh_token:
        print("  [FAIL] TASTYTRADE_REFRESH_TOKEN not set in .env")
        failed += 1
    else:
        print("  [OK] TASTYTRADE_REFRESH_TOKEN configured")
        passed += 1

    if not account_id:
        print("  [FAIL] TASTYTRADE_ACCOUNT_ID not set in .env")
        failed += 1
    else:
        # Mask account ID in output (show only last 4 chars)
        print(f"  [OK] TASTYTRADE_ACCOUNT_ID configured (ending ...{account_id[-4:]})")
        passed += 1

    if failed > 0:
        print(f"\n[STOP] Cannot proceed — {failed} env var(s) missing.")
        print("Configure these in your .env file and retry.")
        return False

    print()

    # ---- Step 2: Import and initialize client ----
    print("Step 2: Initializing TastyTrade client...")

    try:
        from src.api.tastytrade_client import TastyTradeClient
        client = TastyTradeClient()
        print("  [OK] TastyTrade client initialized (OAuth)")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Client initialization: {e}")
        failed += 1
        print(f"\n[STOP] Cannot proceed — client initialization failed.")
        return False

    print()

    # ---- Step 3: Test OAuth session ----
    print("Step 3: Establishing OAuth session...")

    try:
        session = client._get_session()
        print("  [OK] OAuth session established")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Session creation: {e}")
        failed += 1
        print(f"\n[STOP] Cannot proceed — OAuth session failed.")
        print("Verify your TASTYTRADE_CLIENT_SECRET and TASTYTRADE_REFRESH_TOKEN.")
        return False

    print()

    # ---- Step 4: Test account access ----
    print("Step 4: Accessing configured account...")

    try:
        account = client._get_account()
        print(f"  [OK] Account loaded (ending ...{account.account_number[-4:]})")
        print(f"  [OK] Account type: {account.account_type_name}")
        passed += 1
    except ValueError as e:
        print(f"  [FAIL] Account access: {e}")
        failed += 1
        print(f"\n[STOP] Cannot proceed — account not found.")
        return False
    except Exception as e:
        print(f"  [FAIL] Account access: {e}")
        failed += 1
        return False

    print()

    # ---- Step 5: Fetch account balance ----
    print("Step 5: Fetching account balance...")

    try:
        balance = client.get_account_balance()
        print(f"  [OK] Balance retrieved successfully")
        print(f"       Total Equity:       ${balance['total_equity']:>12,.2f}")
        print(f"       Cash Balance:       ${balance['total_cash']:>12,.2f}")
        print(f"       Stock Long Value:   ${balance['stock_long_value']:>12,.2f}")
        print(f"       Option Long Value:  ${balance['option_long_value']:>12,.2f}")
        print(f"       Option Short Value: ${balance['option_short_value']:>12,.2f}")

        # Validate total_equity is positive
        if balance['total_equity'] > 0:
            print(f"  [OK] Total equity is positive")
            passed += 1
        else:
            print(f"  [WARN] Total equity is ${balance['total_equity']:,.2f}")
            passed += 1  # Still a pass — could be a new/empty account
    except Exception as e:
        print(f"  [FAIL] Balance fetch: {e}")
        failed += 1

    print()

    # ---- Step 6: Fetch positions ----
    print("Step 6: Fetching positions...")

    try:
        positions = client.get_positions()
        print(f"  [OK] Positions retrieved: {len(positions)} position(s)")

        if positions:
            print(f"       Sample positions:")
            for pos in positions[:5]:  # Show first 5 max
                print(f"         {pos['symbol']:>10}  "
                      f"qty={pos['quantity']:>8.2f}  "
                      f"type={pos['instrument_type']}")
            if len(positions) > 5:
                print(f"         ... and {len(positions) - 5} more")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Positions fetch: {e}")
        failed += 1

    print()

    # ---- Step 7: Market status ----
    print("Step 7: Checking market status...")

    try:
        is_open = client.is_market_open()
        status = "OPEN" if is_open else "CLOSED"
        print(f"  [OK] Market status: {status}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Market status: {e}")
        failed += 1

    print()

    # ---- Step 8: Test factory integration ----
    print("Step 8: Testing brokerage factory integration...")

    try:
        from src.api.brokerage import get_brokerage_client
        factory_client = get_brokerage_client('tastytrade')
        factory_balance = factory_client.get_account_balance()
        print(f"  [OK] Factory returned TastyTrade client")
        print(f"  [OK] Factory client balance: ${factory_balance['total_equity']:,.2f}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Factory integration: {e}")
        failed += 1

    # ---- Step 9: Test combined-brokerage NAV ----
    print()
    print("Step 9: Testing combined-brokerage balance...")

    try:
        from src.api.brokerage import get_combined_balance, get_configured_providers

        providers = get_configured_providers()
        print(f"  Configured providers: {', '.join(providers)}")

        if len(providers) > 1:
            combined = get_combined_balance()
            print(f"  [OK] Combined balance retrieved")
            print(f"       Combined Equity: ${combined['total_equity']:>12,.2f}")
            print(f"       Combined Cash:   ${combined['total_cash']:>12,.2f}")
            print(f"       Sources:         {combined['source']}")

            # Show per-brokerage breakdown
            for prov, detail in combined.get('brokerage_details', {}).items():
                prov_equity = detail.get('total_equity', 0)
                print(f"         {prov}: ${prov_equity:>12,.2f}")

            if combined['total_equity'] > 0:
                print(f"  [OK] Combined equity is positive")
            passed += 1
        else:
            print(f"  [SKIP] Only one provider configured ({providers[0]})")
            print(f"         Set BROKERAGE_PROVIDERS=tradier,tastytrade in .env for combined mode")
            passed += 1

    except Exception as e:
        print(f"  [FAIL] Combined balance: {e}")
        failed += 1

    # ---- Summary ----
    print()
    print("=" * 60)
    total = passed + failed
    if failed == 0:
        print(f"ALL {passed} TESTS PASSED")
        print()
        print("TastyTrade integration is ready.")
        print("For combined NAV, set BROKERAGE_PROVIDERS=tradier,tastytrade in .env")
    else:
        print(f"RESULTS: {passed}/{total} passed, {failed} failed")
        print()
        print("Fix the failures above before switching to production.")
    print("=" * 60)

    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
