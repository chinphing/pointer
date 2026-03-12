"""
Inject current screen images into the prompt for the computer profile.
Image order: (1) raw screenshot, (2) annotated image with indices, then (3) 2x zoomed regions (default top 1/4; optional extra from user/model area).
Uses predict_and_annotate_all for detection; builds index_map (screen coordinates) for vision_actions tools.
Saves images under agents/computer/snapshots/<context_id>/.
Only the latest screen inject is sent to the LLM; earlier ones are replaced with a text placeholder to reduce token usage.
"""
from __future__ import annotations

import locale
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

from python.helpers.extension import Extension
from python.helpers import history, files, runtime

# Load computer agent modules by path (agents/computer is not a package)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)

import pyautogui  # noqa: E402
import rtree  # noqa: E402
import coord_convert  # noqa: E402
import screen as screen_mod  # noqa: E402
import som_util  # noqa: E402
import os_prompts  # noqa: E402


# Region keywords: (name, (x_frac_start, y_frac_start, x_frac_end, y_frac_end))
# Center is middle 50%×50%; quadrants are half-width, half-height.
# Key order matters for regex: 上方/下方/顶部/底部/top/bottom before 中央 so they match first.
QUADRANT_MAP = {
    "上方": (0, 0, 1, 0.5),
    "下方": (0, 0.5, 1, 1),
    "顶部": (0, 0, 1, 0.5),
    "底部": (0, 0.5, 1, 1),
    "top": (0, 0, 1, 0.5),
    "bottom": (0, 0.5, 1, 1),
    "top_left": (0, 0, 0.5, 0.5),
    "top-right": (0.5, 0, 1, 0.5),
    "top_right": (0.5, 0, 1, 0.5),
    "bottom_right": (0.5, 0.5, 1, 1),
    "bottom-right": (0.5, 0.5, 1, 1),
    "bottom_left": (0, 0.5, 0.5, 1),
    "bottom-left": (0, 0.5, 0.5, 1),
    "left": (0, 0, 0.5, 1),
    "right": (0.5, 0, 1, 1),
    "左上": (0, 0, 0.5, 0.5),
    "右上": (0.5, 0, 1, 0.5),
    "右下": (0.5, 0.5, 1, 1),
    "左下": (0, 0.5, 0.5, 1),
    "左侧": (0, 0, 0.5, 1),
    "右侧": (0.5, 0, 1, 1),
    "center": (0.25, 0.25, 0.75, 0.75),
    "central": (0.25, 0.25, 0.75, 0.75),
    "centre": (0.25, 0.25, 0.75, 0.75),
    "中央": (0.25, 0.25, 0.75, 0.75),
    "中间": (0.25, 0.25, 0.75, 0.75),
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


def _draw_mouse_overlay(pil_image: Image.Image, mouse_ix: int, mouse_iy: int) -> Image.Image:
    """Draw a small circle and crosshair at mouse position on a copy of the image. Returns new image."""
    out = pil_image.copy()
    if out.mode != "RGB":
        out = out.convert("RGB")
    draw = ImageDraw.Draw(out)
    r = 10
    x1, y1 = mouse_ix - r, mouse_iy - r
    x2, y2 = mouse_ix + r, mouse_iy + r
    draw.ellipse([x1, y1, x2, y2], outline=(255, 0, 0), width=3)
    draw.line([(mouse_ix - r - 2, mouse_iy), (mouse_ix + r + 2, mouse_iy)], fill=(255, 0, 0), width=2)
    draw.line([(mouse_ix, mouse_iy - r - 2), (mouse_ix, mouse_iy + r + 2)], fill=(255, 0, 0), width=2)
    return out


SCREEN_INJECT_PREVIEW = "<screen images>"
SCREEN_RAW_PREVIEW = "<screen raw>"
SCREEN_ANNOTATED_PREVIEW = "<screen annotated>"
SCREEN_ZOOMED_PREVIEW = "<screen zoomed>"


def _get_default_browser() -> str:
    env_browser = os.environ.get("BROWSER", "").strip()
    if env_browser:
        return env_browser
    try:
        if sys.platform == "darwin":
            r = subprocess.run(
                ["defaults", "read", "com.apple.LaunchServices/com.apple.launchservices.secure", "LSHandlers"],
                capture_output=True,
                timeout=2,
            )
            if r.returncode == 0:
                return "macOS default"
        if sys.platform == "win32":
            r = subprocess.run(
                ["reg", "query", "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\Shell\\Associations\\UrlAssociations\\http\\UserChoice", "/v", "ProgId"],
                capture_output=True,
                timeout=2,
            )
            if r.returncode == 0:
                return "Windows default"
    except Exception:
        pass
    return "not detected"


def _build_environment_text(screen_width: int = 0, screen_height: int = 0) -> str:
    now = datetime.now(timezone.utc).astimezone()
    loc = locale.getlocale()
    loc_str = f"{loc[0] or 'C'}_{loc[1] or ''}".rstrip("_") if loc else "C"
    parts = [
        f"OS: {platform.system()} {platform.release()} ({platform.machine()})",
        f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')} {now.tzname() or ''}",
        f"Timezone: {now.tzinfo and getattr(now.tzinfo, 'key', str(now.tzinfo)) or 'local'}",
        f"Locale: {loc_str}",
        f"Browser: {_get_default_browser()}",
    ]
    if screen_width and screen_height:
        parts.append(f"Primary screen (this capture): {screen_width}×{screen_height}")
    return "Environment: " + "; ".join(parts) + "."


# Reuse BoxAnnotator (and its RF-DETR model) across turns to avoid repeated model load
_annotator_cache: Optional[Any] = None


def _get_annotator() -> Any:
    global _annotator_cache
    if _annotator_cache is None:
        _annotator_cache = som_util.BoxAnnotator()
    return _annotator_cache


def _replace_older_screen_injects_with_placeholder(
    history_output: List[history.OutputMessage],
    keep_last: bool = True,
) -> None:
    """Replace screen-inject messages with text-only placeholder to reduce tokens.
    If keep_last is True, only the last screen inject is kept; otherwise all are replaced.
    For historical screen images: keep only raw screenshots (for before/after comparison),
    discard annotated and zoomed images to save tokens.
    """
    if not history_output:
        return

    # Track indices of different screen image types
    inject_indices: List[int] = []  # Full inject blocks (text + all images)
    raw_indices: List[int] = []       # Raw screenshot only
    annotated_indices: List[int] = []  # Annotated with indices
    zoomed_indices: List[int] = []    # Zoomed screenshot only (any zoomed preview)

    for i, out in enumerate(history_output):
        content = out.get("content")
        if not isinstance(content, dict):
            continue
        preview = content.get("preview", "")
        if preview == SCREEN_INJECT_PREVIEW:
            inject_indices.append(i)
        elif preview == SCREEN_RAW_PREVIEW:
            raw_indices.append(i)
        elif preview == SCREEN_ANNOTATED_PREVIEW:
            annotated_indices.append(i)
        elif isinstance(preview, str) and preview.startswith(SCREEN_ZOOMED_PREVIEW):
            zoomed_indices.append(i)

    # For annotated and zoomed: always replace older ones with placeholder (they're not needed for comparison)
    placeholder_text = history.RawMessage(
        raw_content=[{"type": "text", "text": "[Previous annotated/zoomed screen omitted to save tokens.]"}],
        preview="[Previous annotated screen omitted]",
    )
    for i in annotated_indices[:-1] if keep_last and annotated_indices else annotated_indices:
        history_output[i] = history.OutputMessage(ai=False, content=placeholder_text)
    for i in zoomed_indices[:-1] if keep_last and zoomed_indices else zoomed_indices:
        history_output[i] = history.OutputMessage(ai=False, content=placeholder_text)
    
    # For raw screenshots: keep the last one (for comparison), replace older ones with smaller placeholder
    if keep_last and raw_indices:
        to_replace_raw = raw_indices[:-1]
    else:
        to_replace_raw = raw_indices
    
    raw_placeholder = history.RawMessage(
        raw_content=[{"type": "text", "text": "[Previous raw screenshot for reference.]"}],
        preview="[Previous raw screenshot]",
    )
    for i in to_replace_raw:
        history_output[i] = history.OutputMessage(ai=False, content=raw_placeholder)
    
    # For full inject blocks: replace all but the last with placeholder
    inject_placeholder = history.RawMessage(
        raw_content=[{"type": "text", "text": "[Previous screen context omitted to save tokens.]"}],
        preview="[Previous screen context omitted]",
    )
    to_replace_inject = inject_indices[:-1] if keep_last and inject_indices else inject_indices
    for i in to_replace_inject:
        history_output[i] = history.OutputMessage(ai=False, content=inject_placeholder)


def _save_snapshots(
    context_id: str,
    raw_img: Image.Image,
    annotated_img: Image.Image,
    zoomed_imgs: Optional[List[Tuple[str, Image.Image]]] = None,
) -> Dict[str, str]:
    """Save debug images under agents/computer/snapshots/<context_id>/<timestamp>_*.png.
    Returns dict of saved paths: {'raw': path, 'annotated': path, 'zoom_<key>': path, ...}
    """
    result: Dict[str, str] = {}
    try:
        snapshots_base = files.get_abs_path("agents", "computer", "snapshots")
        run_dir = os.path.join(snapshots_base, context_id or "default")
        os.makedirs(run_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = os.path.join(run_dir, ts)
        raw_path = f"{prefix}_raw.png"
        annotated_path = f"{prefix}_annotated.png"
        raw_img.save(raw_path)
        annotated_img.save(annotated_path)
        result["raw"] = raw_path
        result["annotated"] = annotated_path
        if zoomed_imgs:
            for key, img in zoomed_imgs:
                safe_key = key.replace("/", "_").replace("\\", "_")
                zoom_path = f"{prefix}_zoom_{safe_key}.png"
                img.save(zoom_path)
                result[f"zoom_{safe_key}"] = zoom_path
    except Exception:
        pass
    return result


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
            _replace_older_screen_injects_with_placeholder(loop_data.history_output, keep_last=False)
            return

        mon_left, mon_top, mon_width, mon_height = mon_bbox
        w, h = img.size

        err_preview = ""
        annotator = _get_annotator()
        try:
            annotated_img, boxes_sorted = annotator.predict_and_annotate_all(
                img, threshold=0.1, overlap_threshold=0.1
            )
            boxes_sorted = list(boxes_sorted)
        except Exception as e:
            annotated_img = img
            boxes_sorted = []
            err_preview = f"Detection failed: {e}; no indices available."

        index_map: Dict[int, Dict[str, float]] = {}
        if boxes_sorted:
            for i, box in enumerate(boxes_sorted):
                x1, y1, x2, y2 = float(box[0]), float(box[1]), float(box[2]), float(box[3])
                cx = mon_left + (x1 + x2) / 2
                cy = mon_top + (y1 + y2) / 2
                left = mon_left + x1
                top = mon_top + y1
                right = mon_left + x2
                bottom = mon_top + y2
                index_map[i + 1] = {"x": cx, "y": cy, "left": left, "top": top, "right": right, "bottom": bottom}
            self.agent.set_data("computer_vision_index_map", index_map)
        else:
            self.agent.set_data("computer_vision_index_map", {})
            err_preview = "No interactive elements detected."

        # Coordinate system for absolute positioning: model outputs normalized; we convert to pixels when executing.
        coord_system = self.agent.get_data("computer_vision_coord_system") or "qwen"
        if coord_system not in coord_convert.list_systems():
            coord_system = "qwen"
        norm_range = "x and y in [0, 1000]" if coord_system == "qwen" else ("x and y in [0, 1]" if coord_system == "kimi" else "screenshot pixels")

        # Mouse position: draw on annotated image; show normalized coords in prompt so model sees same scale as its output
        mouse_ix, mouse_iy = None, None
        mouse_coords_str = "Mouse: position unavailable."
        try:
            mx, my = pyautogui.position()
            mouse_ix = mx - mon_left
            mouse_iy = my - mon_top
            if 0 <= mouse_ix < w and 0 <= mouse_iy < h:
                annotated_img = _draw_mouse_overlay(annotated_img, mouse_ix, mouse_iy)
                nx, ny = coord_convert.pixel_to_normalized(mouse_ix, mouse_iy, coord_system, w, h)
                mouse_coords_str = (
                    f"Current mouse position (normalized, same scale as your output): ({round(nx, 2)}, {round(ny, 2)}). "
                    "After an action, compare with the next turn mouse position to judge whether the click landed on target or deviated."
                )
            else:
                mouse_coords_str = "Mouse: outside captured area."
        except Exception:
            pass

        reference_bbox_text = ""
        if index_map and mouse_ix is not None and mouse_iy is not None:
            # Build rtree index: bbox in screenshot space (origin 0,0 top-left); id = index (1-based)
            idx_rtree = rtree.index.Index()
            im_boxes: Dict[int, Tuple[float, float, float, float]] = {}
            for idx in index_map:
                e = index_map[idx]
                x1 = float(e["left"]) - mon_left
                y1 = float(e["top"]) - mon_top
                x2 = float(e["right"]) - mon_left
                y2 = float(e["bottom"]) - mon_top
                im_boxes[idx] = (x1, y1, x2, y2)
                idx_rtree.insert(idx, (x1, y1, x2, y2))

            # Use rtree nearest to get 5 elements closest to the mouse (screenshot point)
            nearest_ids = list(idx_rtree.nearest((mouse_ix, mouse_iy, mouse_ix, mouse_iy), 5))
            nearest_items = [(i, im_boxes[i]) for i in nearest_ids]

            def _fmt_norm(items: List[Tuple[int, Tuple[float, float, float, float]]], iw: int, ih: int, sys: str) -> str:
                if not items:
                    return "none"
                parts = []
                for idx, (x1, y1, x2, y2) in items:
                    n1x, n1y = coord_convert.pixel_to_normalized(x1, y1, sys, iw, ih)
                    n2x, n2y = coord_convert.pixel_to_normalized(x2, y2, sys, iw, ih)
                    parts.append(f"index {idx} (x1,y1,x2,y2)=({round(n1x, 2)},{round(n1y, 2)},{round(n2x, 2)},{round(n2y, 2)})")
                return "; ".join(parts)

            reference_bbox_text = (
                " Reference bboxes (normalized, same scale as your output). 5 nearest marked elements to the mouse: "
                f"{_fmt_norm(nearest_items, w, h, coord_system)}. "
                "Coordinate-based principles: (1) Reference bbox must have explicit coordinates above and be very close to the target (within 50 pixels). "
                "(2) Derive x, y using the reference element as anchor; do not guess coordinates without a clear basis. "
                "(3) Generally: first hover_index to a marked element near the target, then use coordinate-based tools with inferred x, y. "
                "When inferring: decide whether the target is INSIDE or OUTSIDE the chosen reference bbox; This is very important for coordinate-based tools."
                f"Output x, y in the same normalized system: {norm_range}."
            )

        self.agent.set_data("computer_vision_coordinate_system", coord_system)
        self.agent.set_data(
            "computer_vision_screen_info",
            {
                "width": w,
                "height": h,
                "mon_left": mon_left,
                "mon_top": mon_top,
            },
        )

        prev_action_block: Optional[str] = None
        last_action = self.agent.data.get("computer_last_vision_action")
        last_goal = self.agent.data.get("computer_last_goal") or ""
        
        # Track consecutive failures - increment if same goal repeated
        failure_count = self.agent.data.get("computer_action_failure_count") or 0
        
        if last_action:
            goal = last_action.get("args", {}).get("goal", "")
            result = last_action.get("result", "")
            
            # If same goal was repeated, increment failure count
            if goal == last_goal and goal:
                failure_count = failure_count + 1
            else:
                failure_count = 1
            
            # Store current goal for next turn comparison
            self.agent.set_data("computer_last_goal", goal)
            
            # Build failure warning if too many consecutive failures
            failure_warning = ""
            if failure_count >= 3:
                failure_warning = (
                    f"⚠️ WARNING: {failure_count} consecutive attempts with same goal '{goal}' failed. "
                    "This approach is not working. Consider: (1) the target element may not exist or be accessible, "
                    "(2) the UI may have changed, (3) you need a completely different approach. "
                    "If stuck, use 'response' tool to inform user and ask for guidance instead of repeating failed actions. "
                )
            
            prev_action_block = (
                f"Previous action goal: {goal}. "
                f"Action state: {result}. "
                "Validate: Did the previous action achieve the goal? Check screenshot for expected changes. "
                "Only treat as success if the expected change is clearly visible. "
                "For coordinate-based positioning (click_at, type_text_at, etc.): each step that brings the pointer closer to the target counts as success; you may try up to 3 times—no need to hit the target in one shot. "
                "If unverified or failed: (1) retry the same action first (1–2 times), (2) then try a different method, (3) only after several attempts still fail may you conclude the goal was not achieved. "
                "Then output your next tool call (retry, alternative, or continue if verified)."
            )
            if failure_warning:
                prev_action_block = failure_warning + " " + prev_action_block
            
            # Update failure count
            self.agent.set_data("computer_action_failure_count", failure_count)
            self.agent.set_data("computer_last_vision_action", None)

        annotation_help = (
            "How to read the annotated image: each interactive element is wrapped in a colored box; "
            "the index number is shown in a small same-color label that may be above, below, to the left, or to the right of the box. "
            "Use the same color and proximity (position next to the box) to match the correct index to the target element. "
            "When multiple boxes could match the same target (e.g. a button inside a larger container), prefer the index whose bbox tightly wraps the target (smallest fit) for precise positioning; avoid the index of a larger bbox that merely contains it."
        )
        n_total = len(index_map)
        content = []
        env_text = _build_environment_text(w, h)
        content.append({"type": "text", "text": env_text})
        if prev_action_block:
            content.append({"type": "text", "text": prev_action_block})
        content.append({
            "type": "text",
            "text": (
                "Input types for this turn: "
                "(1) raw screenshot; "
                "(2) annotated screenshot with indices; "
                "(3) top-area 2x zoom from the annotated screenshot for index confirmation; "
                "(4) optional extra local 2x zooms for other regions when needed. "
                + annotation_help
                + f" Image size: {w}×{h} pixels. Origin: top-left (0,0). "
                + "The annotated image shows the current mouse cursor (red circle/crosshair). "
                + mouse_coords_str + "\n"
                + reference_bbox_text
                + " When referring to elements, describe their position (e.g. top-left, center, bottom-right)."
            ),
        })
        if not index_map and err_preview:
            content.append({"type": "text", "text": err_preview})

        # Add OS-specific shortcuts reference
        prompts_base_dir = os.path.join(_COMPUTER_DIR, "prompts")
        os_shortcuts = os_prompts.format_os_context(prompts_base_dir)
        if os_shortcuts:
            content.append({"type": "text", "text": os_shortcuts})

        # Build content blocks with proper LangChain format (list of dicts)
        # Each message's raw_content must be a list to satisfy HumanMessage validation
        
        # 1. Context text (environment, instructions, annotation help)
        context_content = content.copy()
        
        # 2. Raw screenshot - kept in history for comparison
        b64_raw = _pil_to_base64_jpeg(img)
        raw_img_content: List[Dict[str, Any]] = [
            {"type": "text", "text": "[Screen raw]"},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64_raw}"},
            },
        ]
        
        # 3. Annotated screenshot (indices for vision_actions)
        b64_annotated = _pil_to_base64_jpeg(annotated_img)
        annotated_img_content: List[Dict[str, Any]] = [
            {"type": "text", "text": "[Screen annotated]"},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64_annotated}"},
            },
        ]

        # 4. Zoomed screenshot - Always include top 1/4 from high-confidence image; add extra zoom if user specified a region
        # Default: always zoom top 1/4 because interactive elements are dense there
        zoomed_contents: List[Tuple[str, List[Dict[str, Any]]]] = []
        zoomed_for_snapshot: Optional[Tuple[str, Image.Image]] = None

        # Always generate top 1/4 zoom (fixed behavior)
        top_zoomed = _crop_quadrant_2x(annotated_img, "top")
        if top_zoomed is not None:
            zoomed_for_snapshot = ("top", top_zoomed)
            b64_top = _pil_to_base64_jpeg(top_zoomed)
            zoomed_contents.append(("top", [
                {"type": "text", "text": "[Screen zoomed] top, 2x (default focus area):"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_top}"}},
            ]))

        # Check if user/model mentioned a specific region (excluding top/upper which is default)
        user_msg = ""
        if loop_data.user_message and getattr(loop_data.user_message, "message", None):
            user_msg = loop_data.user_message.message or ""
        last_resp = (loop_data.last_response or "").lower()
        combined = f"{user_msg} {last_resp}"
        quadrant_key = _detect_quadrant_hint(combined)

        # Ignore top/upper region mentions since top is already default zoomed
        # Non-default regions: left, right, bottom, center, quadrants, etc.
        TOP_REGION_KEYS = {"top", "上方", "顶部"}
        if quadrant_key and quadrant_key not in TOP_REGION_KEYS:
            quadrant_key = quadrant_key.lower().replace("-", "_")
            if quadrant_key in QUADRANT_MAP:
                extra_zoomed = _crop_quadrant_2x(annotated_img, quadrant_key)
                if extra_zoomed is not None:
                    b64_extra = _pil_to_base64_jpeg(extra_zoomed)
                    zoomed_contents.append((quadrant_key, [
                        {"type": "text", "text": f"[Screen zoomed] {quadrant_key}, 2x:"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_extra}"}},
                    ]))

        context_id = getattr(self.agent.context, "id", None) or "default"
        # Build list of zoomed images for saving (extract from zoomed_contents)
        zoomed_imgs_to_save: List[Tuple[str, Image.Image]] = []
        for z_key, _ in zoomed_contents:
            if z_key == "top" and top_zoomed is not None:
                zoomed_imgs_to_save.append(("top", top_zoomed))
            elif z_key != "top":
                # Re-crop for non-top regions (or we could cache earlier)
                extra_img = _crop_quadrant_2x(annotated_img, z_key)
                if extra_img is not None:
                    zoomed_imgs_to_save.append((z_key, extra_img))
        saved_paths = _save_snapshots(context_id, img, annotated_img, zoomed_imgs_to_save)

        # In development mode, attach snapshot link to the last GEN log item
        if runtime.is_development() and saved_paths.get("annotated"):
            # Find the last agent log item and add snapshot link
            logs = self.agent.context.log.logs
            for log_item in reversed(logs):
                if hasattr(log_item, 'type') and log_item.type == "agent":
                    # Get existing kvps or create new
                    existing_kvps = dict(log_item.kvps) if log_item.kvps else {}
                    existing_kvps["snapshot"] = saved_paths["annotated"]
                    # Use update method to trigger state change notification
                    log_item.update(kvps=existing_kvps)
                    break

        # Inject as separate messages so history can selectively keep/discard
        # All contents are now properly formatted as lists for LangChain compatibility
        
        # 1. Context text (always kept as it's small and informative)
        context_msg = history.RawMessage(raw_content=context_content, preview=SCREEN_INJECT_PREVIEW)
        loop_data.history_output.append(history.OutputMessage(ai=False, content=context_msg))
        
        # 2. Raw screenshot (kept in history for before/after comparison)
        raw_msg = history.RawMessage(raw_content=raw_img_content, preview=SCREEN_RAW_PREVIEW)
        loop_data.history_output.append(history.OutputMessage(ai=False, content=raw_msg))
        
        # 3. Annotated screenshot
        annotated_msg = history.RawMessage(raw_content=annotated_img_content, preview=SCREEN_ANNOTATED_PREVIEW)
        loop_data.history_output.append(history.OutputMessage(ai=False, content=annotated_msg))

        # 4. Zoomed screenshots (default top 1/4 + optional extra regions)
        for z_key, z_content in zoomed_contents:
            zoomed_msg = history.RawMessage(raw_content=z_content, preview=f"{SCREEN_ZOOMED_PREVIEW} {z_key}")
            loop_data.history_output.append(history.OutputMessage(ai=False, content=zoomed_msg))

        _replace_older_screen_injects_with_placeholder(loop_data.history_output)
