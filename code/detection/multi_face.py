import cv2
import mediapipe as mp


class MultiFaceDetector:
    def __init__(
        self,
        config,
        show_debug_sources=False,  # optional per-source debug (only MediaPipe here)
        show_final_green=True,
        min_area_px=600
    ):
        # Load config with safe fallbacks
        mf_cfg = (config or {}).get('detection', {}).get('multi_face', {})

        # MediaPipe detector configuration
        self.model_selection = int(mf_cfg.get('model_selection', 1))  # 0: short range, 1: full range
        # Support both keys for convenience
        self.min_confidence = float(mf_cfg.get('min_detection_confidence', mf_cfg.get('min_confidence', 0.5)))
        self.upscale_factor = float(mf_cfg.get('upscale_factor', 1.0))  # 1.0 means no upscale

        # Initialize MediaPipe once (reused across calls)
        self.mp_face = mp.solutions.face_detection.FaceDetection(
            model_selection=self.model_selection,
            min_detection_confidence=self.min_confidence
        )

        # Alerting
        self.threshold = int(mf_cfg.get('alert_threshold', 1))
        self.consecutive_frames = 0
        self.alert_triggered = False
        self.alert_logger = None

        # Visualization
        self.show_debug_sources = bool(mf_cfg.get('show_debug_sources', show_debug_sources))
        self.show_final_green = bool(mf_cfg.get('show_final_green', show_final_green))
        self.min_area_px = int(mf_cfg.get('min_area_px', min_area_px))

    def set_alert_logger(self, alert_logger):
        self.alert_logger = alert_logger

    # -------------------- detectors --------------------
    def _detect_mediapipe(self, frame_bgr):
        # Optional upscale to improve recall on small faces
        if self.upscale_factor and self.upscale_factor > 1.0:
            frame_proc = cv2.resize(
                frame_bgr,
                None,
                fx=self.upscale_factor,
                fy=self.upscale_factor,
                interpolation=cv2.INTER_LINEAR
            )
            scale_back = 1.0 / self.upscale_factor
        else:
            frame_proc = frame_bgr
            scale_back = 1.0

        rgb = cv2.cvtColor(frame_proc, cv2.COLOR_BGR2RGB)
        res = self.mp_face.process(rgb)
        out = []
        if res.detections:
            h, w = frame_proc.shape[:2]
            for det in res.detections:
                bbox = det.location_data.relative_bounding_box
                x1 = int(bbox.xmin * w)
                y1 = int(bbox.ymin * h)
                x2 = x1 + int(bbox.width * w)
                y2 = y1 + int(bbox.height * h)
                # Scale back to original frame if needed
                if scale_back != 1.0:
                    x1 = int(x1 * scale_back)
                    y1 = int(y1 * scale_back)
                    x2 = int(x2 * scale_back)
                    y2 = int(y2 * scale_back)
                score = float(det.score[0]) if det.score else 0.0
                if score >= self.min_confidence:
                    out.append(((x1, y1, x2, y2), score, "mediapipe"))
        return out

    # -------------------- main API --------------------
    def detect_multiple_faces(self, frame):
        """
        frame: BGR image
        returns: bool alert_triggered
        """
        h, w = frame.shape[:2]

        def _is_reflection(box):
            x1, y1, x2, y2 = box
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            return (cx > 0.80 * w) and (cy > 0.80 * h)

        # Run MediaPipe-only detection
        det_mp = self._detect_mediapipe(frame)

        filtered = []
        for d in det_mp:
            if not _is_reflection(d[0]):
                filtered.append(d)

        # visualization
        if self.show_debug_sources:
            for (x1, y1, x2, y2), score, source in filtered:
                color = (255, 0, 0)  # blue-ish for MediaPipe
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"{source}:{score:.2f}",
                            (x1, max(10, y1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        high_conf_faces = 0
        for (x1, y1, x2, y2), score, _ in filtered:
            area = max(0, x2 - x1) * max(0, y2 - y1)
            if area < self.min_area_px:
                continue
            high_conf_faces += 1
            if self.show_final_green:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"{score:.2f}",
                            (x1, y1 - 22 if self.show_debug_sources else y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # alert logic
        if high_conf_faces >= 2:
            self.consecutive_frames += 1
            if (self.consecutive_frames >= self.threshold) and self.alert_logger and not self.alert_triggered:
                self.alert_logger.log_alert(
                    "MULTIPLE_FACES",
                    f"detected. Only the candidate must be visible.",
                    frame
                )
                self.alert_triggered = True
        else:
            self.consecutive_frames = 0
            self.alert_triggered = False

        return self.alert_triggered

    def close(self):
        pass