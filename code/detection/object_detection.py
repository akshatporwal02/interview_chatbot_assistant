import cv2
import torch
from ultralytics import YOLO
from datetime import datetime
 


class ObjectDetector:
    def __init__(self, config):
        # Use detection config provided by the caller (merged in main)
        self.config = config['detection']['objects']
        self.model = None

        # Load class map and thresholds from config (keys may be strings in YAML)
        raw_class_map = self.config.get('class_map', {})
        self.class_map = {int(k): v for k, v in raw_class_map.items()}

        raw_thresh = self.config.get('class_thresholds', {})
        self.class_thresholds = {int(k): float(v) for k, v in raw_thresh.items()}

        # Special handling for TV minimum area fraction
        self.tv_class_id = int(self.config.get('tv_class_id'))
        self.tv_min_area_frac = float(self.config.get('tv_min_area_frac'))

        # Optional handling for phone class id: take from config if present, else infer from class_map
        phone_cfg = self.config.get('phone_class_id', None)
        self.phone_class_id = int(phone_cfg) if phone_cfg is not None else None
        if self.phone_class_id is None:
            # Try to infer by label name containing 'phone'
            inferred = None
            for cid, label in self.class_map.items():
                try:
                    if isinstance(label, str) and 'phone' in label.lower():
                        inferred = cid
                        break
                except Exception:
                    # Ignore any odd labels
                    pass
            self.phone_class_id = inferred

        self.alert_logger = None
        self.detection_interval = int(self.config.get('detection_interval'))
        self.frame_count = 0
        self._initialize_model()
        self.last_detection_time = datetime.now()

    def _initialize_model(self):
        """Initialize optimized YOLO model"""
        try:
            # Load model with absolute path to avoid CWD issues
            from pathlib import Path
            model_cfg = self.config.get('model_path', 'models/yolov8l.pt')
            # If config path is relative, resolve relative to repo root (code/..)
            model_path = (
                Path(__file__).resolve().parents[1] / model_cfg
                if not Path(model_cfg).is_absolute() else Path(model_cfg)
            )
            # If the path exists, load from file. Otherwise, pass the original string
            # (model name) to YOLO so it can leverage its cache/download mechanism.
            if model_path.exists():
                self.model = YOLO(str(model_path))
            else:
                self.model = YOLO(str(model_cfg))

            # Optimize model settings from config
            # Ultralytics does not support 'dml' device string; use CUDA if available else CPU
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            imgsz = int(self.config.get('imgsz', 960))
            self.model.overrides['conf'] = float(self.config.get('base_conf'))
            self.model.overrides['device'] = device
            self.model.overrides['imgsz'] = imgsz
            self.model.overrides['iou'] = float(self.config.get('iou'))

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
            use_tta = bool(self.config.get('augment', True))
            results = self.model(frame, verbose=False, augment=use_tta)
            detected = False
            for result in results:
                for box in result.boxes:
                    cls = int(box.cls)
                    conf = float(box.conf)
        
                    if cls in self.class_map:
                        # Choose per-class threshold; fallback to config if not found
                        min_conf = self.class_thresholds.get(cls, float(self.config.get('min_confidence', 0.65)))
                        if conf >= min_conf:
                            # Additional TV size filter to reduce spurious tiny detections
                            if cls == self.tv_class_id:
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