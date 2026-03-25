"""
CAPTCHA verification: type, click, and drag flows; uses DaTi API for recognition then performs the action.
"""
from __future__ import annotations

import base64
import os
import platform
import random
import re
import sys
import time
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from agent import Agent, LoopData
from python.helpers.tool import Tool, Response

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)

import screen as screen_mod  # noqa: E402
from actions import ActionTools  # noqa: E402
import dati_client  # noqa: E402
import mouse_path  # noqa: E402
from mouse_move import CompositeMove, SimpleMove  # noqa: E402

from tools import vision_common as vc  # noqa: E402

# Points per segment and move interval (seconds)
BEZIER_POINTS = 10
# Curvature: 0 straight, 1 default (see mouse_path); None bend_sign = random left/right per segment
MOUSE_PATH_CURVATURE = 1.0
MOUSE_PATH_BEND_SIGN = None  # +1 / -1 fixes bend direction
# Tangential + normal jitter on p1/p2 (px); 0 off; None = mouse_path default (~2px)
MOUSE_PATH_CONTROL_JITTER_PX = 2.0
MOVE_INTERVAL = 0.03
DRAG_MOVE_INTERVAL = 0.02
# Random pause before each move (seconds), human-like pacing
PRE_MOVE_DELAY_MIN, PRE_MOVE_DELAY_MAX = 0.5, 1.5
# After reaching start (drag handle / first click target), jitter cursor ±N px a few times before down/click
PRE_REAL_MOVE_JITTER_STEPS = 3
PRE_REAL_MOVE_JITTER_RADIUS_PX = 10
PRE_REAL_MOVE_JITTER_SLEEP_MIN = 0.2
PRE_REAL_MOVE_JITTER_SLEEP_MAX = 0.5
# Total duration range for a single move (seconds)
MOVE_TOTAL_TIME_MIN, MOVE_TOTAL_TIME_MAX = 0.3, 1
# Slider drag duration (seconds): backends often check timing; too fast looks bot-like; ~0.35–0.8
SLIDER_TOTAL_TIME_MIN, SLIDER_TOTAL_TIME_MAX = 0.35, 0.75
# Path/time noise: perpendicular jitter (px), interval randomization factor
PATH_JITTER_PX = 2
INTERVAL_PERTURB_FACTOR = 0.2
CLICK_DELAY_MIN, CLICK_DELAY_MAX = 1.0, 5.0
QUERY_TIMEOUT = 60.0

# Click / non-jitter segments: easing + interval noise, no path jitter (CompositeMove path_jitter_max_px=0)
_CAPTCHA_MOVE_COMPOSITE = CompositeMove(
    path_jitter_max_px=0.0,
    default_interval=MOVE_INTERVAL,
    interval_perturb_factor=INTERVAL_PERTURB_FACTOR,
)
# Slider main path: Bezier + normal jitter + same interval policy
_CAPTCHA_MOVE_SLIDER = CompositeMove(
    path_jitter_max_px=PATH_JITTER_PX,
    default_interval=MOVE_INTERVAL,
    interval_perturb_factor=INTERVAL_PERTURB_FACTOR,
)
_CAPTCHA_MOVE_SIMPLE = SimpleMove(
    default_interval=DRAG_MOVE_INTERVAL,
    curvature=MOUSE_PATH_CURVATURE,
    bend_sign=MOUSE_PATH_BEND_SIGN,
    control_jitter_px=MOUSE_PATH_CONTROL_JITTER_PX,
)


def _apply_mouse_plan(path: List[Tuple[float, float]], intervals: List[float]) -> None:
    """Execute pointer moves from mouse_move path + intervals (decoupled from path generation)."""
    import pyautogui

    for (x, y), dt in zip(path, intervals):
        pyautogui.moveTo(int(round(x)), int(round(y)))
        time.sleep(dt)


