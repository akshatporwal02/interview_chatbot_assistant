import requests
import subprocess
import sys
import os
import time

DAILY_API_KEY = "73cdd4c6a7240308bdbe80621d62309d0cbada79ea4081fa1af29a0c12f6fadf"
DAILY_API_BASE = "https://api.daily.co/v1"
HEADERS = {"Authorization": f"Bearer {DAILY_API_KEY}"}


def get_all_rooms():
    url = f"{DAILY_API_BASE}/rooms"
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    return res.json().get("data", [])


def is_meeting_ongoing(room_name):
    """
    Return tri-state: 'bot_present', 'ongoing', 'idle'
    - Use presence to detect the Observer Bot accurately
    - Use meetings endpoint to know if the room is flagged as ongoing
    """
    # 1) Presence check for the bot
    presence_url = f"{DAILY_API_BASE}/rooms/{room_name}/presence"
    try:
        res = requests.get(presence_url, headers=HEADERS)
        res.raise_for_status()
        participants = res.json().get("data", [])
        for p in participants:
            name = (p.get("userName") or p.get("user_name") or p.get("name") or "").strip()
            if name == "Observer Bot":
                return "bot_present"
    except Exception as e:
        print(f"⚠️ Presence check failed for {room_name}: {e}")

    # 2) Meetings endpoint to know ongoing status
    try:
        url = f"{DAILY_API_BASE}/meetings"
        res = requests.get(url, headers=HEADERS)
        res.raise_for_status()
        meetings = res.json().get("data", [])
        for meeting in meetings:
            if meeting.get("room") == room_name and meeting.get("ongoing", False):
                return "ongoing"
    except Exception as e:
        print(f"⚠️ Meetings check failed for {room_name}: {e}")

    return "idle"


def launch_room_bot(room_url, room_name):
    if os.name == "nt":  # Windows
        subprocess.Popen(
            ["start", "cmd", "/k", "python", "main.py", room_url, room_name],
            shell=True
        )
    else:  # macOS / Linux
        subprocess.Popen(["gnome-terminal", "--", "python3", "main.py", room_url, room_name])


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