from pathlib import Path
import subprocess
import requests
import time
from typing import Optional

from .api_utils import get_recording_access_link, get_latest_recording_for_room


def download_file(url: str, dest_path: Path) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def extract_audio_from_video(video_path: Path, audio_path: Path) -> None:
    command = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(audio_path)
    ]
    subprocess.run(command, check=True)


def fetch_cloud_recording_wav(room_name: str, headers: dict, poll_total_secs: int, poll_interval_secs: int) -> Optional[Path]:
    downloads_dir = Path("session_data/recordings")
    video_path = None

    deadline = time.time() + poll_total_secs
    attempt = 0
    last_seen_id = None

    while time.time() < deadline:
        attempt += 1
        rec = get_latest_recording_for_room(room_name, headers)
        if rec:
            rec_id = rec.get("id")
            if rec_id and rec_id != last_seen_id:
                try:
                    link = get_recording_access_link(rec_id, headers)
                    if link:
                        ext = ".mp4"
                        if ".webm" in link.lower():
                            ext = ".webm"
                        video_path = downloads_dir / f"{room_name}_{rec_id}{ext}"
                        download_file(link, video_path)
                        break
                except Exception:
                    last_seen_id = rec_id
        time.sleep(poll_interval_secs)

    if not video_path or not video_path.exists():
        return None

    audio_path = video_path.with_suffix(".wav")
    try:
        extract_audio_from_video(video_path, audio_path)
    except subprocess.CalledProcessError:
        return None

    return audio_path