def _mouse_jitter_near_cursor(jitter_radius_px: int = PRE_REAL_MOVE_JITTER_RADIUS_PX) -> None:
    """Move to random points within ±jitter_radius_px of cursor (no eased path)."""
    import pyautogui

    w, h = pyautogui.size()
    ox, oy = (int(pyautogui.position()[0]), int(pyautogui.position()[1]))
    r = jitter_radius_px
    for _ in range(PRE_REAL_MOVE_JITTER_STEPS):
        nx = ox + random.randint(-r, r)
        ny = oy + random.randint(-r, r)
        nx = max(0, min(w - 1, nx))
        ny = max(0, min(h - 1, ny))
        pyautogui.moveTo(nx, ny)
        time.sleep(random.uniform(PRE_REAL_MOVE_JITTER_SLEEP_MIN, PRE_REAL_MOVE_JITTER_SLEEP_MAX))


def _captcha_log(agent: Any, message: str) -> None:
    """Append a simple info log for CAPTCHA progress (e.g. recognizing, done)."""
    if not agent or not getattr(agent, "context", None):
        return
    try:
        agent.context.log.log(type="info", content=message)
    except Exception:
        pass


def _get_dati_config(agent: Any) -> Dict[str, Any]:
    """Read DaTi config from current system settings (Settings UI / usr/settings.json) at call time so UI-saved values apply without restart. dati_client._config merges with env for missing keys."""
    from python.helpers import settings
    current = settings.get_settings()
    api_url = (current.get("dati_api_url") or "").strip() or None
    authcode = (current.get("dati_authcode") or "").strip() or None
    typeno = (current.get("dati_typeno") or "").strip() or None
    author = (current.get("dati_author") or "").strip() or None
    return {"api_url": api_url, "authcode": authcode, "typeno": typeno, "author": author}


def _crop_captcha_and_encode(
    agent: Any,
    index_captcha_area: int,
) -> Tuple[Optional[str], Optional[Response]]:
    """Screenshot current monitor, crop index_captcha_area; return base64 with data:image/png;base64, prefix."""
    index_map, err = vc.get_index_map(agent)
    if err is not None:
        return None, err
    if index_captcha_area not in index_map:
        return None, Response(
            message=f"index_captcha_area {index_captcha_area} not in index_map.",
            break_loop=False,
        )
    try:
        img, mon_bbox = screen_mod.screenshot_current_monitor()
    except Exception as e:
        return None, Response(message=f"Screenshot failed: {e}", break_loop=False)
    mon_left, mon_top = int(mon_bbox[0]), int(mon_bbox[1])
    entry = index_map[index_captcha_area]
    left = int(round(float(entry["left"])))
    top = int(round(float(entry["top"])))
    right = int(round(float(entry["right"])))
    bottom = int(round(float(entry["bottom"])))
    # Crop box in screenshot pixel coords
    w, h = img.size
    c_left = max(0, min(left - mon_left, w - 1))
    c_top = max(0, min(top - mon_top, h - 1))
    c_right = max(c_left + 1, min(right - mon_left, w))
    c_bottom = max(c_top + 1, min(bottom - mon_top, h))
    print(
        f"[captcha_area] index_captcha_area={index_captcha_area} "
        f"screen_bbox=({left}, {top}, {right}, {bottom}) "
        f"crop_on_image=({c_left}, {c_top}, {c_right}, {c_bottom}) size={c_right - c_left}x{c_bottom - c_top}"
    )
    crop = img.crop((c_left, c_top, c_right, c_bottom))
    buf = BytesIO()
    crop.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}", None


