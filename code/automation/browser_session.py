from contextlib import contextmanager
from typing import Optional, List
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page


class BrowserSession:
    """
    Context manager to create/close Playwright browser, context, and page.
    Usage:
        with BrowserSession(headless=True, permissions=["camera", "microphone"]) as session:
            page = session.page
    """

    def __init__(self, headless: bool = True, permissions: Optional[List[str]] = None, extra_args: Optional[List[str]] = None):
        self.headless = headless
        self.permissions = permissions or []
        # Add safe defaults for containerized Chromium
        default_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-zygote",
        ]
        self.launch_args = default_args + (extra_args or [])
        self._playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def __enter__(self):
        self._playwright = sync_playwright().start()
        # Pass hardened args suitable for Northflank containers
        self.browser = self._playwright.chromium.launch(headless=self.headless, args=self.launch_args)
        self.context = self.browser.new_context(permissions=self.permissions)
        self.page = self.context.new_page()
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.context:
                self.context.close()
        finally:
            try:
                if self.browser:
                    self.browser.close()
            finally:
                if self._playwright:
                    self._playwright.stop()