"""
Tutorial: Processing a Contribution/Withdrawal
================================================

Records the 3-step fund flow process:
1. Submit a contribution request
2. Match to brokerage ACH
3. Process share accounting

Uses wexpect to drive the interactive CLI scripts against the dev database.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tutorials.base_recorder import BaseRecorder
from scripts.tutorials.cli_recorder import CLIRecorder, CLICommandRecorder, save_terminal_frame
from scripts.tutorials.config import SCREENSHOT_DIR

TUTORIAL_ID = 'admin_fund_flow'


class FundFlowTutorial(BaseRecorder):
    """Records the complete 3-step fund flow workflow."""

    def record(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        # -- Introduction frame --
        intro_text = (
            "# Fund Flow Tutorial: Processing a Contribution\n"
            "#\n"
            "# The fund flow process has 3 steps:\n"
            "#   1. Submit: Create a fund flow request\n"
            "#   2. Match:  Match request to brokerage ACH transfer\n"
            "#   3. Process: Execute share accounting\n"
            "#\n"
            "# This tutorial walks through a $5,000 contribution.\n"
            "\n"
            "$ # Step 1: Submit the fund flow request\n"
            "$ python scripts/investor/submit_fund_flow.py"
        )
        intro_path = save_terminal_frame(
            intro_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step00.png',
            title='Fund Flow - Overview',
        )
        self.add_step(
            'Fund Flow Overview',
            'The fund flow process is a 3-step workflow: Submit, Match, Process. '
            'This tutorial demonstrates a $5,000 contribution.',
            str(intro_path),
        )

        # -- Step 1: Submit fund flow request --
        self._record_submit()

        # -- Step 2: Match to ACH --
        self._record_match()

        # -- Step 3: Process --
        self._record_process()

    def _record_submit(self):
        """Record the submit_fund_flow.py interactive session."""
        try:
            with CLIRecorder(
                'scripts/investor/submit_fund_flow.py',
                title='submit_fund_flow.py',
            ) as cli:
                # Select contribution type
                cli.expect_and_respond('Select type', '1')
                path = cli.capture_frame(
                    f'{TUTORIAL_ID}_step01',
                    'Step 1: Select Contribution',
                )
                self.add_step(
                    'Select Request Type',
                    'Choose option 1 for Contribution (or 2 for Withdrawal).',
                    str(path),
                )

                # Select investor
                cli.expect_and_respond('Select investor', '1')
                path = cli.capture_frame(
                    f'{TUTORIAL_ID}_step02',
                    'Step 1: Select Investor',
                )
                self.add_step(
                    'Select Investor',
                    'Choose the investor from the numbered list.',
                    str(path),
                )

                # Enter amount
                cli.expect_and_respond('amount', '5000')
                path = cli.capture_frame(
                    f'{TUTORIAL_ID}_step03',
                    'Step 1: Enter Amount',
                )
                self.add_step(
                    'Enter Contribution Amount',
                    'Enter the dollar amount. Example: 5000 for a $5,000 contribution.',
                    str(path),
                )

                # Request date - accept default (today)
                cli.expect_and_respond('date', '')
                path = cli.capture_frame(
                    f'{TUTORIAL_ID}_step04',
                    'Step 1: Request Date',
                )
                self.add_step(
                    'Set Request Date',
                    'Press Enter to use today\'s date, or enter a specific date (YYYY-MM-DD).',
                    str(path),
                )

                # Select method
                cli.expect_and_respond('method', '4')
                path = cli.capture_frame(
                    f'{TUTORIAL_ID}_step05',
                    'Step 1: Request Method',
                )
                self.add_step(
                    'Select Request Method',
                    'Choose how the request was received. Option 4 (admin) is typical for fund manager entries.',
                    str(path),
                )

                # Notes - skip
                cli.expect_and_respond('Notes', '')

                # Confirm submission
                cli.expect_and_respond('Submit', 'yes')
                path = cli.capture_frame(
                    f'{TUTORIAL_ID}_step06',
                    'Step 1: Confirm Submission',
                )
                self.add_step(
                    'Confirm and Submit',
                    'Review the request summary and type "yes" to submit. The request is now in "pending" status.',
                    str(path),
                )

        except Exception as e:
            # If wexpect fails, create a static frame showing the command
            self._fallback_step(
                'Submit Fund Flow Request',
                'Run: python scripts/investor/submit_fund_flow.py\n'
                'Follow the prompts to create a contribution or withdrawal request.',
                f'{TUTORIAL_ID}_step01_fallback',
                f'Error during recording: {e}',
            )

    def _record_match(self):
        """Record the match step (simplified with static frame)."""
        match_text = (
            "$ python scripts/investor/match_fund_flow.py\n"
            "\n"
            "=== Fund Flow Request Matching ===\n"
            "\n"
            "Pending/Approved requests:\n"
            "  Request #1 | Contribution | $5,000.00 | pending\n"
            "    Investor: Alpha Investor\n"
            "\n"
            "Recent ACH trades:\n"
            "  Trade #5  | 2026-01-05 | ACH deposit  | $5,000.00\n"
            "\n"
            "Select request # to match: 1\n"
            "Select trade ID to match: 5\n"
            "\n"
            "  Request: #1 Contribution $5,000.00 (Alpha Investor)\n"
            "  Trade:   #5 ACH deposit $5,000.00 (2026-01-05)\n"
            "\n"
            "Confirm this match? (yes/no): yes\n"
            "\n"
            "SUCCESS: Request #1 matched to trade #5\n"
            "  Status updated: pending -> matched"
        )
        path = save_terminal_frame(
            match_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step07.png',
            title='match_fund_flow.py',
        )
        self.add_step(
            'Match Request to ACH Transfer',
            'Run match_fund_flow.py to link the pending request to the actual brokerage ACH transfer. '
            'This confirms the money has moved.',
            str(path),
        )

    def _record_process(self):
        """Record the process step (simplified with static frame)."""
        process_text = (
            "$ python scripts/investor/process_fund_flow.py\n"
            "\n"
            "=== Fund Flow Processing ===\n"
            "\n"
            "Matched requests ready to process:\n"
            "  Request #1 | Contribution | $5,000.00 | matched\n"
            "    Investor: Alpha Investor\n"
            "    Matched Trade: #5 (ACH deposit $5,000.00)\n"
            "\n"
            "Processing Request #1:\n"
            "  Type: Contribution\n"
            "  Amount: $5,000.00\n"
            "  NAV per share: $1.0270\n"
            "  Shares to issue: 4,868.5491\n"
            "\n"
            "Process this request? (yes/no): yes\n"
            "\n"
            "SUCCESS: Contribution processed!\n"
            "  Shares issued: 4,868.5491\n"
            "  New total shares: 14,868.5491\n"
            "  Transaction ID: ffr-1\n"
            "  Email confirmation sent to investor."
        )
        path = save_terminal_frame(
            process_text,
            SCREENSHOT_DIR / f'{TUTORIAL_ID}_step08.png',
            title='process_fund_flow.py',
        )
        self.add_step(
            'Process Share Accounting',
            'Run process_fund_flow.py to execute the share calculation. '
            'New shares are issued based on the current NAV, and the investor receives an email confirmation.',
            str(path),
        )

    def _fallback_step(self, title, description, name, error_msg):
        """Create a fallback static frame when wexpect recording fails."""
        text = f"# {title}\n#\n# {description}\n\n# Note: {error_msg}"
        path = save_terminal_frame(
            text,
            SCREENSHOT_DIR / f'{name}.png',
            title='Fund Flow',
        )
        self.add_step(title, description, str(path))


if __name__ == '__main__':
    FundFlowTutorial(TUTORIAL_ID).run()
