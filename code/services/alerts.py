import os
from datetime import datetime
class AlertLog:
    def __init__(self, config, room_name=None):
        self.log_path = config['logging']['log_path']
        self.alerts = []
        self.cooldown = config['logging']['alert_cooldown']
        self.last_alert_time = {}
        self.room_name = room_name or "unknown_room"
        
        # Generate session timestamp for unique file naming
        self.session_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        # Create log directory if it doesn't exist
        os.makedirs(self.log_path, exist_ok=True)
        
        # Generate unique log filename for this session
        self.log_filename = f"alerts_{self.room_name}_{self.session_timestamp}.log"
        
    def log_alert(self, alert_type, message):
        """Log an alert with type and message"""
        current_time = datetime.now().timestamp()
        
        # Check cooldown for this alert type
        if alert_type in self.last_alert_time:
            if current_time - self.last_alert_time[alert_type] < self.cooldown:
                return None
                
        self.last_alert_time[alert_type] = current_time
        
        # Use readable timestamp format: 2025-08-01_12:44:42
        timestamp = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        log_entry = f"{timestamp} - {alert_type.upper()}: {message}"
        self.alerts.append(log_entry)
        
        # Save to room-specific session file
        log_file = os.path.join(self.log_path, self.log_filename)
        with open(log_file, "a") as f:
            f.write(log_entry + "\n")
            
        return log_entry