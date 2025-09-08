import smtplib
from email.message import EmailMessage
import os
from glob import glob
from pathlib import Path

def send_email_with_attachments(report_path, student_name, receiver_email, room_name):
    """
    Send email with PDF report, transcript file, and log file attachments
    
    Args:
        report_path (str): Path to the PDF report
        student_name (str): Name of the student
        receiver_email (str): Recipient email address
        room_name (str): Room name to find corresponding transcript and log files
    """
    sender_email = ""
    app_password = ""  # Use App Password for Gmail

    subject = f"Interview Summary Files for {student_name}"
    body = f"""Hello team,

Please find attached the complete interview summary files for  {student_name} , which include:

📄 Evaluation Report (PDF) -  A detailed analysis and assessment of the candidate’s performance  
📝 Transcript File - A complete record of the interview conversation  
📋 Log File - System alerts and monitoring details

These files are provided to ensure transparency and offer comprehensive insights into the session

Best regards,
Concret.io Team"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg.set_content(body)

    attachments_count = 0

    # Attach PDF Report
    try:
        if os.path.exists(report_path):
            with open(report_path, "rb") as f:
                file_data = f.read()
                filename = os.path.basename(report_path)
                msg.add_attachment(file_data, maintype="application", subtype="pdf", filename=filename)
                attachments_count += 1
                print(f"✅ PDF report attached: {filename}")
        else:
            print(f"⚠️ PDF report not found: {report_path}")
    except Exception as e:
        print(f"❌ Failed to attach PDF: {e}")

    # Find and attach transcript file
    try:
        project_root = Path(__file__).resolve().parents[2]
        transcripts_glob = str(project_root / "code" / "session_data" / "transcripts_doc" / f"transcript_{room_name}_*.txt")
        transcript_files = sorted(glob(transcripts_glob))
        if transcript_files:
            transcript_path = transcript_files[-1]  # Get the most recent one
            with open(transcript_path, "r", encoding="utf-8") as f:
                transcript_data = f.read().encode('utf-8')
                filename = os.path.basename(transcript_path)
                msg.add_attachment(transcript_data, maintype="text", subtype="plain", filename=filename)
                attachments_count += 1
                print(f"✅ Transcript attached: {filename}")
        else:
            print(f"⚠️ No transcript file found for room: {room_name}")
    except Exception as e:
        print(f"❌ Failed to attach transcript: {e}")

    # Find and attach log file
    try:
        project_root = Path(__file__).resolve().parents[2]
        logs_glob = str(project_root / "code" / "session_data" / "logs" / f"alerts_{room_name}_*.log")
        log_files = sorted(glob(logs_glob))
        if log_files:
            log_path = log_files[-1]  # Get the most recent one
            with open(log_path, "r", encoding="utf-8") as f:
                log_data = f.read().encode('utf-8')
                filename = os.path.basename(log_path)
                msg.add_attachment(log_data, maintype="text", subtype="plain", filename=filename)
                attachments_count += 1
                print(f"✅ Log file attached: {filename}")
        else:
            print(f"⚠️ No log file found for room: {room_name}")
    except Exception as e:
        print(f"❌ Failed to attach log file: {e}")

    # Send the email
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, app_password)
            server.send_message(msg)
            print(f"📧 Email sent successfully to {receiver_email}")
            print(f"📎 Total attachments sent: {attachments_count}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

# Keep the old function for backward compatibility
# def send_email_with_pdf(report_path, student_name, receiver_email):
#     """
#     Legacy function - sends only PDF report
#     For backward compatibility only
#     """
#     sender_email = "akshatporwal022003@gmail.com"
#     app_password = "agmp myvy ogpc ycey"  # Use App Password for Gmail

#     subject = f"Interview Report for {student_name}"
#     body = f"Hello,\n\nHere is the interview report for {student_name}.\n\nRegards,\nConcret.io"

#     msg = EmailMessage()
#     msg["Subject"] = subject
#     msg["From"] = sender_email
#     msg["To"] = receiver_email
#     msg.set_content(body)

#     # Attach PDF
#     with open(report_path, "rb") as f:
#         file_data = f.read()
#         msg.add_attachment(file_data, maintype="application", subtype="pdf", filename=report_path.split("/")[-1])

#     try:
#         with smtplib.SMTP("smtp.gmail.com", 587) as server:
#             server.starttls()
#             server.login(sender_email, app_password)
#             server.send_message(msg)
#             print(f"📧 Email sent to {receiver_email} with report.")
#     except Exception as e:
#         print(f"❌ Failed to send email: {e}")
