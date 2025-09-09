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

    def __init__(self, headless: bool = True, permissions: Optional[List[str]] = None):
        self.headless = headless
        self.permissions = permissions or []
        self._playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def __enter__(self):
        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(headless=self.headless)
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