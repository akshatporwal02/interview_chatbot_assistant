import time
import queue
import cv2
import numpy as np
import pytz
import yaml
import sys
from datetime import datetime, timezone
from automation.browser_session import BrowserSession
from automation.navigation import open_ui_url, ensure_ui_ready, get_daily_frame, get_daily_iframe
from automation.join_flow import fill_room_and_join
from automation.recording_controls import start_recording_if_possible, stop_recording_and_leave
from automation.chat import ensure_chat_open, send_chat_message
from automation.screenshots import take_screenshot
from automation.participants import pin_participant
import requests
from urllib.parse import urlparse
from screenshot_capture import ViolationCapturer
from detection.face_detection import FaceDetector
from detection.eye_tracking import EyeTracker
from detection.multi_face import MultiFaceDetector
from detection.object_detection import ObjectDetector
from transcript_generator import AudioMonitor
from report_generation.report_generator import ReportGenerator
from services.alerts import AlertLogger
from report_generation.score_evaluator import analyze_transcript, parse_llm_response
from services.send_message import send_email_with_attachments
from pathlib import Path
import subprocess
import os
from utils.crop_ss import get_big_tile_crop
from utils.api_utils import (
    get_next_daily_meeting as api_get_next_daily_meeting,
    get_active_participants as api_get_active_participants,
    get_meeting_details as api_get_meeting_details,
)
from utils.time_utils import utc_to_ist
from utils.api_utils import (
    get_daily_headers,
    list_recordings as api_list_recordings,
    get_latest_recording_for_room as api_get_latest_recording_for_room,
    get_recording_access_link as api_get_recording_access_link,
)
from utils.media_utils import download_file as util_download_file, extract_audio_from_video as util_extract_audio_from_video, fetch_cloud_recording_wav as util_fetch_cloud_recording_wav

from utils.env_utils import load_dotenv, get_daily_api_key, get_email_default_receiver
from utils.terminal_log import init_terminal_logging
load_dotenv()
DAILY_API_KEY = get_daily_api_key()
DAILY_API_BASE = "https://api.daily.co/v1"
HEADERS = {"Authorization": f"Bearer {DAILY_API_KEY}"} if DAILY_API_KEY else {}

def utc_to_ist(utc_dt):
    ist = pytz.timezone("Asia/Kolkata")
    return utc_dt.astimezone(ist)

def get_next_daily_meeting():
    return api_get_next_daily_meeting(HEADERS)

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
    return api_list_recordings(HEADERS)

def get_latest_recording_for_room(room_name):
    try:
        return api_get_latest_recording_for_room(room_name, HEADERS)
    except Exception as e:
        print(f"❌ Error listing recordings: {e}")
        return None

def get_recording_access_link(recording_id):
    return api_get_recording_access_link(recording_id, HEADERS)

def download_file(url, dest_path: Path):
    return util_download_file(url, dest_path)

def extract_audio_from_video(video_path: Path, audio_path: Path):
    return util_extract_audio_from_video(video_path, audio_path)

