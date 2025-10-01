import cv2
import os
from datetime import datetime

class ViolationCapturer:
    def __init__(self, config):
        self.output_dir = os.path.join(config['global']['output_path'], "violation_captures")
        os.makedirs(self.output_dir, exist_ok=True)
        
    def capture_violation(self, frame, violation_type, timestamp=None):
        """Saves violation screenshot with metadata"""
        timestamp = timestamp or datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        # Convert timestamp for filename (remove colons for Windows compatibility)
        filename_timestamp = timestamp.replace(":", "")
        filename = f"{violation_type}_{filename_timestamp}.jpg"
        path = os.path.join(self.output_dir, filename)
        
        # Draw violation label on image
        labeled_frame = frame.copy()
        h, w = labeled_frame.shape[:2]
        text = f"{violation_type} - {timestamp}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        thickness = 2

        # Measure text and shrink if it would overflow
        (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        max_w = w - 40  # 20px padding on both sides
        if text_w > max_w and text_w > 0:
            font_scale = max(0.5, font_scale * (max_w / float(text_w)))
            (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)

        # Right-align within the frame with padding
        x = max(20, w - 20 - text_w)
        y = 40

        # Optional background for readability
        bg_top_left = (x - 8, y - text_h - 8)
        bg_bottom_right = (x + text_w + 8, y + baseline + 8)
        cv2.rectangle(labeled_frame, bg_top_left, bg_bottom_right, (255, 255, 255), -1)
        cv2.putText(labeled_frame, text, (x, y), font, font_scale, (0, 0, 255), thickness)
        
        cv2.imwrite(path, labeled_frame)
        return {
            'type': violation_type,
            'timestamp': timestamp,
            'image_path': os.path.abspath(path)
        }