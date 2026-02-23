"""
Tutorial: Your Dashboard Overview
===================================

Records a tour of the investor dashboard using Playwright.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tutorials.base_recorder import BaseRecorder
from scripts.tutorials.browser_recorder import BrowserRecorder
from scripts.tutorials.config import SCREENSHOT_DIR

TUTORIAL_ID = 'investor_dashboard'

TEST_EMAIL = 'alpha@test.com'
TEST_PASSWORD = 'TestPass123!'


class DashboardTutorial(BaseRecorder):
    """Records the investor dashboard overview tour."""

    def record(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        with BrowserRecorder(headless=True) as browser:
            # Login first
            browser.navigate('http://localhost:3000')
            browser.wait(2)
            browser.fill('input[type="email"]', TEST_EMAIL)
            browser.fill('input[type="password"]', TEST_PASSWORD)
            browser.click('button[type="submit"]')
            browser.wait(3)

            # Step 1: Dashboard overview
            path = browser.capture_screenshot(f'{TUTORIAL_ID}_step01')
            self.add_step(
                'Dashboard Overview',
                'After logging in, you see your main dashboard with portfolio value, '
                'NAV per share, and total return at the top.',
                str(path),
            )

            # Step 2: Portfolio stats cards
            path = browser.capture_screenshot(f'{TUTORIAL_ID}_step02', full_page=False)
            self.add_step(
                'Portfolio Summary Cards',
                'The top section shows your current portfolio value, NAV per share, '
                'shares owned, and total return since inception.',
                str(path),
            )

            # Step 3: Fund performance section
            browser.page.evaluate('window.scrollTo(0, 400)')
            browser.wait(1)
            path = browser.capture_screenshot(f'{TUTORIAL_ID}_step03')
            self.add_step(
                'Fund Performance',
                'The performance section shows daily, month-to-date, year-to-date, '
                'and since-inception returns. Fund size and active investor count are shown below.',
                str(path),
            )

            # Step 4: Recent transactions
            browser.page.evaluate('window.scrollTo(0, 600)')
            browser.wait(1)
            path = browser.capture_screenshot(f'{TUTORIAL_ID}_step04')
            self.add_step(
                'Recent Transactions',
                'The right panel shows your most recent transactions including '
                'contributions and withdrawals with dates and amounts.',
                str(path),
            )

            # Step 5: Account summary
            browser.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            browser.wait(1)
            path = browser.capture_screenshot(f'{TUTORIAL_ID}_step05')
            self.add_step(
                'Account Summary',
                'At the bottom, view your net investment, initial capital, current shares, '
                'and investor ID. Use the refresh button in the header to update data.',
                str(path),
            )


if __name__ == '__main__':
    DashboardTutorial(TUTORIAL_ID).run()
