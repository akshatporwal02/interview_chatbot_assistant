from typing import Optional
from playwright.sync_api import Page, Frame


def fill_room_and_join(page: Page, daily_frame: Optional[Frame], meeting_url: str, username: str = "Strata(Bot)") -> None:
    print("[join_flow] Waiting for Join Room button...")
    btn = page.wait_for_selector("#join-room-button", timeout=10000)
    try:
        btn.scroll_into_view_if_needed()
    except Exception:
        pass
    page.click("#join-room-button")
    page.wait_for_timeout(300)  # small settle time

    # Step 2: Enter the room URL
    print("[join_flow] Filling room URL...")
    page.wait_for_selector("#roomUrl", timeout=10000)
    page.fill("#roomUrl", meeting_url)
    page.wait_for_timeout(200)

    # Step 3: Click the "Next" button (validate room)
    print("[join_flow] Validating room...")
    page.wait_for_selector("#validate-room-button", timeout=10000)
    page.click("#validate-room-button")
    page.wait_for_timeout(300)

    # Step 4: Check the instructions checkbox
    print("[join_flow] Checking instructions checkbox...")
    page.wait_for_selector("#instructions-checkbox", timeout=10000)
    page.check("#instructions-checkbox")
    page.wait_for_timeout(200)

    # Step 5: Click the "Next" button (confirm joining room)
    print("[join_flow] Confirming join...")
    page.wait_for_selector("#join-room-confirm-button", timeout=10000)
    page.click("#join-room-confirm-button")
    page.wait_for_timeout(500)

    # Step 6: Now switch to the Daily iframe. If not provided or not yet available, resolve it now.
    if not daily_frame:
        # Poll for the iframe without throwing, up to ~15s
        for _ in range(15):
            try:
                iframe_el = page.query_selector('iframe')
                if iframe_el:
                    df = iframe_el.content_frame()
                    if df:
                        daily_frame = df
                        break
            except Exception:
                pass
            page.wait_for_timeout(5000)

    if not daily_frame:
        raise RuntimeError("Daily iframe/frame not found after confirming join.")

    print("[join_flow] Setting username in Daily prejoin...")
    daily_frame.wait_for_selector("input#username", timeout=20000)
    daily_frame.fill("input#username", username)

    daily_frame.wait_for_selector('button:has-text("Continue")', timeout=10000)
    daily_frame.click('button:has-text("Continue")')

    daily_frame.wait_for_selector('button:has-text("Join")', timeout=10000)
    daily_frame.click('button:has-text("Join")')