def _upload_and_query(
    agent: Any,
    base64string: str,
    remark: str,
) -> Tuple[Optional[str], Optional[Response]]:
    """Upload CAPTCHA and poll for answer (default timeout 1 min). Returns answer string or error Response."""
    cfg = _get_dati_config(agent)
    # Effective config: settings + env fallback (so UI-saved or env both work)
    effective = dati_client._config(
        cfg.get("api_url"),
        cfg.get("authcode"),
        cfg.get("typeno"),
        cfg.get("author"),
    )
    api_url = effective.get("api_url")
    authcode = effective.get("authcode")
    typeno = effective.get("typeno")
    author = effective.get("author")
    if not authcode or not typeno or not author:
        return None, Response(
            message="DaTi config missing: set dati_authcode, dati_typeno, dati_author in Settings → Agent → CAPTCHA / DaTi (or env DATI_AUTHCODE, DATI_TYPENO, DATI_AUTHOR).",
            break_loop=False,
        )
    out = dati_client.upload(
        base64string,
        remark,
        api_url=api_url,
        authcode=authcode,
        typeno=typeno,
        author=author,
    )
    if out.get("status") != 0:
        return None, Response(
            message=dati_client.format_dati_error(out.get("status"), out.get("msg")),
            break_loop=False,
        )
    subjectno = out.get("msg")
    if not subjectno:
        return None, Response(message="Upload returned no task id.", break_loop=False)
    answer, query_err = dati_client.query_until_ready(
        str(subjectno),
        timeout_seconds=QUERY_TIMEOUT,
        api_url=api_url,
        authcode=authcode,
    )
    print(f"[dtsdk] query raw result (answer string): {answer!r}")
    if query_err:
        return None, Response(message=query_err, break_loop=False)
    if not answer:
        return None, Response(
            message="Query returned empty answer.",
            break_loop=False,
        )
    return answer, None


def _parse_coords_result(answer: str) -> List[Tuple[int, int]]:
    """Parse '2,143|64,82|160,44|228,52' into [(2,143), (64,82), ...]."""
    out = []
    for part in re.split(r"[\|\\|\s]+", answer.strip()):
        part = part.strip()
        if not part:
            continue
        if "," in part:
            a, b = part.split(",", 1)
            try:
                out.append((int(a.strip()), int(b.strip())))
            except ValueError:
                continue
    return out


def _relative_to_screen(
    index_map: Dict[int, Dict[str, float]],
    index_captcha_area: int,
    relative_points: List[Tuple[int, int]],
) -> List[List[int]]:
    """Convert coordinates relative to CAPTCHA bbox to screen coordinates."""
    entry = index_map[index_captcha_area]
    left = int(round(float(entry["left"])))
    top = int(round(float(entry["top"])))
    return [[left + rx, top + ry] for rx, ry in relative_points]


def _do_type(
    tool: "CaptchaVerifyTool",
    args: Dict[str, Any],
    goal: str,
) -> Response:
    index_captcha_area = args.get("index_captcha_area")
    index_input_area = args.get("index_input_area")
    remark = args.get("remark", "")
    if index_captcha_area is None:
        return Response(message="Missing index_captcha_area.", break_loop=False)
    if index_input_area is None:
        return Response(message="Missing index_input_area for type.", break_loop=False)
    try:
        index_captcha_area = int(index_captcha_area)
        index_input_area = int(index_input_area)
    except (TypeError, ValueError):
        return Response(message="index_captcha_area and index_input_area must be integers.", break_loop=False)
    b64, err = _crop_captcha_and_encode(tool.agent, index_captcha_area)
    if err is not None:
        return err
    _captcha_log(tool.agent, "CAPTCHA recognizing…")
    answer, err = _upload_and_query(tool.agent, b64, remark)
    if err is not None:
        return err
    _captcha_log(tool.agent, "CAPTCHA solved")
    index_map, err = vc.get_index_map(tool.agent)
    if err is not None:
        return err
    pos = vc.resolve_index(index_map, index_input_area)
    _captcha_log(tool.agent, "Human-like input")
    actions = ActionTools(dry_run=False, paste_key=["command", "v"] if platform.system() == "Darwin" else ["ctrl", "v"])
    actions._click(pos)
    time.sleep(0.1)
    actions._type_text(answer, clear_field_first=True)
    _captcha_log(tool.agent, "Done")
    return Response(
        message=(
            f"Goal: {goal}. Type action executed, cleared first. Please verify result on next screenshot."
        ),
        break_loop=False,
    )


