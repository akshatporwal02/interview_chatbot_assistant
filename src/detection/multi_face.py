import cv2
import torch
from facenet_pytorch import MTCNN
import mediapipe as mp


class MultiFaceDetector:
    def __init__(
        self,
        config,
        show_debug_sources=True,   # colored boxes per detector (green=mtcnn, blue=mediapipe)
        show_final_green=True,     # classic green box for merged faces
        iou_threshold=0.35,        # relaxed threshold for merging
        min_face_size_mtcnn=12,    # smaller -> better far/small faces
        min_area_px=600            # ignore tiny noise after merge
    ):
        self.device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

        # --- MTCNN: better for small/far faces ---
        self.detector_mtcnn = MTCNN(
            keep_all=True,
            post_process=False,
            min_face_size=min_face_size_mtcnn,
            thresholds=[0.6, 0.7, 0.7],
            device=self.device
        )

        # --- MediaPipe: robust for partial/edge/occluded/profile faces ---
        self.mp_face = mp.solutions.face_detection.FaceDetection(
            model_selection=1,                # 0: short range, 1: full range
            min_detection_confidence=0.5
        )

        # alerting
        self.threshold = config['detection']['multi_face']['alert_threshold']
        self.consecutive_frames = 0
        self.alert_triggered = False
        self.alert_logger = None

        # viz + merge config
        self.show_debug_sources = show_debug_sources
        self.show_final_green = show_final_green
        self.iou_threshold = iou_threshold
        self.min_area_px = min_area_px

    def set_alert_logger(self, alert_logger):
        self.alert_logger = alert_logger

    # -------------------- helpers --------------------
    @staticmethod
    def _iou(box1, box2):
        """IoU between (x1,y1,x2,y2)."""
        x1, y1, x2, y2 = box1
        X1, Y1, X2, Y2 = box2

        ix1, iy1 = max(x1, X1), max(y1, Y1)
        ix2, iy2 = min(x2, X2), min(y2, Y2)

        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        if inter <= 0:
            return 0.0
        a1 = max(0, x2 - x1) * max(0, y2 - y1)
        a2 = max(0, X2 - X1) * max(0, Y2 - Y1)
        union = a1 + a2 - inter
        return inter / union if union > 0 else 0.0

    def _merge_detections(self, detections):
        """
        detections: list of (box, score, source)
        returns: merged list of (box, score, source)
        """
        merged = []
        for box, score, source in detections:
            matched = False
            for i, (m_box, m_score, m_source) in enumerate(merged):
                iou = self._iou(box, m_box)

                # centers
                cx, cy = (box[0]+box[2]) / 2, (box[1]+box[3]) / 2
                mcx, mcy = (m_box[0]+m_box[2]) / 2, (m_box[1]+m_box[3]) / 2
                center_dist = ((cx - mcx)**2 + (cy - mcy)**2) ** 0.5

                # check if center of one lies inside the other
                inside = (m_box[0] <= cx <= m_box[2]) and (m_box[1] <= cy <= m_box[3])

                if iou > self.iou_threshold or center_dist < 0.4 * (box[2]-box[0]) or inside:
                    # keep the higher-confidence one, prefer mtcnn if similar
                    if score > m_score or (abs(score - m_score) < 0.1 and source == "mtcnn"):
                        merged[i] = (box, score, source)
                    matched = True
                    break
            if not matched:
                merged.append((box, score, source))
        return merged

    # -------------------- detectors --------------------
    def _detect_mtcnn(self, frame_rgb):
        boxes, probs = self.detector_mtcnn.detect(frame_rgb)
        out = []
        if boxes is not None and probs is not None:
            for box, p in zip(boxes, probs):
                if p is None or p < 0.80:
                    continue
                x1, y1, x2, y2 = [int(v) for v in box]
                out.append(((x1, y1, x2, y2), float(p), "mtcnn"))
        return out

    def _detect_mediapipe(self, frame_bgr):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        res = self.mp_face.process(rgb)
        out = []
        if res.detections:
            h, w = frame_bgr.shape[:2]
            for det in res.detections:
                bbox = det.location_data.relative_bounding_box
                x1 = int(bbox.xmin * w)
                y1 = int(bbox.ymin * h)
                x2 = x1 + int(bbox.width * w)
                y2 = y1 + int(bbox.height * h)
                score = float(det.score[0]) if det.score else 0.0
                if score >= 0.50:
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

        # run detectors
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        det_mtcnn = self._detect_mtcnn(frame_rgb)
        det_mp = self._detect_mediapipe(frame)

        all_det = []
        for d in det_mtcnn + det_mp:
            if not _is_reflection(d[0]):
                all_det.append(d)

        merged = self._merge_detections(all_det)

        # visualization
        if self.show_debug_sources:
            for (x1, y1, x2, y2), score, source in merged:
                color = (0, 255, 0) if source == "mtcnn" else (255, 0, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"{source}:{score:.2f}",
                            (x1, max(10, y1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        high_conf_faces = 0
        for (x1, y1, x2, y2), score, _ in merged:
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
                    f"Alert! MULTIPLE FACES detected. Only the candidate must be visible.",
                    frame
                )
                self.alert_triggered = True
        else:
            self.consecutive_frames = 0
            self.alert_triggered = False

        return self.alert_triggered

    def close(self):
        pass