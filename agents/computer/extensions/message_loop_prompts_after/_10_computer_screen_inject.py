"""
Inject current screen images into the prompt for the computer profile.
Adds: raw screenshot, annotated screenshot (with L-R T-B indices), and optionally
a 2x zoomed region when user or model specified an area (top_left, top_right, bottom_right, bottom_left, or center).
Also builds index_map (screen coordinates) for vision_actions tools.
Saves each image under agents/computer/snapshots/<context_id>/ for debugging.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from python.helpers.extension import Extension
from python.helpers import history, files

# Load computer agent modules by path (agents/computer is not a package)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)

import screen as screen_mod  # noqa: E402
import som_util  # noqa: E402


# Region keywords: (name, (x_frac_start, y_frac_start, x_frac_end, y_frac_end))
# Center is middle 50%×50%; quadrants are half-width, half-height.
QUADRANT_MAP = {
    "top_left": (0, 0, 0.5, 0.5),
    "top-right": (0.5, 0, 1, 0.5),
    "top_right": (0.5, 0, 1, 0.5),
    "bottom_right": (0.5, 0.5, 1, 1),
    "bottom-right": (0.5, 0.5, 1, 1),
    "bottom_left": (0, 0.5, 0.5, 1),
    "bottom-left": (0, 0.5, 0.5, 1),
    "left": (0, 0, 0.5, 1),
    "right": (0.5, 0, 1, 1),
    "center": (0.25, 0.25, 0.75, 0.75),
    "central": (0.25, 0.25, 0.75, 0.75),
    "centre": (0.25, 0.25, 0.75, 0.75),
    "中央": (0.25, 0.25, 0.75, 0.75),
    "中间": (0.25, 0.25, 0.75, 0.75),
    "左上": (0, 0, 0.5, 0.5),
    "右上": (0.5, 0, 1, 0.5),
    "右下": (0.5, 0.5, 1, 1),
    "左下": (0, 0.5, 0.5, 1),
}

QUADRANT_PATTERN = re.compile(
    "|".join(re.escape(k) for k in QUADRANT_MAP.keys()), re.I
)


def _detect_quadrant_hint(text: str) -> Optional[str]:
    """Return first matching quadrant key from text, or None."""
    if not text:
        return None
    m = QUADRANT_PATTERN.search(text)
    if m:
        return m.group(0).lower().replace("-", "_")
    return None


def _crop_quadrant_2x(pil_img: Image.Image, quadrant_key: str) -> Optional[Image.Image]:
    """Crop the quadrant region and resize to 2x. Returns None if key unknown."""
    if quadrant_key not in QUADRANT_MAP:
        return None
    x0, y0, x1, y1 = QUADRANT_MAP[quadrant_key]
    w, h = pil_img.size
    box = (
        int(x0 * w),
        int(y0 * h),
        int(x1 * w),
        int(y1 * h),
    )
    crop = pil_img.crop(box)
    new_w = crop.width * 2
    new_h = crop.height * 2
    return crop.resize((new_w, new_h), Image.Resampling.LANCZOS)


def _pil_to_base64_jpeg(pil_img: Image.Image, quality: int = 85) -> str:
    buf = BytesIO()
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")
    pil_img.save(buf, format="JPEG", quality=quality)
    import base64
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _save_snapshots(
    context_id: str,
    raw_img: Image.Image,
    annotated_img: Image.Image,
    zoomed_img: Optional[Tuple[str, Image.Image]] = None,
) -> None:
    """Save debug images under agents/computer/snapshots/<context_id>/<timestamp>_*.png."""
    try:
        snapshots_base = files.get_abs_path("agents", "computer", "snapshots")
        run_dir = os.path.join(snapshots_base, context_id or "default")
        os.makedirs(run_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = os.path.join(run_dir, ts)
        raw_img.save(f"{prefix}_raw.png")
        annotated_img.save(f"{prefix}_annotated.png")
        if zoomed_img is not None:
            key, img = zoomed_img
            safe_key = key.replace("/", "_").replace("\\", "_")
            img.save(f"{prefix}_zoom_{safe_key}.png")
    except Exception:
        pass


class ComputerScreenInject(Extension):
    async def execute(self, loop_data=None, **kwargs: Any) -> None:
        if loop_data is None:
            return
        if getattr(self.agent.config, "profile", "") != "computer":
            return

        try:
            img, mon_bbox = screen_mod.screenshot_current_monitor()
        except Exception as e:
            err_msg = f"Screen capture failed: {e}"
            raw = history.RawMessage(raw_content=[{"type": "text", "text": err_msg}], preview=err_msg)
            loop_data.history_output.append(history.OutputMessage(ai=False, content=raw))
            return

        mon_left, mon_top, mon_width, mon_height = mon_bbox
        w, h = img.size

        err_preview = ""
        try:
            annotator = som_util.BoxAnnotator()
            boxes, _scores = annotator.predict(img, threshold=0.35)
            boxes = list(boxes) if boxes is not None else []
        except Exception as e:
            boxes = []
            err_preview = f"Detection failed: {e}; no indices available."

        index_map: Dict[int, Dict[str, float]] = {}
        if boxes:
            sorted_boxes = som_util.sort_boxes_lrtb(boxes, h)
            annotated_img = annotator.annotate(sorted_boxes, img)
            for i, box in enumerate(sorted_boxes):
                x1, y1, x2, y2 = float(box[0]), float(box[1]), float(box[2]), float(box[3])
                cx = mon_left + (x1 + x2) / 2
                cy = mon_top + (y1 + y2) / 2
                index_map[i + 1] = {"x": cx, "y": cy}
            self.agent.set_data("computer_vision_index_map", index_map)
        else:
            annotated_img = img
            self.agent.set_data("computer_vision_index_map", {})
            err_preview = "No interactive elements detected."

        content: List[Dict[str, Any]] = [
            {"type": "text", "text": "Current screen: (1) raw, (2) annotated with indices. Use the numbers on the annotated image for tool calls. When referring to elements, describe their position (e.g. top-left, center, bottom-right, 左上/右上/左下/右下) to help target them accurately."}
        ]
        if not index_map and err_preview:
            content.append({"type": "text", "text": err_preview})

        for im in [img, annotated_img]:
            b64 = _pil_to_base64_jpeg(im)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })

        user_msg = ""
        if loop_data.user_message and getattr(loop_data.user_message, "message", None):
            user_msg = loop_data.user_message.message or ""
        last_resp = (loop_data.last_response or "").lower()
        combined = f"{user_msg} {last_resp}"
        quadrant_key = _detect_quadrant_hint(combined)
        if quadrant_key:
            quadrant_key = quadrant_key.lower().replace("-", "_")
        zoomed_for_snapshot: Optional[Tuple[str, Image.Image]] = None
        if quadrant_key and quadrant_key in QUADRANT_MAP:
            zoomed = _crop_quadrant_2x(annotated_img, quadrant_key)
            if zoomed is not None:
                zoomed_for_snapshot = (quadrant_key, zoomed)
                b64_zoom = _pil_to_base64_jpeg(zoomed)
                content.append({"type": "text", "text": f"Zoomed quadrant ({quadrant_key}), 2x:"})
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64_zoom}"},
                })

        context_id = getattr(self.agent.context, "id", None) or "default"
        _save_snapshots(context_id, img, annotated_img, zoomed_for_snapshot)

        raw = history.RawMessage(raw_content=content, preview="<screen images>")
        loop_data.history_output.append(history.OutputMessage(ai=False, content=raw))
