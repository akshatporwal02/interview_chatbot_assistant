import time
import queue
import cv2
import numpy as np
import pytz
import yaml
import sys
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright
import requests
from urllib.parse import urlparse
from screenshot_capture import ViolationCapturer
from detection.face_detection import FaceDetector
from detection.eye_tracking import EyeTracker
from detection.mouth_detection import MouthMonitor
from detection.multi_face import MultiFaceDetector
from detection.object_detection import ObjectDetector
from audio_detection import AudioMonitor
from report_generation.report_generator import ReportGenerator
from services.alerts import AlertLog
from report_generation.score_evaluator import analyze_transcript, parse_llm_response
from services.send_message import send_email_with_attachments
from pathlib import Path
import subprocess
import os
from utils.api_utils import (
    # get_next_daily_meeting as api_get_next_daily_meeting,
    get_active_participants as api_get_active_participants,
    get_meeting_details as api_get_meeting_details,
)
# centralized utils (lift-and-shift, same behavior)
from utils.time_utils import utc_to_ist
from utils.api_utils import (
    get_daily_headers,
    list_recordings as api_list_recordings,
    get_latest_recording_for_room as api_get_latest_recording_for_room,
    get_recording_access_link as api_get_recording_access_link,
)
from utils.media_utils import download_file as util_download_file, extract_audio_from_video as util_extract_audio_from_video

# =======================
#    CONFIG / CONSTANTS
# =======================
from utils.env_utils import load_dotenv, get_daily_api_key
load_dotenv()  # load .env at repo root if present
DAILY_API_KEY = get_daily_api_key()
DAILY_API_BASE = "https://api.daily.co/v1"
HEADERS = {"Authorization": f"Bearer {DAILY_API_KEY}"} if DAILY_API_KEY else {}

# How long to poll for the cloud recording to appear after leaving (seconds)
RECORDING_POLL_TOTAL_SECS = 180  # 3 minutes total
RECORDING_POLL_INTERVAL_SECS = 6  # check every 6s

# =======================
#     TIMEZONE HELPERS
# =======================
def utc_to_ist(utc_dt):
    ist = pytz.timezone("Asia/Kolkata")
    return utc_dt.astimezone(ist)

# =======================
#        LOGGER
# =======================
class AlertLogger:
    def __init__(self, chat_queue=None, capturer=None, violations_list=None, file_logger=None):
        self.chat_queue = chat_queue
        self.capturer = capturer
        self.violations_list = violations_list
        self.file_logger = file_logger

    def log_alert(self, alert_type, message, frame=None):
        alert_text = f"⚠️ {alert_type} {message}"
        print(alert_text)

        timestamp = datetime.now().strftime('%Y-%m-%d_%H:%M:%S')
        image_path = None

        if frame is not None and self.capturer:
            result = self.capturer.capture_violation(frame, alert_type, timestamp)
            image_path = result.get('image_path')

        if self.violations_list is not None:
            self.violations_list.append({
                'type': alert_type,
                'timestamp': timestamp,
                'message': message,
                'image_path': image_path
            })

        # Write to file using AlertLog
        if self.file_logger:
            self.file_logger.log_alert(alert_type, message)

        if self.chat_queue:
            self.chat_queue.put(alert_text)

# =======================
#   DAILY API HELPERS
# =======================

# def get_next_daily_meeting():
#     return api_get_next_daily_meeting(HEADERS)

def get_active_participants(room_name):
    try:
        return api_get_active_participants(room_name, HEADERS)
    except Exception as e:
        print(f"❌ Failed to fetch participant list: {e}")
        return []

def get_meeting_details(room_name):
    try:
        details = api_get_meeting_details(room_name, HEADERS)
        if not details:
            print(f"⚠️ No meeting found for room: {room_name}")
        return details
    except Exception as e:
        print(f"❌ Failed to fetch meeting details: {e}")
        return None

def list_recordings():
    """Return list of all recordings (Daily cloud)."""
    return api_list_recordings(HEADERS)

def get_latest_recording_for_room(room_name):
    """
    Return the most recent recording dict for a room (or None if not found).
    Recording fields we rely on: id, room_name, created_at
    """
    try:
        return api_get_latest_recording_for_room(room_name, HEADERS)
    except Exception as e:
        print(f"❌ Error listing recordings: {e}")
        return None

