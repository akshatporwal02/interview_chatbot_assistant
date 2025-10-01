import cv2
import mediapipe as mp
import numpy as np
from datetime import datetime

class EyeTracker:
    def __init__(self, config):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5)
        
        self.config = config
        self.eye_threshold = config['detection']['eye_tracking']['gaze_threshold']
        # Tunable sensitivity parameters with sensible defaults
        et_cfg = config.get('detection', {}).get('eye_tracking', {})
        self.gaze_px_thresh = et_cfg.get('gaze_sensitivity', 15)  # base px threshold
        self.gaze_norm_frac = et_cfg.get('gaze_norm_frac', 0.20)  # fraction of inter-eye distance
        self.velocity_thresh = et_cfg.get('velocity_threshold', 7.0)  # px/frame change to count micro move
        self.ear_delta_thresh = et_cfg.get('ear_delta_threshold', 0.07)  # rapid EAR change indicates occlusion/hand near face
        self.min_event_gap_sec = et_cfg.get('min_event_gap_sec', 2.0)  # debounce between alerts
        self.last_gaze_change = datetime.now()
        self.gaze_direction = "center"  # Default value
        self.eye_ratio = 0.3  # Default open eye ratio
        self.gaze_changes = 0
        self.alert_logger = None
        # Track last measurements for velocity and deltas
        self._last_horiz_diff = None
        self._last_ear = None
        self._last_alert_time = datetime.min
        
        # Landmark indices for left and right eyes
        self.LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
        self.RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
        
        # For EAR (Eye Aspect Ratio) calculation
        self.EYE_ASPECT_RATIO_THRESH = 0.3
        self.EYE_ASPECT_RATIO_CONSEC_FRAMES = 3

    def set_alert_logger(self, alert_logger):
        self.alert_logger = alert_logger

    def _calculate_ear(self, eye_points):
        # Compute the euclidean distances between the two sets of
        # vertical eye landmarks (x, y)-coordinates
        A = np.linalg.norm(eye_points[1] - eye_points[5])
        B = np.linalg.norm(eye_points[2] - eye_points[4])
        
        # Compute the euclidean distance between the horizontal
        # eye landmark (x, y)-coordinates
        C = np.linalg.norm(eye_points[0] - eye_points[3])
        
        # Compute the eye aspect ratio
        ear = (A + B) / (2.0 * C)
        return ear

    def track_eyes(self, frame):
        try:
            # Convert frame to RGB and process
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb_frame)
            
            if not results.multi_face_landmarks:
                return self.gaze_direction, self.eye_ratio  # Return last known values
            
            face_landmarks = results.multi_face_landmarks[0]
            frame_h, frame_w = frame.shape[:2]
            
            # Get eye landmarks in pixel coordinates
            left_eye_coords = np.array([(face_landmarks.landmark[i].x * frame_w, 
                                       face_landmarks.landmark[i].y * frame_h) 
                                      for i in self.LEFT_EYE_INDICES])
            
            right_eye_coords = np.array([(face_landmarks.landmark[i].x * frame_w, 
                                        face_landmarks.landmark[i].y * frame_h) 
                                       for i in self.RIGHT_EYE_INDICES])
            
            # Calculate Eye Aspect Ratio (EAR) for both eyes
            left_ear = self._calculate_ear(left_eye_coords)
            right_ear = self._calculate_ear(right_eye_coords)
            self.eye_ratio = (left_ear + right_ear) / 2.0
            
            # Calculate gaze direction based on eye position
            left_eye_center = np.mean(left_eye_coords, axis=0)
            right_eye_center = np.mean(right_eye_coords, axis=0)
            
            # Calculate horizontal difference between eye centers and nose
            nose_tip = np.array([face_landmarks.landmark[4].x * frame_w,
                                face_landmarks.landmark[4].y * frame_h])
            
            left_diff = left_eye_center[0] - nose_tip[0]
            right_diff = right_eye_center[0] - nose_tip[0]
            horiz_diff = (left_diff + right_diff) / 2.0
            # Compute normalized threshold using inter-eye distance for robustness across scales
            inter_eye_dist = np.linalg.norm(right_eye_center - left_eye_center)
            scaled_thresh = max(self.gaze_px_thresh, self.gaze_norm_frac * inter_eye_dist)
            
            # Determine gaze direction
            new_gaze = "center"
            if horiz_diff < -scaled_thresh:  # Looking left
                new_gaze = "left"
            elif horiz_diff > scaled_thresh:  # Looking right
                new_gaze = "right"
            
            # Update gaze changes and detect micro-movements
            current_time = datetime.now()
            velocity = 0.0 if self._last_horiz_diff is None else abs(horiz_diff - self._last_horiz_diff)
            ear_delta = 0.0 if self._last_ear is None else abs(self.eye_ratio - self._last_ear)
            
            movement_event = False
            if new_gaze != self.gaze_direction:
                movement_event = True
                self.gaze_direction = new_gaze
                self.last_gaze_change = current_time
                self.gaze_changes += 1
            # Consider micro-movements even if gaze bucket is unchanged
            if velocity > self.velocity_thresh or ear_delta > self.ear_delta_thresh:
                movement_event = True
                self.gaze_changes += 1
            
            # Debounce alerts to avoid spamming while still being responsive
            if movement_event and self.alert_logger:
                since_last = (current_time - self._last_alert_time).total_seconds()
                if since_last >= self.min_event_gap_sec:
                    self.alert_logger.log_alert(
                        "EYE_MOVEMENT",
                        "detected. Kindly maintain steady focus",
                        frame
                    )
                    self._last_alert_time = current_time
                # If we are within the debounce window, we just accumulate changes but don't spam alerts
            
            # Update last measurements
            self._last_horiz_diff = horiz_diff
            self._last_ear = self.eye_ratio
            return self.gaze_direction, self.eye_ratio
            
        except Exception as e:
            if self.alert_logger:
                self.alert_logger.log_alert(
                    "EYE_TRACKING_ERROR",
                    f"Error in eye tracking: {str(e)}"
                )
            return self.gaze_direction, self.eye_ratio  # Return last known values