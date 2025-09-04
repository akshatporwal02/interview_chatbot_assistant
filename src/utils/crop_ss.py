# import cv2
# import numpy as np

# def get_big_tile_crop(page, daily_frame, iframe_element, full_screenshot_bgr, selector="div.tile-info"):
#     """
#     From a full screenshot (BGR), return only the big tile region for detection.
#     Returns: cropped_bgr (tile) or None
#     """
#     if not (page and daily_frame and iframe_element and full_screenshot_bgr is not None):
#         return None

#     try:
#         # Get bounding box of tile in iframe coordinates
#         rect = daily_frame.evaluate(f"""sel => {{
#             const el = document.querySelector(sel);
#             if (!el) return null;
#             const r = el.getBoundingClientRect();
#             return {{ x: r.x, y: r.y, width: r.width, height: r.height }};
#         }}""", selector)
#         if not rect:
#             return None

#         # Get iframe offset on page
#         iframe_box = iframe_element.bounding_box()
#         if not iframe_box:
#             return None

#         # Adjust for iframe offset
#         x = int(rect["x"] + iframe_box["x"])
#         y = int(rect["y"] + iframe_box["y"])
#         w = int(rect["width"])
#         h = int(rect["height"])

#         H, W = full_screenshot_bgr.shape[:2]
#         x, y = max(0, x), max(0, y)
#         w, h = min(w, W - x), min(h, H - y)

#         if w <= 0 or h <= 0:
#             return None

#         return full_screenshot_bgr[y:y+h, x:x+w]

#     except Exception as e:
#         print(f"⚠️ Failed to crop big tile: {e}")
#         return None

import cv2
import numpy as np

def get_big_tile_crop(page, daily_frame, iframe_element, full_screenshot_bgr, selector="div.tile-info"):
    """
    From a full screenshot (BGR), return only the big tile region for detection.
    Also removes the small overlay tile (mini self-view) if present.
    Returns: cropped_bgr (tile) or None
    """
    if not (page and daily_frame and iframe_element and full_screenshot_bgr is not None):
        return None

    try:
        # Get bounding box of tile in iframe coordinates
        rect = daily_frame.evaluate(f"""sel => {{
            const el = document.querySelector(sel);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {{ x: r.x, y: r.y, width: r.width, height: r.height }};
        }}""", selector)
        if not rect:
            return None

        # Get iframe offset on page
        iframe_box = iframe_element.bounding_box()
        if not iframe_box:
            return None

        # Adjust for iframe offset
        x = int(rect["x"] + iframe_box["x"])
        y = int(rect["y"] + iframe_box["y"])
        w = int(rect["width"])
        h = int(rect["height"])

        H, W = full_screenshot_bgr.shape[:2]
        x, y = max(0, x), max(0, y)
        w, h = min(w, W - x), min(h, H - y)

        if w <= 0 or h <= 0:
            return None

        # Crop the big tile region
        big_tile = full_screenshot_bgr[y:y+h, x:x+w].copy()

        # --- Remove the small overlay (usually top-left) ---
        overlay_h = int(h * 0.5)  # 50% of big tile height
        overlay_w = int(w * 0.25)  # 25% of big tile width

        # Black out overlay area
        big_tile[0:overlay_h, 0:overlay_w] = (0, 0, 0)

        return big_tile

    except Exception as e:
        print(f"⚠️ Failed to crop big tile: {e}")
        return None