def get_recording_access_link(recording_id):
    """
    Get an access (download) link for a recording.
    Response may have 'download_link' or 'url' depending on account/config.
    """
    return api_get_recording_access_link(recording_id, HEADERS)

def download_file(url, dest_path: Path):
    """Stream download to dest_path."""
    return util_download_file(url, dest_path)

# =======================
#   MEDIA UTIL HELPERS
# =======================
def extract_audio_from_video(video_path: Path, audio_path: Path):
    """Extract PCM 16k mono WAV using ffmpeg."""
    return util_extract_audio_from_video(video_path, audio_path)

def fetch_cloud_recording_wav(room_name: str) -> Path | None:
    """
    Wait for Daily cloud recording for this room, then download and
    extract audio to WAV. Returns path to WAV, or None if unavailable.
    """
    downloads_dir = Path("session_data/recordings")
    video_path = None

    deadline = time.time() + RECORDING_POLL_TOTAL_SECS
    attempt = 0
    last_seen_id = None

    print(f"⏳ Waiting for Daily cloud recording for room '{room_name}' ...")
    while time.time() < deadline:
        attempt += 1
        rec = get_latest_recording_for_room(room_name)
        if rec:
            rec_id = rec.get("id")
            if rec_id and rec_id != last_seen_id:
                print(f"📦 Found recording candidate (attempt {attempt}): {rec_id}")
                try:
                    link = get_recording_access_link(rec_id)
                    if link:
                        ext = ".mp4"
                        if ".webm" in link.lower():
                            ext = ".webm"
                        video_path = downloads_dir / f"{room_name}_{rec_id}{ext}"
                        print(f"⬇️  Downloading recording from access link...")
                        download_file(link, video_path)
                        print(f"✅ Downloaded recording to {video_path}")
                        break
                except Exception as e:
                    print(f"⚠️ Access link not ready yet ({e}); retrying...")
                    last_seen_id = rec_id

        time.sleep(RECORDING_POLL_INTERVAL_SECS)

    if not video_path or not video_path.exists():
        print("❌ Could not obtain cloud recording file.")
        return None

    audio_path = video_path.with_suffix(".wav")
    try:
        extract_audio_from_video(video_path, audio_path)
    except subprocess.CalledProcessError as e:
        print(f"❌ ffmpeg failed to extract audio: {e}")
        return None

    return audio_path

