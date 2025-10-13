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
    # Standardize downloads directory under project_root/session_data to align with writers/readers
    # __file__ is /app/code/utils/media_utils.py → parents[2] is /app
    project_root = Path(__file__).resolve().parents[2]
    downloads_dir = project_root / "session_data" / "recordings"
    video_path = None

    deadline = time.time() + poll_total_secs
    attempt = 0
    last_seen_id = None

    print(f"[recording] Polling for latest recording for room='{room_name}' up to {poll_total_secs}s (interval={poll_interval_secs}s)...")
    while time.time() < deadline:
        attempt += 1
        try:
            rec = get_latest_recording_for_room(room_name, headers)
        except Exception as e:
            print(f"[recording] Attempt {attempt}: failed to list recordings: {e}")
            rec = None

        if rec:
            rec_id = rec.get("id")
            print(f"[recording] Attempt {attempt}: found recording id={rec_id}")
            if rec_id and rec_id != last_seen_id:
                try:
                    link = get_recording_access_link(rec_id, headers)
                    print(f"[recording] Attempt {attempt}: access link resolved? {'yes' if link else 'no'}")
                    if link:
                        ext = ".mp4"
                        if ".webm" in link.lower():
                            ext = ".webm"
                        video_path = downloads_dir / f"{room_name}_{rec_id}{ext}"
                        print(f"[recording] Attempt {attempt}: downloading to {video_path} ...")
                        download_file(link, video_path)
                        print(f"[recording] Download complete: {video_path}")
                        break
                except Exception as dl_err:
                    # Do NOT suppress retries for the same recording ID; transient issues (e.g., permissions)
                    # may be resolved by subsequent attempts during the polling window.
                    print(f"[recording] Attempt {attempt}: download/access failed: {dl_err}")
                    # keep last_seen_id unchanged so we retry this rec_id on next loop
        else:
            print(f"[recording] Attempt {attempt}: no recording found yet. Waiting...")

        time.sleep(poll_interval_secs)

    if not video_path or not video_path.exists():
        print("[recording] No downloadable recording became available within the polling window.")
        return None

    audio_path = video_path.with_suffix(".wav")
    try:
        print(f"[recording] Extracting audio to {audio_path} via ffmpeg...")
        extract_audio_from_video(video_path, audio_path)
        print(f"[recording] Audio extracted: {audio_path}")
    except subprocess.CalledProcessError as ff_err:
        print(f"[recording] ffmpeg extraction failed: {ff_err}")
        return None

    return audio_path