def _do_click(
    tool: "CaptchaVerifyTool",
    args: Dict[str, Any],
    goal: str,
) -> Response:
    index_captcha_area = args.get("index_captcha_area")
    remark = args.get("remark", "")
    if index_captcha_area is None:
        return Response(message="Missing index_captcha_area.", break_loop=False)
    try:
        index_captcha_area = int(index_captcha_area)
    except (TypeError, ValueError):
        return Response(message="index_captcha_area must be integer.", break_loop=False)
    b64, err = _crop_captcha_and_encode(tool.agent, index_captcha_area)
    if err is not None:
        return err
    _captcha_log(tool.agent, "CAPTCHA recognizing…")
    answer, err = _upload_and_query(tool.agent, b64, remark)
    if err is not None:
        return err
    _captcha_log(tool.agent, "CAPTCHA solved")
    rel = _parse_coords_result(answer)
    if not rel:
        return Response(message="No coordinates in answer.", break_loop=False)
    index_map, err = vc.get_index_map(tool.agent)
    if err is not None:
        return err
    screen_points = _relative_to_screen(index_map, index_captcha_area, rel)
    _captcha_log(tool.agent, "Human-like moves")
    import pyautogui
    actions = ActionTools(dry_run=False, paste_key=["command", "v"] if platform.system() == "Darwin" else ["ctrl", "v"])
    for i, target in enumerate(screen_points):
        # Random pause before each move (human-like pacing)
        time.sleep(PRE_MOVE_DELAY_MIN + random.random() * (PRE_MOVE_DELAY_MAX - PRE_MOVE_DELAY_MIN))
        current = pyautogui.position()
        path_pts = mouse_path.mouse_path(
            [current[0], current[1]],
            target,
            num_points=BEZIER_POINTS,
            curvature=MOUSE_PATH_CURVATURE,
            bend_sign=MOUSE_PATH_BEND_SIGN,
            control_jitter_px=MOUSE_PATH_CONTROL_JITTER_PX,
        )
        # Move duration; intervals from CompositeMove (ease-out + time noise)
        total_time = MOVE_TOTAL_TIME_MIN + random.random() * (MOVE_TOTAL_TIME_MAX - MOVE_TOTAL_TIME_MIN)
        p, iv = _CAPTCHA_MOVE_COMPOSITE.plan(path_pts, total_time=total_time)
        _apply_mouse_plan(p, iv)
        actions._click(target)

        if i < len(screen_points) - 1:
            jitter_radius_px = int(PRE_REAL_MOVE_JITTER_RADIUS_PX / (i + 1))
            _mouse_jitter_near_cursor(jitter_radius_px)
    _captcha_log(tool.agent, "Done")
    return Response(
        message=f"Goal: {goal}. Clicked {len(screen_points)} point(s). Verify on next screenshot.",
        break_loop=False,
    )


