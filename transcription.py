import requests
import os
import time
from pathlib import Path

DAILY_API_KEY = "73cdd4c6a7240308bdbe80621d62309d0cbada79ea4081fa1af29a0c12f6fadf"
DAILY_API_BASE = "https://api.daily.co/v1"
TRANSCRIPT_DIR = Path("transcripts_doc")

HEADERS = {
    "Authorization": f"Bearer {DAILY_API_KEY}",
    "Content-Type": "application/json"
}


def start_transcription(room_name):
    url = f"{DAILY_API_BASE}/rooms/{room_name}/transcription/start"
    try:
        res = requests.post(url, headers=HEADERS)
        if res.status_code == 200:
            print(f"✅ Transcription started for room: {room_name}")
        else:
            print(f"❌ Failed to start transcription: {res.text}")
    except Exception as e:
        print(f"❌ Exception while starting transcription: {e}")


def stop_transcription(room_name):
    url = f"{DAILY_API_BASE}/rooms/{room_name}/transcription/stop"
    try:
        res = requests.post(url, headers=HEADERS)
        if res.status_code == 200:
            print(f"✅ Transcription stopped for room: {room_name}")
        else:
            print(f"❌ Failed to stop transcription: {res.text}")
    except Exception as e:
        print(f"❌ Exception while stopping transcription: {e}")


def fetch_transcript_id_for_room(room_name):
    url = f"{DAILY_API_BASE}/transcript/"
    try:
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            data = res.json()
            transcripts = data.get("data", [])
            for transcript in transcripts:
                if transcript.get("roomName") == room_name:
                    return transcript.get("transcriptId")
            print(f"⚠️ No transcript found for room: {room_name}")
        else:
            print(f"❌ Failed to fetch transcripts: {res.text}")
    except Exception as e:
        print(f"❌ Exception while fetching transcripts: {e}")
    return None


def download_transcript(transcript_id):
    link_url = f"{DAILY_API_BASE}/transcript/{transcript_id}/access-link"
    try:
        link_res = requests.get(link_url, headers=HEADERS)
        if link_res.status_code == 200:
            access_url = link_res.json().get("link")
            if access_url:
                TRANSCRIPT_DIR.mkdir(exist_ok=True)
                filename = TRANSCRIPT_DIR / f"{transcript_id}.txt"
                file_res = requests.get(access_url)
                with open(filename, "wb") as f:
                    f.write(file_res.content)
                print(f"📥 Transcript downloaded: {filename.resolve()}")
                return file_res.text
            else:
                print("❌ Access link not found in response.")
        else:
            print(f"❌ Failed to get access link: {link_res.text}")
    except Exception as e:
        print(f"❌ Exception while downloading transcript: {e}")