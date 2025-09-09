from typing import Optional
from playwright.sync_api import Page


def take_screenshot(page: Page, full_page: bool = False) -> bytes:
    return page.screenshot(full_page=full_page)