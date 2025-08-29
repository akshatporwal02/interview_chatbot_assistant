import cv2
import torch
from ultralytics import YOLO
from datetime import datetime


class ObjectDetector:
    def __init__(self, config):
        self.config = config['detection']['objects']
        self.model = None

        # Target COCO classes mapped to human-readable labels
        self.class_map = {
            73: 'book',
            67: 'cell phone',
            62: 'tv',
            65: 'remote',
            63: 'laptop'
        }

        # Per-class confidence thresholds to balance recall vs precision
        # Make 'tv' stricter to avoid false positives on rectangular objects
        self.class_thresholds = {
            62: 0.85,  # tv (strict)
            63: 0.85,  # laptop
            65: 0.55,  # remote
            67: 0.55,  # cell phone
            73: 0.55   # book
        }

        # Additional filter: require TVs to occupy at least a small fraction of the frame
        # This helps ignore tiny rectangles falsely detected as TVs
        self.tv_min_area_frac = 0.015  # 1.5% of the frame area

        self.alert_logger = None
        self.detection_interval = self.config['detection_interval']
        self.frame_count = 0
        self._initialize_model()
        self.last_detection_time = datetime.now()

    def _initialize_model(self):
        """Initialize optimized YOLO model"""
        try:
            # Load model
            self.model = YOLO('models/yolov8l.pt')

            # Optimize model settings
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            imgsz = 960  # higher resolution to improve far/partial detections

            # Use a permissive base conf; final filtering via per-class thresholds
            self.model.overrides['conf'] = 0.50
            self.model.overrides['device'] = device
            self.model.overrides['imgsz'] = imgsz
            self.model.overrides['iou'] = 0.60

            # Restrict predictions to only our target classes to reduce noise
            self.model.overrides['classes'] = list(self.class_map.keys())

            # Warm up the model with the chosen input size
            dummy_input = torch.zeros((1, 3, imgsz, imgsz)).to(self.model.device)
            self.model(dummy_input)

        except Exception as e:
            raise RuntimeError(f"Failed to initialize object detector: {str(e)}")

    def set_alert_logger(self, alert_logger):
        self.alert_logger = alert_logger

    def detect_objects(self, frame, visualize=False):
        """Optimized object detection with time-based throttling.

        - Uses original frame (no pre-downscale) to preserve details
        - Higher imgsz and test-time augmentation to help far/partial objects
        - Per-class thresholds and TV min-area filter to reduce false positives
        """
        current_time = datetime.now()
        time_since_last = (current_time - self.last_detection_time).total_seconds()

        # Skip detection if not enough time has passed (rate limit by max_fps)
        if time_since_last < (1.0 / self.config['max_fps']):
            return False

        try:
            orig_h, orig_w = frame.shape[:2]

            # Run inference; augment helps on partial occlusions (slower but better recall)
            results = self.model(frame, verbose=False, augment=True)

            detected = False
            for result in results:
                for box in result.boxes:
                    cls = int(box.cls)
                    conf = float(box.conf)

                    if cls in self.class_map:
                        # Choose per-class threshold; fallback to config if not found
                        min_conf = self.class_thresholds.get(cls, self.config['min_confidence'])
                        if conf >= min_conf:
                            # Additional TV size filter to reduce spurious tiny detections
                            if cls == 62:  # tv
                                x1, y1, x2, y2 = box.xyxy[0]
                                w = float(x2 - x1)
                                h = float(y2 - y1)
                                area_frac = (w * h) / float(orig_w * orig_h)
                                if area_frac < self.tv_min_area_frac:
                                    continue

                            detected = True
                            label = self.class_map[cls]

                            if self.alert_logger:
                                self.alert_logger.log_alert(
                                    "FORBIDDEN_OBJECT",
                                    f"detected : {label}. Kindly refrain from using such objects.",
                                    frame
                                )

                            if visualize:
                                x1, y1, x2, y2 = box.xyxy[0]
                                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                                cv2.putText(
                                    frame,
                                    f"{label} {conf:.2f}",
                                    (x1, max(0, y1 - 10)),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5,
                                    (0, 0, 255),
                                    1,
                                )

            self.last_detection_time = current_time
            return detected

        except Exception as e:
            if self.alert_logger:
                self.alert_logger.log_alert(
                    "OBJECT_DETECTION_ERROR",
                    f"Object detection failed: {str(e)}"
                )
            return False