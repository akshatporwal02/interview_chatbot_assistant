from datetime import datetime
import pytz


def utc_to_ist(utc_dt):
    ist = pytz.timezone("Asia/Kolkata")
    return utc_dt.astimezone(ist)


def now_timestamp_readable() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H:%M:%S")


def now_timestamp_filename() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def ensure_windows_safe_filename(s: str) -> str:
    return s.replace(":", "-").replace("/", "_").replace("\\", "_")