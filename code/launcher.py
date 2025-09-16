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
    if os.name == "nt":  # Windows
        subprocess.Popen(
            ["start","/MIN", "cmd", "/c", "python", "main.py", room_url, room_name],
            shell=True
        )
    else:  # macOS / Linux / Containers
        # In Docker containers, terminal emulators like gnome-terminal are not available.
        # Launch the bot process directly using the current Python interpreter.
        python_exec = sys.executable or "python3"
        # Ensure we reference the correct path to main.py from project root in container
        main_path = os.path.join(os.path.dirname(__file__), "main.py")
        
        print(f"🚀 Launching subprocess: {python_exec} {main_path} {room_url} {room_name}")
        
        try:
            # Use subprocess.Popen with stdout/stderr streaming to parent terminal
            # This allows all subprocess logs to appear in Northflank terminal
            process = subprocess.Popen(
                [python_exec, main_path, room_url, room_name],
                stdout=None,  # Inherit parent's stdout (Northflank terminal)
                stderr=None,  # Inherit parent's stderr (Northflank terminal)
                cwd=os.path.dirname(__file__)  # Set working directory to code folder
            )
            
            print(f"✅ Started subprocess with PID: {process.pid}")
            print(f"📺 All subprocess logs will stream to this terminal")
            
            # Optional: Wait a moment to check if process starts successfully
            time.sleep(2)
            if process.poll() is None:
                print(f"✅ Process {process.pid} is running and streaming logs")
            else:
                print(f"❌ Process {process.pid} exited with code {process.returncode}")
                    
        except Exception as e:
            print(f"❌ Failed to launch subprocess: {e}")
            import traceback
            traceback.print_exc()


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