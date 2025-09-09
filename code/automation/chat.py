import time
from typing import Optional
from playwright.sync_api import Frame


def ensure_chat_open(daily_frame: Frame) -> None:
    try:
        chat_button = daily_frame.query_selector("#chat-controls")
        if chat_button:
            is_expanded = chat_button.get_attribute("aria-expanded")
            if is_expanded == "false":
                chat_button.click()
                time.sleep(1)
    except Exception as e:
        print(f"⚠️ Failed to open chat panel: {e}")


def send_chat_message(daily_frame: Frame, message: str) -> bool:
    try:
        chat_input = daily_frame.query_selector("textarea")
        if chat_input:
            chat_input.fill(message)
            chat_input.press("Enter")
            return True
        return False
    except Exception as e:
        print(f"Chat error: {e}")
        return False