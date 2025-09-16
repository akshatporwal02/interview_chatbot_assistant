import requests
import subprocess
import sys
import os
import time

from utils.api_utils import get_daily_headers, list_rooms, is_meeting_ongoing as api_is_meeting_ongoing
from utils.env_utils import load_dotenv, get_daily_api_key

load_dotenv()
DAILY_API_KEY = get_daily_api_key()
HEADERS = get_daily_headers(DAILY_API_KEY) if DAILY_API_KEY else {}


def get_all_rooms():
    return list_rooms(HEADERS)


def is_meeting_ongoing(room_name):
    return api_is_meeting_ongoing(room_name, HEADERS)


def launch_room_bot(room_url, room_name):
    # Sanitize room_name to create a valid tmux session name
    session_name = "".join(c for c in room_name if c.isalnum() or c in ('-', '_')).rstrip()

    if os.name == "nt":  # Windows (for local development)
        print(f"(Windows) Launching bot for {room_name} in a new terminal...")
        subprocess.Popen(
            ["start", "/MIN", "cmd", "/c", "python", "code/main.py", room_url, room_name],
            shell=True
        )
    else:  # Docker/Linux environment
        print(f"(Linux/Docker) Launching bot for {room_name} in a new tmux session '{session_name}'...")
        command = [
            "tmux", "new-session", "-d", "-s", session_name,
            "python3", "code/main.py", room_url, room_name
        ]
        subprocess.Popen(command)


if __name__ == "__main__":
    rooms = get_all_rooms()
    if not rooms:
        print("❌ No rooms found.")
        sys.exit(1)

    now = int(time.time())
    eligible_rooms = []  # ✅ Store only after checks

    print("\n📋 Checking room conditions...\n")
    for room in rooms:
        room_url = room["url"]
        room_name = room["name"]

        # Fetch not-before and normalize to epoch seconds (supports ms or nested placement)
        nbf_raw = room.get("nbf") or (room.get("config", {}) or {}).get("nbf")
        if nbf_raw is not None:
            try:
                nbf_int = int(nbf_raw)
                # Heuristic: values > 10^12 are likely in milliseconds
                nbf_secs = nbf_int // 1000 if nbf_int > 10**12 else nbf_int
                if now < nbf_secs:
                    print(f"⏳ {room_name} not started yet (nbf={nbf_secs}, now={now}) → Skipping")
                    continue
            except (ValueError, TypeError):
                print(f"⚠️ {room_name} has non-numeric nbf={nbf_raw}; proceeding without nbf check")

        # Condition 2: skip if meeting ongoing or bot already inside
        meet_status = is_meeting_ongoing(room_name)
        if meet_status == "bot_present":
            print(f"⚠️ {room_name} → Bot already present, skipping")
            continue
        elif meet_status == "ongoing":
            print(f"ℹ️ {room_name} → Meeting ongoing, proceeding to join")
            # Do not skip; we want the bot to join ongoing meetings if it's not already inside

        # Passed all checks → eligible
        print(f"✅ {room_name} → Eligible")
        eligible_rooms.append((room_url, room_name))

    # ✅ After all checks done → only now launch bots
    print("\n🚀 Launching eligible bots...\n")
    for room_url, room_name in eligible_rooms:
        print(f"🔹 Opening terminal for: {room_name}")
        launch_room_bot(room_url, room_name)

    print("\n✅ Finished launching all eligible bots.")