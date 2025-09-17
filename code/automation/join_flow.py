from typing import Optional
from playwright.sync_api import Page, Frame
from datetime import datetime
import os


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
        # Wait for iframes to appear before scanning
        try:
            page.wait_for_selector("iframe", timeout=15000, state="attached")
        except Exception:
            pass
        # Poll for the correct iframe without throwing, up to ~15s
        # Prefer the frame that actually contains the username/continue controls
        for _ in range(15):
            try:
                frames = page.frames
                # Log frame URLs for diagnostics
                try:
                    urls = [getattr(f, "url", "<no-url>") for f in frames]
                    print(f"[join_flow] Found {len(frames)} frames: {urls}")
                except Exception:
                    pass

                # First preference: frames that visibly contain username or Continue controls
                visible_matches = []
                for f in frames:
                    try:
                        # short waits per frame so we don't block too long overall
                        if f.wait_for_selector("input#username", timeout=500, state="visible"):
                            visible_matches.append(f)
                            continue
                    except Exception:
                        pass
                    try:
                        if f.wait_for_selector('button:has-text("Continue")', timeout=500, state="visible"):
                            visible_matches.append(f)
                    except Exception:
                        pass

                candidate = None
                if visible_matches:
                    # If more than one, prefer the one whose URL mentions daily
                    candidate = next((f for f in visible_matches if "daily" in (getattr(f, "url", "") or "") or "daily.co" in (getattr(f, "url", "") or "")), visible_matches[0])
                else:
                    # Fallback: Heuristic by URL if nothing visible yet
                    candidate = next((f for f in frames if "daily" in (getattr(f, "url", "") or "") or "daily.co" in (getattr(f, "url", "") or "")), None)

                if candidate:
                    daily_frame = candidate
                    break
            except Exception:
                pass
            page.wait_for_timeout(1000)

    if not daily_frame:
        raise RuntimeError("Daily iframe/frame not found after confirming join.")

    print("[join_flow] Setting username in Daily prejoin...")
    try:
        # Some headless runs have visibility quirks; wait until the input is visible
        daily_frame.wait_for_selector("input#username", timeout=20000, state="visible")
    except Exception as e:
        # Diagnostics: take a page screenshot and log frame URL/content length
        try:
            ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            os.makedirs('/app/screenshots', exist_ok=True)
            shot_path = f"/app/screenshots/join_prejoin_debug_{ts}.png"
            page.screenshot(path=shot_path, full_page=True)
            print(f"[join_flow] Username input not attached within timeout. Screenshot saved: {shot_path}")
            try:
                content_len = len(daily_frame.content()) if daily_frame else 0
                print(f"[join_flow] daily_frame url={getattr(daily_frame, 'url', 'N/A')} content_len={content_len}")
            except Exception:
                pass
        except Exception:
            pass
        raise

    daily_frame.fill("input#username", username)
    daily_frame.wait_for_selector('button:has-text("Continue")', timeout=10000)
    daily_frame.click('button:has-text("Continue")')
    print("[join_flow] Looking for 'Join without camera and mic' link...")
    # Try multiple ways to locate the anchor for robustness
    link_locators = [
        "a.robots-btn-join.underline",
        "a:has-text('Join without camera and mic')",
        "text=Join without camera and mic",
    ]
    joined = False
    for link_sel in link_locators:
        try:
            daily_frame.wait_for_selector(link_sel, timeout=4000)
            daily_frame.click(link_sel)
            print(f"[join_flow] Clicked join link via selector: {link_sel}")
            joined = True
            break
        except Exception:
            continue

    # daily_frame.wait_for_selector('button:has-text("Continue")', timeout=10000)
    # daily_frame.click('button:has-text("Continue")')

    # daily_frame.wait_for_selector('button:has-text("Join")', timeout=10000)
    # daily_frame.click('button:has-text("Join")')