import smtplib
from email.message import EmailMessage
import os
from glob import glob
from pathlib import Path
import re
import time
import yaml
from utils.env_utils import (
    load_dotenv,
    get_email_sender,
    get_email_app_password,
    get_email_default_receiver,
)
from report_generation.score_evaluator import analyze_transcript, parse_llm_response
from utils.env_utils import get_env

def send_email_with_attachments(report_path, student_name, receiver_email=None, room_name=None,
                                final_status: str | None = None,
                                forced_reason: str | None = None,
                                ai_remarks_override: str | None = None,
                                suspicious_text_override: str | None = None):
    """
    Send email with PDF report, transcript file, and log file attachments
    
    Args:
        report_path (str): Path to the PDF report
        student_name (str): Name of the student
        receiver_email (str): Recipient email address (optional)
        room_name (str): Room name to find corresponding transcript and log files
    """
    # Ensure .env is loaded (no-op if already loaded)
    load_dotenv()

    sender_email = get_email_sender()
    app_password = get_email_app_password()
    default_receiver = get_email_default_receiver()
    receiver_email = receiver_email or default_receiver

    if not sender_email or not app_password:
        print("❌ Email credentials missing: please set EMAIL_SENDER and EMAIL_APP_PASSWORD in your .env file.")
        return

    # Resolve recipients from .env (preferred) or fallbacks. We allow either to be present.
    report_receiver = get_env("EMAIL_REPORT_RECEIVER") or receiver_email or default_receiver
    artifacts_receiver = get_env("EMAIL_ARTIFACTS_RECEIVER") or receiver_email or default_receiver
    if not (report_receiver or artifacts_receiver):
        print("⚠️ No recipient configured: set EMAIL_REPORT_RECEIVER/EMAIL_ARTIFACTS_RECEIVER or pass receiver_email or set EMAIL_RECEIVER in .env")
        return

    # --------------------
    # Derive dynamic fields from LLM prompt outputs and logs
    # --------------------
    status_text = (final_status or "Summary")
    ai_remarks_text = (ai_remarks_override or "Not available")
    suspicious_text = (suspicious_text_override or "Not available")
    forced_reason = forced_reason

    try:
        project_root = Path(__file__).resolve().parents[2]

        # 1) Suspicious activity count derived like ReportGenerator total violations
        #    Count ALL alerts (all types) except FACE_REAPPEARED across room logs.
        if (not suspicious_text_override) and room_name:
            logs_glob = str(project_root / "code" / "session_data" / "logs" / f"alerts_{room_name}_*.log")
            log_files = sorted(glob(logs_glob))
            if log_files:
                try:
                    # Example line format: "2025-09-15_12:34:56 - SUSPICIOUS_ACTIVITY: details"
                    type_re = re.compile(r"-\s+([A-Z_]+):")
                    total_count = 0
                    for log_path in log_files:
                        try:
                            with open(log_path, 'r', encoding='utf-8') as lf:
                                for line in lf:
                                    m = type_re.search(line.upper())
                                    if not m:
                                        continue
                                    atype = m.group(1).strip()
                                    if atype == "FACE_REAPPEARED":
                                        continue
                                    total_count += 1
                        except Exception:
                            continue
                    suspicious_text = f"{total_count} instance(s) detected"
                except Exception:
                    pass

        # 2) Status and AI Remarks (4–5 words) from LLM analysis (prompt region)
        #    Only if not explicitly provided by caller
        if (not final_status or not ai_remarks_override) and room_name:
            try:
                llm_analysis = analyze_transcript(room_name)
                cand, intr, dec = parse_llm_response(llm_analysis)
                if dec:
                    if (not final_status) and dec.get('recommendation'):
                        status_text = dec.get('recommendation').strip()
                    if (not ai_remarks_override) and dec.get('ai_remarks'):
                        ai_remarks_text = dec.get('ai_remarks').strip()
            except Exception:
                pass
        # If caller provided final_status, do not attempt any overrides here.
    except Exception:
        pass

    # Compose subject and bodies (HTML for better appeal)
    subject = f"[Interview Report] {student_name} - {status_text}"
    report_html = f"""
    <html>
      <body style="font-family:Segoe UI,Arial,sans-serif; color:#111;">
        <p>Hello Team,</p>
        <p>Here is the interview report for <strong>{student_name}</strong>. Quick snapshot:</p>
        <ul>
          <li><strong>Candidate Status:</strong> {status_text}</li>
          <li><strong>AI Remarks :</strong> {ai_remarks_text}</li>
          <li><strong>Suspicious Activity:</strong> {suspicious_text}</li>
        </ul>
        <p><strong>Included:</strong> Evaluation Report (PDF)</p>
        <p style="margin-top:10px;">If you need more details regarding the session or encounter any issues, please reach out to Candidly Support for assistance. candidly-support@concret.io</p>
        <p style="margin-top:20px;">Best regards,<br/> Team candidly</p>
      </body>
    </html>
    """

    artifacts_html = f"""
    <html>
      <body style="font-family:Segoe UI,Arial,sans-serif; color:#111;">
        <p>Hello Team,</p>
        <p>Here are the supporting artifacts for <strong>{student_name}</strong> Snapshot:</p>
        <ul>
          <li><strong>Candidate Status:</strong> {status_text}</li>
          <li><strong>AI Remarks :</strong> {ai_remarks_text}</li>
          <li><strong>Suspicious Activity:</strong> {suspicious_text}</li>
        </ul>
        <p><strong>Included:</strong> Transcript (TXT), Alert Logs (LOG), Terminal Logs (LOG)</p>
        <p style="margin-top:10px;">For any issues or further assistance, kindly contact Candidly Support.candidly-support@concret.io</p>
        <p style="margin-top:20px;">Best regards,<br/>Team candidly</p>
      </body>
    </html>
    """

    # recipients already resolved above: report_receiver, artifacts_receiver

    # 1) Report-only email
    report_msg = EmailMessage()
    report_msg["Subject"] = subject
    report_msg["From"] = sender_email
    report_msg["To"] = report_receiver
    report_msg.set_content("This email requires an HTML-capable client.")
    report_msg.add_alternative(report_html, subtype="html")

    report_attachments = 0
    try:
        if os.path.exists(report_path):
            with open(report_path, "rb") as f:
                file_data = f.read()
                filename = os.path.basename(report_path)
                report_msg.add_attachment(file_data, maintype="application", subtype="pdf", filename=filename)
                report_attachments += 1
                print(f"✅ PDF report attached (report email): {filename}")
        else:
            print(f"⚠️ PDF report not found: {report_path}")
    except Exception as e:
        print(f"❌ Failed to attach PDF (report email): {e}")

    # 2) Artifacts-only email
    artifacts_msg = EmailMessage()
    artifacts_msg["Subject"] = f"[Interview Logs] {student_name} - {status_text}"
    artifacts_msg["From"] = sender_email
    artifacts_msg["To"] = artifacts_receiver
    artifacts_msg.set_content("This email requires an HTML-capable client.")
    artifacts_msg.add_alternative(artifacts_html, subtype="html")

    artifacts_attachments = 0
    try:
        project_root = Path(__file__).resolve().parents[2]
        transcripts_glob = str(project_root / "code" / "session_data" / "transcripts_doc" / f"transcript_{room_name}_*.txt")
        transcript_files = sorted(glob(transcripts_glob))
        if transcript_files:
            transcript_path = transcript_files[-1]
            with open(transcript_path, "r", encoding="utf-8") as f:
                transcript_data = f.read().encode('utf-8')
                filename = os.path.basename(transcript_path)
                artifacts_msg.add_attachment(transcript_data, maintype="text", subtype="plain", filename=filename)
                artifacts_attachments += 1
                print(f"✅ Transcript attached (artifacts email): {filename}")
        else:
            print(f"⚠️ No transcript file found for room: {room_name}")
    except Exception as e:
        print(f"❌ Failed to attach transcript (artifacts email): {e}")

    try:
        project_root = Path(__file__).resolve().parents[2]
        logs_glob = str(project_root / "code" / "session_data" / "logs" / f"alerts_{room_name}_*.log")
        log_files = sorted(glob(logs_glob))
        if log_files:
            log_path = log_files[-1]
            with open(log_path, "r", encoding="utf-8") as f:
                log_data = f.read().encode('utf-8')
                filename = os.path.basename(log_path)
                artifacts_msg.add_attachment(log_data, maintype="text", subtype="plain", filename=filename)
                artifacts_attachments += 1
                print(f"✅ Alert log attached (artifacts email): {filename}")
        else:
            print(f"⚠️ No alert log file found for room: {room_name}")
    except Exception as e:
        print(f"❌ Failed to attach alert log (artifacts email): {e}")

    try:
        project_root = Path(__file__).resolve().parents[2]
        term_glob = str(project_root / "code" / "session_data" / "terminal_logs" / f"terminal_log_{room_name}_*.log")
        term_files = sorted(glob(term_glob))
        if term_files:
            term_path = term_files[-1]
            with open(term_path, "r", encoding="utf-8") as f:
                term_data = f.read().encode('utf-8')
                filename = os.path.basename(term_path)
                artifacts_msg.add_attachment(term_data, maintype="text", subtype="plain", filename=filename)
                artifacts_attachments += 1
                print(f"✅ Terminal log attached (artifacts email): {filename}")
        else:
            print(f"⚠️ No terminal log file found for room: {room_name}")
    except Exception as e:
        print(f"❌ Failed to attach terminal log (artifacts email): {e}")

    # Send both emails
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, app_password)
            server.send_message(report_msg)
            print(f"📧 Report email sent to {report_receiver} | Attachments: {report_attachments}")
            # Optional delay between emails to avoid provider throttling
            try:
                delay_secs = int(get_env("EMAIL_SEND_DELAY_SECONDS") or 2)
            except Exception:
                delay_secs = 2
            if delay_secs > 0:
                print(f"⏳ Waiting {delay_secs}s before sending artifacts email...")
                time.sleep(delay_secs)
            server.send_message(artifacts_msg)
            print(f"📧 Artifacts email sent to {artifacts_receiver} | Attachments: {artifacts_attachments}")
    except Exception as e:
        print(f"❌ Failed to send email(s): {e}")
