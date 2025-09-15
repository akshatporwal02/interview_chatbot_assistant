from typing import Optional
from playwright.sync_api import Page, Frame, ElementHandle


def open_ui_url(page: Page, url: str) -> None:
    page.goto(url)
    # Ensure initial HTML is parsed before we begin
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass


def get_daily_iframe(page: Page) -> Optional[ElementHandle]:
    # Do not require visibility; the iframe may be attached but not yet visible
    try:
        page.wait_for_selector("iframe", state="attached", timeout=5000)
    except Exception:
        pass
    return page.query_selector("iframe")


def get_daily_frame(page: Page) -> Optional[Frame]:
    iframe_el = get_daily_iframe(page)
    return iframe_el.content_frame() if iframe_el else None


def ensure_ui_ready(page: Page) -> None:
    # Presence check for the new custom UI elements
    # Either the top-level Join button or the room URL input should be visible
    try:
        page.wait_for_selector('#join-room-button', timeout=5000)
        return
    except Exception:
        pass

    page.wait_for_selector('#roomUrl', timeout=10000)
