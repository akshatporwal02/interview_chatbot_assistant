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

        # Ensure log directory exists
        os.makedirs(self.log_path, exist_ok=True)

        # Unique file per session
        self.session_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_filename = f"alerts_{self.room_name}_{self.session_timestamp}.log"

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

        # Screenshot capture if frame given
        image_path = None
        if frame is not None and self.capturer:
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

        # Add to violations list
        if self.violations_list is not None:
            self.violations_list.append({
                "type": alert_type,
                "message": message,
                "timestamp": timestamp,
                "image_path": image_path
            })

        # Send to chat queue
        if self.chat_queue:
            self.chat_queue.put(alert_text)

        return alert_text