def join_daily(meeting_time_utc, meeting_url):
    now_utc = datetime.now(timezone.utc)
    wait_seconds = (meeting_time_utc - now_utc).total_seconds()
    if wait_seconds > 0:
        print(f"⏳ Waiting {int(wait_seconds)} seconds...")
        time.sleep(wait_seconds)

    meeting_time_ist = utc_to_ist(meeting_time_utc)
    room_name = urlparse(meeting_url).path.lstrip("/")
    meeting_info = None

    print(f"🗕️ Meeting Scheduled IST: {meeting_time_ist.strftime('%Y-%m-%d %H:%M:%S')} | Room Name: {room_name}")

    session_ts_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    with BrowserSession(headless=True, permissions=["camera", "microphone", "midi", "midi-sysex"]) as session:
        page = session.page

        vercel_ui_url = "https://candidly.concret.io/"
        open_ui_url(page, vercel_ui_url)
        print("✅ Opened custom Vercel-hosted UI")
        project_root = Path(__file__).resolve().parents[1]
        config_path = project_root / "config" / "config.yaml"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        det_config_path = project_root / "code" / "detection" / "detection_config.yaml"
        try:
            with open(det_config_path, 'r', encoding='utf-8') as df:
                det_cfg = yaml.safe_load(df) or {}
                if 'detection' in det_cfg:
                    config['detection'] = det_cfg['detection']
        except FileNotFoundError:
            print("\u26a0\ufe0f detection_config.yaml not found, using detection config from config.yaml")

        audio_monitor = AudioMonitor(config, room_name, session_ts_str)

        try:
            ensure_ui_ready(page)
            # Pass None to avoid premature iframe resolution; join_flow will resolve it after confirm
            fill_room_and_join(page, None, meeting_url, username="Strata (Bot)")
            print("✅ Joined Daily room via automation module")
            join_time_ist = utc_to_ist(datetime.now(timezone.utc))
            print(f"🕒 Bot JOINED meeting at: {join_time_ist.strftime('%Y-%m-%d %H:%M:%S')} IST")

            frame = get_daily_frame(page)
            try:
                frame.wait_for_selector('#btn-leave', timeout=15000)
                print('✅ Detected in-call UI; recording controls available')
            except Exception:
                print('⚠️ Could not confirm in-call UI; proceeding')

            start_recording_if_possible(frame)
            print("🕒 Staying in the meeting for monitoring...")

        except Exception as e:
            print(f"⚠️ Failed to interact with UI: {e}")
            return

        chat_queue = queue.Queue()
        violations = []
        capturer = ViolationCapturer(config)
        logger = AlertLogger(config, room_name, chat_queue, capturer, violations)


        face = FaceDetector(config);        face.set_alert_logger(logger)
        eye = EyeTracker(config);           eye.set_alert_logger(logger)
        multi = MultiFaceDetector(config);  multi.set_alert_logger(logger)
        objects = ObjectDetector(config);   objects.set_alert_logger(logger)
        # audio_monitor.set_alert_logger(logger)

        start_time = time.time()
        max_duration = 7200
        meeting_participants = []
        last_participant_check = 0
        everyone_left_time = None
        wait_duration = 10

        iframe_element = get_daily_iframe(page)
        daily_frame = get_daily_frame(page) if iframe_element else None

        detection_active = True
        pinned_once = False

        while time.time() - start_time < max_duration:
            try:
                # Track if at least one candidate (not interviewer, not bot) is present this iteration
                candidate_present = False
                current_participants = get_active_participants(room_name)
                if current_participants:
                    # Minimal candidate presence check: exclude interviewer and bot (spaces ignored)
                    for _p in current_participants:
                        _name = (_p.get("userName") or "").strip().lower()
                        _name_ns = _name.replace(" ", "")
                        if _name == "concret.io":
                            continue
                        if ("strata" in _name_ns) and ("bot" in _name_ns):
                            continue
                        candidate_present = True
                        break

                    if candidate_present and not detection_active:
                        detection_active = True
                        print("🔄 Detection RESUMED - Candidate present")
                    if not candidate_present and detection_active:
                        detection_active = False
                        print("⏸️ Detection PAUSED - No candidate present")

                    current_time = time.time()
                    if current_time - last_participant_check >= 30:
                        last_participant_check = current_time
                        for participant in current_participants:
                            participant_name = participant.get("userName", "Unknown")
                            # Simple guard: do not record Strata bot as participant
                            name_lower = (participant_name or "").strip().lower()
                            if "strata" in name_lower and "bot" in name_lower:
                                continue
                            if not any(p.get("userName") == participant_name for p in meeting_participants):
                                meeting_participants.append(participant)
                                print(f"📝 Recorded participant: {participant_name}")
                else:
                    if detection_active:
                        detection_active = False
                        print("⏸️ Detection PAUSED - No participants in the meeting")

                if detection_active:
                    screenshot = take_screenshot(page, full_page=False)
                    cv_frame = cv2.imdecode(np.frombuffer(screenshot, np.uint8), cv2.IMREAD_COLOR)
                    if cv_frame is not None:
                        big_tile_frame = get_big_tile_crop(page, daily_frame, iframe_element, cv_frame)
                        if big_tile_frame is not None:
                            face.detect_face(big_tile_frame)
                            eye.track_eyes(big_tile_frame)
                            multi.detect_multiple_faces(big_tile_frame)
                            objects.detect_objects(big_tile_frame, visualize=True)
                        else:
                            print("⚠️ Could not crop big tile; running detection on full frame")
                            face.detect_face(cv_frame)
                            eye.track_eyes(cv_frame)
                            multi.detect_multiple_faces(cv_frame)
                            objects.detect_objects(cv_frame, visualize=True)

                if daily_frame and candidate_present and not pinned_once:
                    pinned = pin_participant(daily_frame)
                    if pinned:
                        print("✅ Successfully pinned participant")
                        pinned_once = True
                    else:
                        print("⚠️ Could not pin any participant")

                ensure_chat_open(daily_frame)
                while not chat_queue.empty():
                    msg = chat_queue.get()
                    send_chat_message(daily_frame, msg)
                    print(f"📤 Alert sent: {msg}")

                current_participants_for_leaving = get_active_participants(room_name)
                # Start leave timer only when NO participant except the bot is present
                no_candidate_present = True
                if current_participants_for_leaving:
                    for _p in current_participants_for_leaving:
                        _name2 = (_p.get("userName") or "").strip().lower()
                        _name2_ns = _name2.replace(" ", "")
                        if ("strata" in _name2_ns) and ("bot" in _name2_ns):
                            continue
                        no_candidate_present = False
                        break

                if no_candidate_present:
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
                                    # Add human-readable duration string for report display
                                    total_secs = int(meeting_info.get("duration", 0))
                                    hrs, rem = divmod(total_secs, 3600)
                                    mins, secs = divmod(rem, 60)
                                    if hrs:
                                        meeting_info["duration_str"] = f"{hrs}h {mins}m {secs}s"
                                    elif mins:
                                        meeting_info["duration_str"] = f"{mins}m {secs}s"
                                    else:
                                        meeting_info["duration_str"] = f"{secs}s"
                                print(f"📋 Final Meeting Info with Duration: {meeting_info}")
                            else:
                                print("⚠️ Could not fetch final meeting info.")

                            time.sleep(2)
                            if daily_frame:
                                try:
                                    stop_recording_and_leave(daily_frame)
                                    print("✅ Bot left the meeting after 1-minute wait.")
                                    leave_time_ist = utc_to_ist(datetime.now(timezone.utc))
                                    print(f"🕒 Bot LEFT meeting at: {leave_time_ist.strftime('%Y-%m-%d %H:%M:%S')} IST")
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

        # Drop the last pending detection from persistence (ignore last detection)
        try:
            logger.finalize()
        except Exception:
            pass

        page.wait_for_timeout(2000)
        # session.browser.close()
        # Decide whether to proceed with post-processing based on who attended
        if not meeting_participants:
            print("As there were no participants in the session, report generation is not applicable.")
            return

        normalized_names = [
            (p.get("userName") or "Unknown").strip().lower() for p in meeting_participants
        ]
        has_concret = any(n == "concret.io" for n in normalized_names)
        has_candidate = any(n not in {"concret.io", "Strata (Bot)"} for n in normalized_names)

        # Case 1: Only strata(Bot) and concret.io were present (no candidate)
        if not has_candidate and has_concret:
            print("As candidate was not present so report generation is not applicable.")
            return

        # Case 2: Only Candidate and Strata(Bot)  were present (no interviewer)
        if has_candidate and not has_concret:
            print("As interviewer was not present so report generation is not applicable.")
            return

        # Edge case: Neither candidate nor interviewer present (e.g., only Strata(Bot))
        if not has_candidate and not has_concret:
            print("As neither candidate nor interviewer were present so report generation is not applicable.")
            return

        transcript_text = None

        print("📥 Fetching cloud recording & extracting audio...")
        poll_cfg = config.get('recording', {})
        poll_total = int(poll_cfg.get('poll_total_secs', 180))
        poll_interval = int(poll_cfg.get('poll_interval_secs', 6))
        wav_path = util_fetch_cloud_recording_wav(room_name, HEADERS, poll_total, poll_interval)

        if wav_path and wav_path.exists():
            print(f"📝 Transcribing audio from {wav_path} using faster-whisper via AudioMonitor...")
            audio_monitor.audio_file = str(wav_path)
            transcript_text = audio_monitor.get_transcript_text()
        else:
            print(f"❌ Could not fetch or process cloud recording for room: {room_name}")

        print("🤖 Analyzing transcript with LLM...")
        llm_analysis = analyze_transcript(room_name)
        print("✅ LLM analysis complete.")

        candidate_analysis, interviewer_analysis, decision = parse_llm_response(llm_analysis)

        if meeting_participants:
            print(f"📊 Generating reports for  participant(s)")
            # Find interviewer (concret.io) ID
            interviewer_id = None
            for p in meeting_participants:
                uname = (p.get("userName") or "").strip().lower()
                if uname == "concret.io":
                    interviewer_id = p.get("id")
                    break

            for person in meeting_participants:
                username = person.get("userName", "Unknown")
                if username.strip().lower() == "concret.io":
                    continue

                student = {
                    'id': person.get("id") or datetime.now().strftime('%Y%m%d%H%M%S'),
                    'name': person.get("userName", "Unknown"),
                    'email': f'{person.get("userName", "unknown").lower().replace(" ", "")}@example.com',
                    'interviewer_name': interviewer_id or ''
                }

                report_gen = ReportGenerator(config)

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
                    try:
                        receiver = get_email_default_receiver()
                        send_email_with_attachments(
                            report_path=report_path,
                            student_name=student['name'],
                            receiver_email=receiver,  # falls back inside to .env if None
                            room_name=room_name,
                        )
                    except Exception as e:
                        print(f"❌ Failed to send email for {student['name']}: {e}")

                else:
                    print(f"❌ Report generation failed for {student['name']}")

        else:
            print("⚠️ No participants found, generating default report")

if __name__ == "__main__":
    t, url = get_next_daily_meeting()
    if t and url:
        room_name = urlparse(url).path.lstrip("/") or "session"
        log_path = init_terminal_logging(room_name)
        join_daily(t, url)
    else:
        print("❌ No Daily.co meeting found.")
    # if len(sys.argv) >= 3:
    #     url = sys.argv[1]
    #     room_name = sys.argv[2]
    #     log_path = init_terminal_logging(room_name)
    #     meeting_time_utc = datetime.now(timezone.utc)  # assume join now
    #     join_daily(meeting_time_utc, url)
    # else:
    #     print("❌ Please provide room URL and name as arguments.")
