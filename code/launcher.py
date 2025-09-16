import requests
import subprocess
import sys
import os
import time
import threading

from utils.api_utils import get_daily_headers, list_rooms, is_meeting_ongoing as api_is_meeting_ongoing
from utils.env_utils import load_dotenv, get_daily_api_key

load_dotenv()
DAILY_API_KEY = get_daily_api_key()
HEADERS = get_daily_headers(DAILY_API_KEY) if DAILY_API_KEY else {}


def get_all_rooms():
    return list_rooms(HEADERS)


def is_meeting_ongoing(room_name):
    return api_is_meeting_ongoing(room_name, HEADERS)


def _stream_process_output(proc: subprocess.Popen, room_name: str):
    try:
        if proc.stdout is not None:
            for line in iter(proc.stdout.readline, ''):
                if not line:
                    break
                print(f"[BOT-{room_name}] {line.rstrip()}")
        proc.wait()
        print(f" [BOT-{room_name}] exited with code {proc.returncode}")
    except Exception as e:
        print(f" [BOT-{room_name}] log stream error: {e}")


def launch_room_bot(room_url, room_name):
    if os.name == "nt":  # Windows
        subprocess.Popen(
            ["start","/MIN", "cmd", "/c", "python", "main.py", room_url, room_name],
            shell=True
        )
    else:  # macOS / Linux / Containers
        # In Docker containers, terminal emulators like gnome-terminal are not available.
        # Launch the bot process directly using the current Python interpreter and keep container alive.
        python_exec = sys.executable or "python3"
        main_path = os.path.join(os.path.dirname(__file__), "main.py")

        print(f" Launching subprocess: {python_exec} {main_path} {room_url} {room_name}")
        process = subprocess.Popen(
            [python_exec, "-u", main_path, room_url, room_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=os.path.dirname(__file__)
        )
        print(f" Started subprocess with PID: {process.pid}")
        t = threading.Thread(target=_stream_process_output, args=(process, room_name), daemon=True)
        t.start()
        return process, t


if __name__ == "__main__":
    rooms = get_all_rooms()
    if not rooms:
        print(" No rooms found.")
        sys.exit(1)

    now = int(time.time())
    eligible_rooms = []  # Store only after checks

    print("\n Checking room conditions...\n")
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
                    print(f" {room_name} not started yet (nbf={nbf_secs}, now={now}) → Skipping")
                    continue
            except (ValueError, TypeError):
                print(f" {room_name} has non-numeric nbf={nbf_raw}; proceeding without nbf check")

        # Condition 2: skip if meeting ongoing or bot already inside
        meet_status = is_meeting_ongoing(room_name)
        if meet_status == "bot_present":
            print(f" {room_name} → Bot already present, skipping")
            continue
        elif meet_status == "ongoing":
            print(f" {room_name} → Meeting ongoing, proceeding to join")
            # Do not skip; we want the bot to join ongoing meetings if it's not already inside

        # Passed all checks → eligible
        print(f" {room_name} → Eligible")
        eligible_rooms.append((room_url, room_name))

    # After all checks done → only now launch bots
    print("\n Launching eligible bots...\n")
    processes = []
    for room_url, room_name in eligible_rooms:
        print(f" Opening terminal for: {room_name}")
        result = launch_room_bot(room_url, room_name)
        if result:
            processes.append(result)

    print("\n Waiting for all bot processes to complete...\n")
    # Wait for all processes to exit to keep container alive
    for proc, thread in processes:
        try:
            proc.wait()
            if thread.is_alive():
                thread.join(timeout=2)
        except Exception:
            pass

    print("\n Finished launching all eligible bots.")