# =======================
#   JOIN & MONITOR FLOW
# =======================
def join_daily(meeting_time_utc, meeting_url):
    now_utc = datetime.now(timezone.utc)
    wait_seconds = (meeting_time_utc - now_utc).total_seconds()
    if wait_seconds > 0:
        print(f"⏳ Waiting {int(wait_seconds)} seconds...")
        time.sleep(wait_seconds)

    meeting_time_ist = utc_to_ist(meeting_time_utc)
    room_name = urlparse(meeting_url).path.lstrip("/")
    meeting_info = None

    print(f"🗕️ Meeting Scheduled IST: {meeting_time_ist.strftime('%Y-%m-%d %H:%M:%S')}")

    session_ts_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # No need for accept_downloads (we are not saving browser downloads)
        context = browser.new_context(permissions=["camera", "microphone", "midi", "midi-sysex"])
        page = context.new_page()

        vercel_ui_url = "https://concretiomeet.vercel.app/"
        page.goto(vercel_ui_url)
        print("✅ Opened custom Vercel-hosted UI")
        project_root = Path(__file__).resolve().parents[1]  # goes from src/ to repo root
        config_path = project_root / "config" / "config.yaml"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        audio_monitor = AudioMonitor(config, room_name, session_ts_str)

        try:
            page.wait_for_selector('input[placeholder*="Enter room name"]', timeout=10000)
            page.fill('input[placeholder*="Enter room name"]', meeting_url)
            print("✅ Filled Daily URL")

            page.click('button:has-text("Join Room")')
            print("✅ Clicked Join Room")

            page.wait_for_timeout(5000)
            page.wait_for_selector("iframe", timeout=10000)

            iframe_element = page.query_selector("iframe")
            frame = iframe_element.content_frame()

            frame.wait_for_selector("input#username", timeout=10000)
            frame.fill("input#username", "Observer Bot")
            print("✅ Filled name inside iframe")

            frame.wait_for_selector('button:has-text("Continue")', timeout=10000)
            frame.click('button:has-text("Continue")')
            print("✅ Clicked Continue")

            frame.wait_for_selector('button:has-text("Join")', timeout=10000)
            frame.click('button:has-text("Join")')
            print("✅ Clicked Join inside Daily iframe")

            try:
                frame.wait_for_selector('#btn-leave', timeout=15000)
                print('✅ Detected in-call UI; recording controls available')
            except Exception:
                print('⚠️ Could not confirm in-call UI; proceeding')

            # Try to start cloud recording via UI so Daily stores it in cloud
            try:
                rec_btn = frame.query_selector('#record-controls')
                print(f"Recording button found: {rec_btn}")
                if rec_btn and rec_btn.is_enabled():
                    rec_btn.click()
                    print('⏺️ In-call UI recording button pressed')
                    start_btn = frame.wait_for_selector('button:has-text("Start recording")', timeout=5000)
                    if start_btn and start_btn.is_enabled():
                        start_btn.click()
                        print('▶️ "Start recording" confirmation button pressed (cloud)')
                    else:
                        print('⚠️ "Start recording" button not found or not enabled')
            except Exception as e:
                print(f'⚠️ Could not click in-call recording button: {e}')

            print("🕒 Staying in the meeting for monitoring...")

        except Exception as e:
            print(f"⚠️ Failed to interact with UI: {e}")
            return

        # ✅ STEP 4: Monitoring Begins
        chat_queue = queue.Queue()
        violations = []
        capturer = ViolationCapturer(config)
        logging = AlertLog(config, room_name)
        logger = AlertLogger(chat_queue, capturer, violations, logging)

        face = FaceDetector(config);        face.set_alert_logger(logger)
        eye = EyeTracker(config);           eye.set_alert_logger(logger)
        mouth = MouthMonitor(config);       mouth.set_alert_logger(logger)
        multi = MultiFaceDetector(config);  multi.set_alert_logger(logger)
        objects = ObjectDetector(config);   objects.set_alert_logger(logger)
        audio_monitor.set_alert_logger(logger)

        start_time = time.time()
        max_duration = 3600
        meeting_participants = []
        last_participant_check = 0
        everyone_left_time = None
        wait_duration = 10  # seconds after everyone leaves

        iframe_element = page.query_selector("iframe")
        daily_frame = iframe_element.content_frame() if iframe_element else None

        detection_active = True

        while time.time() - start_time < max_duration:
            try:
                current_participants = get_active_participants(room_name)
                if current_participants:
                    if not detection_active:
                        detection_active = True
                        print("🔄 Detection RESUMED - Participants joined the meeting")

                    current_time = time.time()
                    if current_time - last_participant_check >= 30:
                        last_participant_check = current_time
                        for participant in current_participants:
                            participant_name = participant.get("userName", "Unknown")
                            if not any(p.get("userName") == participant_name for p in meeting_participants):
                                meeting_participants.append(participant)
                                print(f"📝 Recorded participant: {participant_name}")
                else:
                    if detection_active:
                        detection_active = False
                        print("⏸️ Detection PAUSED - No participants in the meeting")

                screenshot = page.screenshot(full_page=False)
                cv_frame = cv2.imdecode(np.frombuffer(screenshot, np.uint8), cv2.IMREAD_COLOR)
                if cv_frame is not None:
                    face.detect_face(cv_frame)
                    eye.track_eyes(cv_frame)
                    mouth.monitor_mouth(cv_frame)
                    multi.detect_multiple_faces(cv_frame)
                    objects.detect_objects(cv_frame, visualize=True)

                if daily_frame:
                    try:
                        chat_button = daily_frame.query_selector("#chat-controls")
                        if chat_button:
                            is_expanded = chat_button.get_attribute("aria-expanded")
                            if is_expanded == "false":
                                chat_button.click()
                                time.sleep(1)
                    except Exception as e:
                        print(f"⚠️ Failed to open chat panel: {e}")

                while not chat_queue.empty():
                    msg = chat_queue.get()
                    if daily_frame:
                        try:
                            chat_input = daily_frame.query_selector("textarea")
                            if chat_input:
                                chat_input.fill(msg)
                                chat_input.press("Enter")
                                print(f"📤 Alert sent: {msg}")
                        except Exception as e:
                            print(f"Chat error: {e}")
                    else:
                        print(f"⚠️ Cannot send message - iframe not available: {msg}")

                current_participants_for_leaving = get_active_participants(room_name)
                if not current_participants_for_leaving:
                    if everyone_left_time is None:
                        everyone_left_time = time.time()
                        print("👋 All participants have left. Waiting 1 minute before leaving...")
                    else:
                        wait_elapsed = time.time() - everyone_left_time
                        remaining_wait = wait_duration - wait_elapsed
                        if remaining_wait > 0:
                            print(f"⏳ Waiting {int(remaining_wait)} more seconds before leaving...")
                        else:
                            print("⏰ 1 minute wait completed. Leaving the meeting...")
                            meeting_info = get_meeting_details(room_name)
                            if meeting_info:
                                start_utc = datetime.fromtimestamp(meeting_info["start_time"], tz=timezone.utc)
                                meeting_info["start_time_ist"] = utc_to_ist(start_utc).strftime('%Y-%m-%d %H:%M:%S')
                                if meeting_info.get("duration") and meeting_info.get("start_time"):
                                    end_utc = datetime.fromtimestamp(meeting_info["start_time"] + meeting_info["duration"], tz=timezone.utc)
                                    meeting_info["end_time_ist"] = utc_to_ist(end_utc).strftime('%Y-%m-%d %H:%M:%S')
                                print(f"📋 Final Meeting Info with Duration: {meeting_info}")
                            else:
                                print("⚠️ Could not fetch final meeting info.")

                            time.sleep(2)
                            if daily_frame:
                                try:
                                    # Open stop recording menu
                                    rec_btn = daily_frame.query_selector('#record-controls')
                                    if rec_btn and rec_btn.is_enabled():
                                        rec_btn.click()
                                        print("⏹️ In-call UI recording button pressed to open stop menu")
                                        stop_btn = daily_frame.wait_for_selector('button:has-text("Stop recording")', timeout=5000)
                                        if stop_btn and stop_btn.is_enabled():
                                            stop_btn.click()
                                            print('🛑 "Stop recording" confirmation button pressed (cloud)')
                                            # No browser download expected — cloud handles it
                                        else:
                                            print('⚠️ "Stop recording" button not found or not enabled')
                                    else:
                                        print("⚠️ Recording button not found or not enabled.")

                                    leave_button = daily_frame.query_selector("#btn-leave")
                                    if leave_button:
                                        leave_button.click()
                                        print("✅ Bot left the meeting after 1-minute wait.")
                                    else:
                                        print("⚠️ Leave button not found.")
                                except Exception as e:
                                    print(f"⚠️ Failed to click stop/leave: {e}")
                            break
                else:
                    if everyone_left_time is not None:
                        everyone_left_time = None
                        print("🔄 Someone rejoined during waiting period - cancelling leave timer")

                time.sleep(2)
            except Exception as e:
                print(f"[ERROR] {e}")
                break

        page.wait_for_timeout(2000)
        browser.close()

        # ============================================
        #   FETCH CLOUD RECORDING → EXTRACT → TRANSCRIBE
        # ============================================
        transcript_text = None

        print("📥 Fetching cloud recording & extracting audio...")
        wav_path = fetch_cloud_recording_wav(room_name)

        if wav_path and wav_path.exists():
            print(f"📝 Transcribing audio from {wav_path} using faster-whisper via AudioMonitor...")
            # Reuse your AudioMonitor to keep a single implementation
            audio_monitor.audio_file = str(wav_path)
            transcript_text = audio_monitor.get_transcript_text()
            # print(f"🗒️ Transcript excerpt: {transcript_text[:200]}...")
        else:
            print(f"❌ Could not fetch or process cloud recording for room: {room_name}")

        # ==========================
        #   Transcript + LLM Analysis
        # ==========================
        print("🤖 Analyzing transcript with LLM...")
        llm_analysis = analyze_transcript(room_name)
        print("✅ LLM analysis complete.")

        candidate_analysis, interviewer_analysis, decision = parse_llm_response(llm_analysis)

        # ==========================
        #   Reporting
        # ==========================
        if meeting_participants:
            print(f"📊 Generating reports for {len(meeting_participants)} participant(s)")
            for person in meeting_participants:
                username = person.get("userName", "Unknown")
                if username.strip().lower() == "concret.io":
                    continue

                student = {
                    'id': person.get("id") or datetime.now().strftime('%Y%m%d%H%M%S'),
                    'name': person.get("userName", "Unknown"),
                    'email': f'{person.get("userName", "unknown").lower().replace(" ", "")}@example.com'
                }

                report_gen = ReportGenerator(config)

                # Ensure meeting_info carries room + session for consistent naming
                meeting_info = meeting_info or {}
                meeting_info.setdefault('room_name', room_name)
                meeting_info.setdefault('session_timestamp', session_ts_str)

                report_path = report_gen.generate_report(
                    student,
                    violations,
                    candidate_analysis=candidate_analysis,
                    interviewer_analysis=interviewer_analysis,
                    decision=decision,
                    transcript_text=llm_analysis,
                    meeting_info=meeting_info
                )

                if report_path:
                    print(f"📄 Report saved for {student['name']}: {report_path}")
                    # try:
                    #     send_email_with_attachments(
                    #       report_path=report_path,
                    #       student_name=student['name'],
                    #       receiver_email='m.gupta@concret.io',
                    #       room_name=room_name
                    #       )
                    # except Exception as e:
                    #       print(f"❌ Failed to send email for {student['name']}: {e}")

                else:
                    print(f"❌ Report generation failed for {student['name']}")

        else:
            print("⚠️ No participants found, generating default report")
            student = {
                'id': datetime.now().strftime('%Y%m%d%H%M%S'),
                'name': 'Unknown Participant',
                'email': 'unknown@example.com'
            }

            # Ensure status and evaluation show for no-participant sessions
            if not candidate_analysis:
                candidate_analysis = [
                    {"criteria": "Communication Skills", "value": "N/A", "score": None, "explanation": ""},
                    {"criteria": "Technical Skills", "value": "N/A", "score": None, "explanation": ""},
                    {"criteria": "Attitude", "value": "N/A", "score": None, "explanation": ""},
                    {"criteria": "Overall Remark", "value": "N/A", "score": None, "explanation": ""},
                ]
            if not interviewer_analysis:
                interviewer_analysis = [
                    {"aspect": "Questions Asked", "value": "N/A", "description": ""},
                    {"aspect": "Difficulty Level", "value": "N/A", "description": ""},
                    {"aspect": "Attitude", "value": "N/A", "description": ""},
                ]
            if not decision or not decision.get("recommendation"):
                decision = {"recommendation": "No Show", "summary": "No participants joined the session."}

            report_gen = ReportGenerator(config)

            # Ensure meeting_info carries room + session for consistent naming
            meeting_info = meeting_info or {}
            meeting_info.setdefault('room_name', room_name)
            meeting_info.setdefault('session_timestamp', session_ts_str)

            report_path = report_gen.generate_report(
                student,
                violations,
                candidate_analysis=candidate_analysis,
                interviewer_analysis=interviewer_analysis,
                decision=decision,
                transcript_text=llm_analysis,
                meeting_info=meeting_info
            )
            if report_path:
                print(f"📄 Default report saved: {report_path}")
                # try:
                #     send_email_with_attachments(
                #           report_path=report_path,
                #           student_name=student['name'],
                #           receiver_email='m.gupta@concret.io',
                #           room_name=room_name
                #           )
                # except Exception as e:
                #           print(f"❌ Failed to send email for {student['name']}: {e}")

            else:
                print("❌ Default report generation failed")

# =======================
#           MAIN
# =======================
if __name__ == "__main__":
    # t, url = get_next_daily_meeting()
    # if t and url:
    #     join_daily(t, url)
    # else:
    #     print("❌ No Daily.co meeting found.")
    if len(sys.argv) >= 3:
        url = sys.argv[1]
        room_name = sys.argv[2]
        meeting_time_utc = datetime.now(timezone.utc)  # assume join now
        join_daily(meeting_time_utc, url)
    else:
        print("❌ Please provide room URL and name as arguments.")
