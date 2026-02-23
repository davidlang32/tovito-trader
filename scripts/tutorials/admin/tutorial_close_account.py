"""
Tutorial: Closing an Investor Account
=======================================

Records the account closure process using close_investor_account.py.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tutorials.base_recorder import BaseRecorder
from scripts.tutorials.cli_recorder import save_terminal_frame
from scripts.tutorials.config import SCREENSHOT_DIR

TUTORIAL_ID = 'admin_close_account'


class CloseAccountTutorial(BaseRecorder):
    """Records the account closure workflow."""

    def record(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        # Overview
        overview_text = (
            "# Closing an Investor Account\n"
            "#\n"
            "# Account closure is a full liquidation that:\n"
            "#   1. Calculates the investor's current position value\n"
            "#   2. Processes a full withdrawal via fund flow pathway\n"
            "#   3. Records realized gains and tax events\n"
            "#   4. Sets investor status to 'Inactive'\n"
            "#\n"
            "# Requires the --investor flag with the investor ID.\n"
            "\n"
            "$ python scripts/investor/close_investor_account.py --investor 20260101-01A"
        )
        path = save_terminal_frame(
            overview_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step01.png',
            title='Close Account',
        )
        self.add_step(
            'Account Closure Overview',
            'Account closure performs a full liquidation via the fund flow pathway. '
            'Run with --investor flag specifying the investor ID.',
            str(path),
        )

        # Account summary
        summary_text = (
            "$ python scripts/investor/close_investor_account.py --investor 20260101-01A\n"
            "\n"
            "=== Account Closure ===\n"
            "\n"
            "Investor: Alpha Investor (20260101-01A)\n"
            "  Status: Active\n"
            "  Current shares: 10,000.0000\n"
            "  Net investment: $10,000.00\n"
            "  Current value: $10,595.00 (NAV: $1.0595)\n"
            "  Unrealized gain: $595.00\n"
            "  Estimated tax (37%): $220.15\n"
            "  Eligible proceeds: $10,374.85\n"
            "\n"
            "This will:\n"
            "  - Withdraw 100% of shares ($10,595.00)\n"
            "  - Record realized gain of $595.00\n"
            "  - Create tax event (settled quarterly)\n"
            "  - Set investor status to 'Inactive'\n"
            "\n"
            "Close this account? (yes/no): yes"
        )
        path = save_terminal_frame(
            summary_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step02.png',
            title='close_investor_account.py',
        )
        self.add_step(
            'Review Account Summary',
            'The script shows the investor\'s current position, unrealized gains, '
            'estimated tax liability, and eligible proceeds before confirmation.',
            str(path),
        )

        # Confirmation result
        result_text = (
            "Close this account? (yes/no): yes\n"
            "\n"
            "Processing account closure...\n"
            "\n"
            "SUCCESS: Account closed for Alpha Investor\n"
            "  Fund flow request #2 created and processed\n"
            "  Shares redeemed: 10,000.0000\n"
            "  Withdrawal amount: $10,595.00\n"
            "  Realized gain: $595.00\n"
            "  Tax due (quarterly): $220.15\n"
            "  Net proceeds: $10,595.00\n"
            "  Investor status: Inactive\n"
            "  Email notification sent."
        )
        path = save_terminal_frame(
            result_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step03.png',
            title='close_investor_account.py',
        )
        self.add_step(
            'Confirm and Process Closure',
            'After confirmation, the script processes the full withdrawal, records tax events, '
            'and sets the investor to Inactive status. An email notification is sent.',
            str(path),
        )


if __name__ == '__main__':
    CloseAccountTutorial(TUTORIAL_ID).run()
