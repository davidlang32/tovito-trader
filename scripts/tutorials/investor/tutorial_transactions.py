"""
Tutorial: Transaction History
==============================

Records the transaction history viewing experience.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tutorials.base_recorder import BaseRecorder
from scripts.tutorials.browser_recorder import BrowserRecorder
from scripts.tutorials.config import SCREENSHOT_DIR

TUTORIAL_ID = 'investor_transactions'

TEST_EMAIL = 'alpha@test.com'
TEST_PASSWORD = 'TestPass123!'


class TransactionsTutorial(BaseRecorder):
    """Records the transaction history walkthrough."""

    def record(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        with BrowserRecorder(headless=True) as browser:
            # Login
            browser.navigate('http://localhost:3000')
            browser.wait(2)
            browser.fill('input[type="email"]', TEST_EMAIL)
            browser.fill('input[type="password"]', TEST_PASSWORD)
            browser.click('button[type="submit"]')
            browser.wait(3)

            # Step 1: Recent transactions panel
            browser.page.evaluate('window.scrollTo(0, 400)')
            browser.wait(1)
            path = browser.capture_screenshot(f'{TUTORIAL_ID}_step01')
            self.add_step(
                'Recent Transactions',
                'Your recent transactions appear in the right panel of the dashboard. '
                'Each entry shows the type (contribution/withdrawal), date, and amount.',
                str(path),
            )

            # Step 2: Transaction details
            path = browser.capture_screenshot(f'{TUTORIAL_ID}_step02')
            self.add_step(
                'Transaction Types',
                'Contributions are shown in green (money added to your account). '
                'Withdrawals are shown in red (money disbursed to you). '
                'Your initial investment is listed as the first transaction.',
                str(path),
            )

            # Step 3: Totals
            browser.page.evaluate('window.scrollTo(0, 600)')
            browser.wait(1)
            path = browser.capture_screenshot(f'{TUTORIAL_ID}_step03')
            self.add_step(
                'Contribution & Withdrawal Totals',
                'Below the transaction list, you can see your total contributions and total withdrawals. '
                'The difference represents your net investment in the fund.',
                str(path),
            )


if __name__ == '__main__':
    TransactionsTutorial(TUTORIAL_ID).run()
