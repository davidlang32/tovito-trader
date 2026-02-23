"""
Tutorial: Logging Into Your Account
=====================================

Records the investor portal login flow using Playwright.
Requires the portal services (API + frontend) to be running.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tutorials.base_recorder import BaseRecorder
from scripts.tutorials.browser_recorder import BrowserRecorder
from scripts.tutorials.config import SCREENSHOT_DIR

TUTORIAL_ID = 'investor_login'

# Test credentials (must match dev database auth records)
TEST_EMAIL = 'alpha@test.com'
TEST_PASSWORD = 'TestPass123!'


class LoginTutorial(BaseRecorder):
    """Records the investor portal login flow."""

    def record(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

        with BrowserRecorder(headless=True, record_video=False) as browser:
            # Step 1: Navigate to login page
            browser.navigate('http://localhost:3000')
            browser.wait(2)
            path = browser.capture_screenshot(f'{TUTORIAL_ID}_step01')
            self.add_step(
                'Open the Investor Portal',
                'Navigate to the Tovito Trader investor portal login page.',
                str(path),
            )

            # Step 2: Enter email
            browser.fill('input[type="email"]', TEST_EMAIL)
            browser.wait(0.5)
            path = browser.capture_screenshot(f'{TUTORIAL_ID}_step02')
            self.add_step(
                'Enter Your Email',
                'Type your registered email address in the email field.',
                str(path),
            )

            # Step 3: Enter password
            browser.fill('input[type="password"]', TEST_PASSWORD)
            browser.wait(0.5)
            path = browser.capture_screenshot(f'{TUTORIAL_ID}_step03')
            self.add_step(
                'Enter Your Password',
                'Type your password in the password field.',
                str(path),
            )

            # Step 4: Click sign in
            browser.click('button[type="submit"]')
            browser.wait(3)
            path = browser.capture_screenshot(f'{TUTORIAL_ID}_step04')
            self.add_step(
                'Click Sign In',
                'Click the Sign In button. You will be redirected to your dashboard.',
                str(path),
            )


if __name__ == '__main__':
    LoginTutorial(TUTORIAL_ID).run()
