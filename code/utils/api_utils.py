import requests
from typing import Literal, Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
import time

DAILY_API_BASE = "https://api.daily.co/v1"


def get_daily_headers(api_key: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def http_get(url: str, headers: Dict[str, str], stream: bool = False):
    return requests.get(url, headers=headers, stream=stream)


def http_post(url: str, headers: Dict[str, str], json: Optional[Dict[str, Any]] = None):
    return requests.post(url, headers=headers, json=json)


def list_rooms(headers: Dict[str, str]) -> List[Dict[str, Any]]:
    url = f"{DAILY_API_BASE}/rooms"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return res.json().get("data", [])


def get_room_presence(room_name: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
    url = f"{DAILY_API_BASE}/rooms/{room_name}/presence"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return res.json().get("data", [])


def list_meetings(headers: Dict[str, str]) -> List[Dict[str, Any]]:
    url = f"{DAILY_API_BASE}/meetings"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return res.json().get("data", [])


def is_meeting_ongoing(room_name: str, headers: Dict[str, str]) -> Literal["bot_present", "ongoing", "idle"]:
    # Presence
    try:
        participants = get_room_presence(room_name, headers)
        for p in participants:
            name = (p.get("userName") or p.get("user_name") or p.get("name") or "").strip()
            if name == "Strata(Bot)":
                return "bot_present"
    except Exception:
        pass

    # Meetings
    try:
        meetings = list_meetings(headers)
        for m in meetings:
            if m.get("room") == room_name and m.get("ongoing", False):
                return "ongoing"
    except Exception:
        pass

    return "idle"


def list_recordings(headers: Dict[str, str]) -> List[Dict[str, Any]]:
    url = f"{DAILY_API_BASE}/recordings"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return res.json().get("data", [])


def get_latest_recording_for_room(room_name: str, headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    try:
        recs = list_recordings(headers)
        matches = [r for r in recs if r.get("room_name") == room_name]
        if not matches:
            return None
        latest = sorted(matches, key=lambda r: r.get("created_at", ""), reverse=True)[0]
        return latest
    except Exception:
        return None


def get_recording_access_link(recording_id: str, headers: Dict[str, str]) -> Optional[str]:
    url = f"{DAILY_API_BASE}/recordings/{recording_id}/access-link"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    data = res.json()
    return data.get("download_link") or data.get("url")


# ---- Additional helpers ported from main.py (no behavior change) ----

def get_next_daily_meeting(headers: Dict[str, str]) -> Tuple[Optional[datetime], Optional[str]]:
    url = f"{DAILY_API_BASE}/rooms"
    res = requests.get(url, headers=headers)
    rooms = res.json().get("data", [])
    if not rooms:
        return None, None
    rooms.sort(key=lambda r: r.get("config", {}).get("nbf", 0))
    next_room = rooms[1]
    meeting_time = datetime.fromtimestamp(next_room["config"].get("nbf", time.time()), tz=timezone.utc)
    return meeting_time, next_room["url"]


def get_active_participants(room_name: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
    url = f"{DAILY_API_BASE}/rooms/{room_name}/presence"
    try:
        res = requests.get(url, headers=headers)
        data = res.json().get("data", [])
        filtered = [p for p in data if p.get("userName") not in ["Strata(Bot)"]]
        return filtered
    except Exception:
        return []


def get_meeting_details(room_name: str, headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    url = f"{DAILY_API_BASE}/meetings"
    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        meetings = res.json().get("data", [])
        for meeting in meetings:
            if meeting.get("room") == room_name:
                return {
                    "id": meeting.get("id"),
                    "room": meeting.get("room"),
                    "start_time": meeting.get("start_time"),
                    "duration": meeting.get("duration"),
                }
        return None
    except Exception:
        return None