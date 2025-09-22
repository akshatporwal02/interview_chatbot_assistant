import os
from datetime import datetime

class AlertLogger:
    def __init__(self, config, room_name=None, chat_queue=None, capturer=None, violations_list=None):
        # Config
        self.log_path = config['logging']['log_path']
        self.cooldown = config['logging']['alert_cooldown']
        self.room_name = room_name or "unknown_room"

        # External handlers
        self.chat_queue = chat_queue
        self.capturer = capturer
        self.violations_list = violations_list

        # Internal state
        self.last_alert_time = {}
        self.alerts = []
        # Buffer the last alert so it is not persisted until the next alert arrives.
        # This ensures the final alert of the session is ignored from files/reports.
        self._pending_alert = None

        # Ensure log directory exists
        os.makedirs(self.log_path, exist_ok=True)

        # Unique file per session
        self.session_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_filename = f"alerts_{self.room_name}_{self.session_timestamp}.log"

    def _persist_alert(self, alert):
        """Persist a single alert to file, in-memory store, violations list and attachments."""
        if not alert:
            return
        timestamp = alert["timestamp"]
        alert_type = alert["type"]
        message = alert["message"]
        frame = alert.get("frame")

        # Screenshot capture if frame given
        image_path = None
        # Do NOT capture screenshots for FACE_REAPPEARED; they are not useful for reports
        if (frame is not None) and self.capturer and (alert_type.upper() != "FACE_REAPPEARED"):
            result = self.capturer.capture_violation(frame, alert_type, timestamp)
            image_path = result.get('image_path')

        # Store in memory
        self.alerts.append({
            "type": alert_type,
            "message": message,
            "timestamp": timestamp,
            "image_path": image_path
        })

        # Write to log file
        log_entry = f"{timestamp} - {alert_type.upper()}: {message}"
        log_file = os.path.join(self.log_path, self.log_filename)
        with open(log_file, "a") as f:
            f.write(log_entry + "\n")

        # Add to violations list, except FACE_REAPPEARED which should be omitted from reports
        if self.violations_list is not None and (alert_type.upper() != "FACE_REAPPEARED"):
            self.violations_list.append({
                "type": alert_type,
                "message": message,
                "timestamp": timestamp,
                "image_path": image_path
            })

    def finalize(self):
        """On session end, handle the last pending alert.

        - If the last detection is FACE_DISAPPEARED, drop it (do not persist to logs,
          stats, or attachments).
        - Otherwise, persist the last pending alert so it is not lost.
        """
        if self._pending_alert is None:
            return
        if (self._pending_alert.get("type") or "").upper() == "FACE_DISAPPEARED":
            # Explicitly drop the last FACE_DISAPPEARED
            self._pending_alert = None
            return
        # Persist any other final alert
        try:
            self._persist_alert(self._pending_alert)
        finally:
            self._pending_alert = None

    def log_alert(self, alert_type, message, frame=None):
        """Log alert to console, log file, chat, and violations list."""
        current_time = datetime.now().timestamp()

        # Cooldown check
        if alert_type in self.last_alert_time:
            if current_time - self.last_alert_time[alert_type] < self.cooldown:
                return None
        self.last_alert_time[alert_type] = current_time

        # Timestamp + formatted text
        timestamp = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        alert_text = f"⚠️ {alert_type.upper()} {message}"
        print(alert_text)  # ✅ Console

        # Send to chat immediately (terminal/chat allowed to show last alert)
        if self.chat_queue:
            self.chat_queue.put(alert_text)

        # Persist the previously pending alert (if any)
        if self._pending_alert is not None:
            self._persist_alert(self._pending_alert)

        # Buffer this alert as the new pending alert; it will be persisted
        # only when a subsequent alert arrives. If no subsequent alert arrives,
        # finalize() will drop it (ignore last detection).
        self._pending_alert = {
            "type": alert_type,
            "message": message,
            "timestamp": timestamp,
            "frame": frame,
        }

        return alert_text
