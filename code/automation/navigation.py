from typing import Optional
from playwright.sync_api import Page, Frame, ElementHandle


def open_ui_url(page: Page, url: str) -> None:
    page.goto(url)


def get_daily_iframe(page: Page) -> Optional[ElementHandle]:
    page.wait_for_selector("iframe", timeout=10000)
    return page.query_selector("iframe")


def get_daily_frame(page: Page) -> Optional[Frame]:
    iframe_el = get_daily_iframe(page)
    return iframe_el.content_frame() if iframe_el else None


def ensure_ui_ready(page: Page) -> None:
    # Basic presence check for the custom UI input
    page.wait_for_selector('input[placeholder*="Enter room name"]', timeout=10000)
