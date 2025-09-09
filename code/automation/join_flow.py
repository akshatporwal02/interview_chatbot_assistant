from playwright.sync_api import Page, Frame


def fill_room_and_join(page: Page, daily_frame: Frame, meeting_url: str, username: str = "Observer Bot") -> None:
    # Fill the room URL in host UI
    page.fill('input[placeholder*="Enter room name"]', meeting_url)
    page.click('button:has-text("Join Room")')

    # Inside Daily iframe
    daily_frame.wait_for_selector("input#username", timeout=10000)
    daily_frame.fill("input#username", username)

    daily_frame.wait_for_selector('button:has-text("Continue")', timeout=10000)
    daily_frame.click('button:has-text("Continue")')

    daily_frame.wait_for_selector('button:has-text("Join")', timeout=10000)
    daily_frame.click('button:has-text("Join")')