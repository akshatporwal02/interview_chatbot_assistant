from playwright.sync_api import Page
import time

def pin_participant(daily_frame, exclude_names=None):
    """
    Pins the first eligible participant in the Daily call.
    Excludes Observer Bot and concret.io by default.
    """
    if exclude_names is None:
        exclude_names = ["Observer Bot", "concret.io"]

    try:
        # Step 1: Click People button
        people_button = daily_frame.query_selector("#people-controls")
        if people_button:
            people_button.click()
            time.sleep(1)
            print("✅ Opened People tab")
        else:
            print("⚠️ People button not found")
            return False

        # Step 2: Get participant list
        people_list = daily_frame.query_selector_all("div.jsx-d777fa1387c7922c.row")
        if not people_list:
            print("⚠️ No participants found in people list")
            return False

        for person in people_list:
            name_el = person.query_selector(".participant-name-container p")
            if not name_el:
                continue

            name = name_el.inner_text().strip()
            if any(ex.lower() in name.lower() for ex in exclude_names):
                continue

            # Step 3: Open 3-dots menu
            dots_btn = person.query_selector("button[id*='actions-btn']")
            if dots_btn:
                dots_btn.click()
                time.sleep(0.5)

                # Step 4: Click "Pin"
                pin_option = daily_frame.query_selector("button[id*='participant-menu-pin-participant']")
                if pin_option:
                    pin_option.click()
                    print(f"📌 Pinned participant: {name}")
                    return True
                else:
                    print("⚠️ Pin option not found")
            else:
                print(f"⚠️ Options menu not found for {name}")

        print("⚠️ No eligible participant found to pin")
        return False

    except Exception as e:
        print(f"❌ Error in pin_participant: {e}")
        return False
