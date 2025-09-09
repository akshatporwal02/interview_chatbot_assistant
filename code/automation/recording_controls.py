from typing import Optional
from playwright.sync_api import Frame


def start_recording_if_possible(daily_frame: Frame) -> None:
    try:
        rec_btn = daily_frame.query_selector('#record-controls')
        if rec_btn and rec_btn.is_enabled():
            rec_btn.click()
            start_btn = daily_frame.wait_for_selector('button:has-text("Start recording")', timeout=5000)
            if start_btn and start_btn.is_enabled():
                start_btn.click()
    except Exception as e:
        print(f"⚠️ Could not start recording: {e}")


def stop_recording_and_leave(daily_frame: Frame) -> None:
    try:
        rec_btn = daily_frame.query_selector('#record-controls')
        if rec_btn and rec_btn.is_enabled():
            rec_btn.click()
            stop_btn = daily_frame.wait_for_selector('button:has-text("Stop recording")', timeout=5000)
            if stop_btn and stop_btn.is_enabled():
                stop_btn.click()
        leave_button = daily_frame.query_selector("#btn-leave")
        if leave_button:
            leave_button.click()
    except Exception as e:
        print(f"⚠️ Could not stop recording/leave: {e}")