def _do_drag(
    tool: "CaptchaVerifyTool",
    args: Dict[str, Any],
    goal: str,
) -> Response:
    index_captcha_area = args.get("index_captcha_area")
    remark = args.get("remark", "")
    if index_captcha_area is None:
        return Response(message="Missing index_captcha_area.", break_loop=False)
    try:
        index_captcha_area = int(index_captcha_area)
    except (TypeError, ValueError):
        return Response(message="index_captcha_area must be integer.", break_loop=False)
    b64, err = _crop_captcha_and_encode(tool.agent, index_captcha_area)
    if err is not None:
        return err
    _captcha_log(tool.agent, "CAPTCHA recognizing…")
    answer, err = _upload_and_query(tool.agent, b64, remark)
    if err is not None:
        return err
    _captcha_log(tool.agent, "CAPTCHA solved")
    rel = _parse_coords_result(answer)
    if len(rel) < 2:
        return Response(message="Drag requires at least 2 coordinates in answer.", break_loop=False)
    index_map, err = vc.get_index_map(tool.agent)
    if err is not None:
        return err
    screen_points = _relative_to_screen(index_map, index_captcha_area, rel)
    is_slider = bool(args.get("is_slider"))
    if is_slider and screen_points:
        from python.helpers import settings as _settings_mod
        offset_px = int(_settings_mod.get_settings().get("captcha_slider_offset_px", 0))
        screen_points = list(screen_points)
        screen_points[-1] = [int(screen_points[-1][0]) + offset_px, int(screen_points[-1][1])]
    _captcha_log(tool.agent, "Human-like drag")
    # Chain points into one Bezier path; slider adds jitter + eased duration for backend checks
    full_path = mouse_path.mouse_path_through_points(
        [[float(p[0]), float(p[1])] for p in screen_points],
        num_points_per_segment=BEZIER_POINTS,
        curvature=MOUSE_PATH_CURVATURE,
        bend_sign=MOUSE_PATH_BEND_SIGN,
        control_jitter_px=MOUSE_PATH_CONTROL_JITTER_PX,
    )
    if not full_path:
        return Response(message="Path generation failed.", break_loop=False)
    import pyautogui
    time.sleep(PRE_MOVE_DELAY_MIN + random.random() * (PRE_MOVE_DELAY_MAX - PRE_MOVE_DELAY_MIN))
    current = pyautogui.position()
    to_start = mouse_path.mouse_path(
        [current[0], current[1]],
        [full_path[0][0], full_path[0][1]],
        num_points=BEZIER_POINTS,
        curvature=MOUSE_PATH_CURVATURE,
        bend_sign=MOUSE_PATH_BEND_SIGN,
        control_jitter_px=MOUSE_PATH_CONTROL_JITTER_PX,
    )
    total_time = MOVE_TOTAL_TIME_MIN + random.random() * (MOVE_TOTAL_TIME_MAX - MOVE_TOTAL_TIME_MIN)
    p0, iv0 = _CAPTCHA_MOVE_COMPOSITE.plan(to_start, total_time=total_time)
    _apply_mouse_plan(p0, iv0)
    
    pyautogui.mouseDown()
    time.sleep(0.05)
    if is_slider:
        slider_time = SLIDER_TOTAL_TIME_MIN + random.random() * (SLIDER_TOTAL_TIME_MAX - SLIDER_TOTAL_TIME_MIN)
        ps, ivs = _CAPTCHA_MOVE_SLIDER.plan(
            full_path[1:],
            total_time=slider_time,
            ease_in_out=True,
            perturb_intervals=True,
        )
        _apply_mouse_plan(ps, ivs)
    else:
        pd, ivd = _CAPTCHA_MOVE_SIMPLE.plan(full_path[1:], interval=DRAG_MOVE_INTERVAL)
        _apply_mouse_plan(pd, ivd)
    time.sleep(0.05)
    pyautogui.mouseUp()
    time.sleep(0.1)
    _captcha_log(tool.agent, "Done")
    return Response(
        message=f"Goal: {goal}. Drag along {len(screen_points)} point(s). Verify on next screenshot.",
        break_loop=False,
    )


class CaptchaVerifyTool(Tool):
    """CAPTCHA verification: type (text), click (pick), drag (slider/path)."""

    async def execute(self, **kwargs: Any) -> Response:
        args = dict(self.args or {})
        for k, v in kwargs.items():
            if v is not None:
                args[k] = v
        goal = str(args.get("goal", "")).strip()
        method = (self.method or "").strip()
        if method == "type":
            return _do_type(self, args, goal or "captcha type")
        if method == "click":
            return _do_click(self, args, goal or "captcha click")
        if method == "drag":
            return _do_drag(self, args, goal or "captcha drag")
        return Response(
            message="Use method: type, click, or drag.",
            break_loop=False,
        )
