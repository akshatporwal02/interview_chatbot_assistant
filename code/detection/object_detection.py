import cv2
import torch
from ultralytics import YOLO
from datetime import datetime
 

class ObjectDetector:
    def __init__(self, config):
        # Use detection config provided by the caller (merged in main)
        self.config = config['detection']['objects']
        self.model = None
        self.veto_model = None

        # Load class map and thresholds from config (keys may be strings in YAML)
        raw_class_map = self.config.get('class_map', {})
        self.class_map = {int(k): v for k, v in raw_class_map.items()}

        raw_thresh = self.config.get('class_thresholds', {})
        self.class_thresholds = {int(k): float(v) for k, v in raw_thresh.items()}

        # Special handling for TV minimum area fraction
        self.tv_class_id = int(self.config.get('tv_class_id'))
        self.tv_min_area_frac = float(self.config.get('tv_min_area_frac'))

        # Headphones veto configuration (optional)
        veto_cfg = self.config.get('veto_headphones', {})
        self.veto_enabled = bool(veto_cfg.get('enabled', False))
        self.veto_model_path = veto_cfg.get('model_path', 'models/best.pt')
        self.veto_conf = float(veto_cfg.get('conf', 0.35))
        self.veto_iou = float(veto_cfg.get('iou', 0.5))
        self.veto_imgsz = int(veto_cfg.get('imgsz', int(self.config.get('imgsz', 960))))
        self.veto_overlap_iou_threshold = float(veto_cfg.get('overlap_iou_threshold', 0.2))
        # Expand veto boxes around headphones to catch nearby hand regions
        self.veto_expand_factor = float(veto_cfg.get('veto_expand_factor', 1.3))

        # Determine phone class id(s) from class_map labels (e.g., COCO id 67)
        self.phone_class_ids = {cid for cid, name in self.class_map.items() if str(name).lower() == 'cell phone'}

        self.alert_logger = None
        self.detection_interval = int(self.config.get('detection_interval'))
        self.frame_count = 0
        self._initialize_model()
        if self.veto_enabled:
            self._initialize_veto_model()
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

    def _initialize_veto_model(self):
        """Load optional headphones veto model with minimal overhead."""
        try:
            from pathlib import Path
            model_cfg = self.veto_model_path
            model_path = (
                Path(__file__).resolve().parents[1] / model_cfg
                if not Path(model_cfg).is_absolute() else Path(model_cfg)
            )
            if model_path.exists():
                self.veto_model = YOLO(str(model_path))
            else:
                self.veto_model = YOLO(str(model_cfg))

            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            self.veto_model.overrides['conf'] = self.veto_conf
            self.veto_model.overrides['device'] = device
            self.veto_model.overrides['imgsz'] = self.veto_imgsz
            self.veto_model.overrides['iou'] = self.veto_iou

            # Warmup once
            dummy_input = torch.zeros((1, 3, self.veto_imgsz, self.veto_imgsz)).to(self.veto_model.device)
            self.veto_model(dummy_input)
        except Exception as e:
            # If veto model fails, continue without veto
            self.veto_enabled = False
            if self.alert_logger:
                self.alert_logger.log_alert(
                    "OBJECT_DETECTION_WARNING",
                    f"Headphones veto model disabled due to load error: {str(e)}"
                )

    @staticmethod
    def _iou(box_a, box_b):
        """Compute IoU between two boxes [x1,y1,x2,y2] (ints or floats)."""
        xA = max(box_a[0], box_b[0])
        yA = max(box_a[1], box_b[1])
        xB = min(box_a[2], box_b[2])
        yB = min(box_a[3], box_b[3])
        inter_w = max(0.0, xB - xA)
        inter_h = max(0.0, yB - yA)
        inter_area = inter_w * inter_h
        if inter_area <= 0:
            return 0.0
        boxA_area = max(0.0, (box_a[2] - box_a[0])) * max(0.0, (box_a[3] - box_a[1]))
        boxB_area = max(0.0, (box_b[2] - box_b[0])) * max(0.0, (box_b[3] - box_b[1]))
        union = boxA_area + boxB_area - inter_area
        if union <= 0:
            return 0.0
        return inter_area / union

    @staticmethod
    def _expand_box(box, factor, frame_w, frame_h):
        """Expand a box [x1,y1,x2,y2] by 'factor' around its center and clamp to frame."""
        x1, y1, x2, y2 = map(float, box)
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        w = (x2 - x1)
        h = (y2 - y1)
        # New half sizes
        half_w = (w * factor) / 2.0
        half_h = (h * factor) / 2.0
        nx1 = max(0.0, cx - half_w)
        ny1 = max(0.0, cy - half_h)
        nx2 = min(float(frame_w), cx + half_w)
        ny2 = min(float(frame_h), cy + half_h)
        return [nx1, ny1, nx2, ny2]
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

            # First pass: collect candidate detections and phone boxes
            detections = []  # list of tuples: (cls, conf, [x1,y1,x2,y2])
            phone_candidates = []  # subset of detections for phone

            for result in results:
                for box in result.boxes:
                    cls = int(box.cls)
                    conf = float(box.conf)

                    if cls in self.class_map:
                        # Choose per-class threshold; fallback to config if not found
                        min_conf = self.class_thresholds.get(cls, float(self.config.get('min_confidence', 0.65)))
                        if conf < min_conf:
                            continue

                        # Additional TV size filter to reduce spurious tiny detections
                        if cls == self.tv_class_id:
                            x1, y1, x2, y2 = box.xyxy[0]
                            w = float(x2 - x1)
                            h = float(y2 - y1)
                            area_frac = (w * h) / float(orig_w * orig_h)
                            if area_frac < self.tv_min_area_frac:
                                continue

                        x1, y1, x2, y2 = box.xyxy[0]
                        det_box = [float(x1), float(y1), float(x2), float(y2)]
                        detections.append((cls, conf, det_box))
                        if cls in self.phone_class_ids:
                            phone_candidates.append((cls, conf, det_box))

            # If configured, run veto model only when phone candidates exist
            veto_boxes = []  # headphones boxes
            if self.veto_enabled and len(phone_candidates) > 0 and self.veto_model is not None:
                try:
                    veto_results = self.veto_model(frame, verbose=False, augment=False)
                    for vr in veto_results:
                        for vbox in vr.boxes:
                            vconf = float(vbox.conf)
                            if vconf < self.veto_conf:
                                continue
                            vx1, vy1, vx2, vy2 = vbox.xyxy[0]
                            # Expand veto boxes to include nearby hand regions around headphones
                            raw_box = [float(vx1), float(vy1), float(vx2), float(vy2)]
                            exp_box = self._expand_box(raw_box, self.veto_expand_factor, orig_w, orig_h)
                            veto_boxes.append(exp_box)
                except Exception as e:
                    # Fail open: if veto fails, proceed without suppression
                    if self.alert_logger:
                        self.alert_logger.log_alert(
                            "OBJECT_DETECTION_WARNING",
                            f"Headphones veto inference failed: {str(e)}"
                        )

            # Apply suppression: remove phone detections overlapping any veto box
            suppressed = set()
            if veto_boxes:
                for idx, (cls, conf, box_xyxy) in enumerate(detections):
                    if cls in self.phone_class_ids:
                        for vbox in veto_boxes:
                            if self._iou(box_xyxy, vbox) >= self.veto_overlap_iou_threshold:
                                suppressed.add(idx)
                                break

            # Emit alerts and visualization for remaining detections
            detected = False
            for idx, (cls, conf, box_xyxy) in enumerate(detections):
                if idx in suppressed:
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
                    x1, y1, x2, y2 = map(int, box_xyxy)
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