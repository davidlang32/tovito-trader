"""
Tutorial: Viewing Your Portfolio
==================================

Records the portfolio viewing experience in the investor portal.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tutorials.base_recorder import BaseRecorder
from scripts.tutorials.browser_recorder import BrowserRecorder
from scripts.tutorials.config import SCREENSHOT_DIR

TUTORIAL_ID = 'investor_portfolio'

TEST_EMAIL = 'alpha@test.com'
TEST_PASSWORD = 'TestPass123!'


class PortfolioTutorial(BaseRecorder):
    """Records the portfolio viewing walkthrough."""

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

            # Step 1: Current position
            path = browser.capture_screenshot(f'{TUTORIAL_ID}_step01')
            self.add_step(
                'Your Current Position',
                'The dashboard header shows your current portfolio value and today\'s '
                'NAV per share. Your total return since inception is shown as a percentage.',
                str(path),
            )

            # Step 2: NAV explanation
            path = browser.capture_screenshot(f'{TUTORIAL_ID}_step02')
            self.add_step(
                'Understanding NAV',
                'NAV (Net Asset Value) per share represents the value of each share you own. '
                'Your portfolio value = your shares x NAV per share. NAV is updated daily after market close.',
                str(path),
            )

            # Step 3: Performance metrics
            browser.page.evaluate('window.scrollTo(0, 400)')
            browser.wait(1)
            path = browser.capture_screenshot(f'{TUTORIAL_ID}_step03')
            self.add_step(
                'Performance Metrics',
                'Track your returns across different timeframes: daily change, month-to-date, '
                'year-to-date, and total return since you joined the fund.',
                str(path),
            )


if __name__ == '__main__':
    PortfolioTutorial(TUTORIAL_ID).run()
