"""
Browser Recorder
================

Playwright-based browser automation for recording investor portal tutorials.
Handles:
- Browser launch with video recording
- Page navigation, form filling, clicking
- Screenshot capture at each step
- Service management (start/stop FastAPI + Vite)
"""

import os
import sys
import time
import subprocess
import tempfile
from pathlib import Path

from scripts.tutorials.config import (
    PROJECT_ROOT, VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
    DEV_DB_PATH, SCREENSHOT_DIR,
)


class BrowserRecorder:
    """
    Context manager for Playwright browser recording sessions.

    Usage:
        with BrowserRecorder() as recorder:
            recorder.navigate('http://localhost:3000')
            path = recorder.capture_screenshot('step1')
            recorder.fill('input[type="email"]', 'test@test.com')
            path = recorder.capture_screenshot('step2')
            # video is saved on exit
    """

    def __init__(self, headless=True, record_video=True):
        self.headless = headless
        self.record_video = record_video
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._video_dir = None
        self._raw_video_path = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)

        context_kwargs = {
            'viewport': {'width': VIEWPORT_WIDTH, 'height': VIEWPORT_HEIGHT},
        }

        if self.record_video:
            self._video_dir = tempfile.mkdtemp(prefix='tutorial_video_')
            context_kwargs['record_video_dir'] = self._video_dir
            context_kwargs['record_video_size'] = {
                'width': VIEWPORT_WIDTH,
                'height': VIEWPORT_HEIGHT,
            }

        self._context = self._browser.new_context(**context_kwargs)
        self._page = self._context.new_page()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._page:
            # Get video path before closing
            if self.record_video and self._page.video:
                try:
                    self._raw_video_path = self._page.video.path()
                except Exception:
                    pass
            self._page.close()

        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

        return False  # Don't suppress exceptions

    @property
    def page(self):
        """Access the underlying Playwright page for advanced operations."""
        return self._page

    @property
    def raw_video_path(self):
        """Path to the raw video recording (webm). Available after context manager exits."""
        return self._raw_video_path

    def navigate(self, url):
        """Navigate to a URL and wait for the page to load."""
        self._page.goto(url, wait_until='networkidle')

    def click(self, selector, timeout=10000):
        """Click an element by CSS selector."""
        self._page.click(selector, timeout=timeout)

    def fill(self, selector, value, timeout=10000):
        """Fill a form input by CSS selector."""
        self._page.fill(selector, value, timeout=timeout)

    def wait(self, seconds):
        """Wait for a specified number of seconds."""
        self._page.wait_for_timeout(int(seconds * 1000))

    def wait_for_selector(self, selector, timeout=10000):
        """Wait for an element to appear."""
        self._page.wait_for_selector(selector, timeout=timeout)

    def capture_screenshot(self, name, full_page=False):
        """
        Take a screenshot of the current page state.

        Args:
            name: Screenshot name (used in filename)
            full_page: Whether to capture the full scrollable page

        Returns:
            Path to the saved screenshot.
        """
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        path = SCREENSHOT_DIR / f'{name}.png'
        self._page.screenshot(path=str(path), full_page=full_page)
        return path


class PortalServiceManager:
    """
    Manages the FastAPI + Vite dev server for browser tutorial recording.

    Usage:
        with PortalServiceManager() as services:
            # API is at http://localhost:8000
            # Frontend is at http://localhost:3000
            ...
    """

    def __init__(self, db_path=None):
        self.db_path = db_path or DEV_DB_PATH
        self._api_proc = None
        self._frontend_proc = None

    def __enter__(self):
        self._start_api()
        self._start_frontend()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop_all()
        return False

    def _start_api(self):
        """Start the FastAPI backend server."""
        env = os.environ.copy()
        env['DATABASE_PATH'] = str(self.db_path)

        self._api_proc = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn',
             'apps.investor_portal.api.main:app',
             '--port', '8000', '--log-level', 'warning'],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for API to be ready
        import urllib.request
        for _ in range(30):
            try:
                req = urllib.request.urlopen('http://localhost:8000/health', timeout=2)
                if req.status == 200:
                    print("  API server started (port 8000)")
                    return
            except Exception:
                pass
            time.sleep(1)

        raise RuntimeError("API server did not start within 30 seconds")

    def _start_frontend(self):
        """Start the Vite dev server."""
        frontend_dir = (
            PROJECT_ROOT / 'apps' / 'investor_portal' / 'frontend' / 'investor_portal'
        )

        self._frontend_proc = subprocess.Popen(
            ['npm', 'run', 'dev'],
            cwd=str(frontend_dir),
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for Vite to be ready
        import urllib.request
        for _ in range(30):
            try:
                req = urllib.request.urlopen('http://localhost:3000', timeout=2)
                if req.status < 500:
                    print("  Frontend started (port 3000)")
                    return
            except Exception:
                pass
            time.sleep(1)

        raise RuntimeError("Frontend did not start within 30 seconds")

    def _stop_all(self):
        """Stop all managed services."""
        for proc, name in [(self._api_proc, 'API'), (self._frontend_proc, 'Frontend')]:
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                print(f"  {name} server stopped")
