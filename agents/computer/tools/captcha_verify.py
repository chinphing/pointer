"""
验证码验证工具：支持输入型、点选型、拖动型；调用 DaTi 接口获取结果后执行对应操作。
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

from tools import vision_common as vc  # noqa: E402

# 轨迹每段插值点数、移动间隔（秒）
BEZIER_POINTS = 10
MOVE_INTERVAL = 0.03
DRAG_MOVE_INTERVAL = 0.02
# 每次移动到目标前的随机等待（秒），模拟人工节奏
PRE_MOVE_DELAY_MIN, PRE_MOVE_DELAY_MAX = 0.5, 1.0
# 单次移动总时长范围（秒）
MOVE_TOTAL_TIME_MIN, MOVE_TOTAL_TIME_MAX = 0.1, 0.35
# 滑块滑动总时长（秒）：后端常校验耗时，过短会被判异常，建议 0.35～0.8
SLIDER_TOTAL_TIME_MIN, SLIDER_TOTAL_TIME_MAX = 0.35, 0.75
# 轨迹/时间扰动：路径点垂直方向抖动像素、每段间隔随机波动比例
PATH_JITTER_PX = 2
INTERVAL_PERTURB_FACTOR = 0.2
CLICK_DELAY_MIN, CLICK_DELAY_MAX = 1.0, 5.0
QUERY_TIMEOUT = 60.0


def _captcha_log(agent: Any, message: str) -> None:
    """Append a simple info log to the agent context for captcha progress (e.g. 识别中, 识别完成)."""
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
    """截取当前屏幕并裁剪 index_captcha_area 区域，返回 base64 字符串（带 data:image/png;base64, 前缀）。"""
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
    # 裁剪框在截图上的像素
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
    """上传验证码并轮询答案，超时 1 分钟。返回答案字符串或错误 Response。"""
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
            message=out.get("msg") or "Upload failed.",
            break_loop=False,
        )
    subjectno = out.get("msg")
    if not subjectno:
        return None, Response(message="Upload returned no task id.", break_loop=False)
    answer = dati_client.query_until_ready(
        str(subjectno),
        timeout_seconds=QUERY_TIMEOUT,
        api_url=api_url,
        authcode=authcode,
    )
    print(f"[dtsdk] query raw result (answer string): {answer!r}")
    if answer is None:
        return None, Response(
            message="Query timeout or failed within 60s.",
            break_loop=False,
        )
    return answer, None


def _parse_coords_result(answer: str) -> List[Tuple[int, int]]:
    """解析 '2,143|64,82|160,44|228,52' 为 [(2,143), (64,82), ...]。"""
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
    """将相对验证码区域的坐标转为屏幕坐标。"""
    entry = index_map[index_captcha_area]
    left = int(round(float(entry["left"])))
    top = int(round(float(entry["top"])))
    return [[left + rx, top + ry] for rx, ry in relative_points]


def _ease_out_intervals(n: int, total_time: float) -> List[float]:
    """先快后慢：返回 n 个间隔（秒），和为 total_time。前期间隔短、后期间隔长，更接近人类移动。"""
    if n <= 0:
        return []
    if n == 1:
        return [total_time]
    import math
    intervals = []
    for i in range(n):
        progress_after = (i + 1) / n
        progress_before = i / n
        t_after = 1.0 - math.sqrt(max(0, 1.0 - progress_after))
        t_before = 1.0 - math.sqrt(max(0, 1.0 - progress_before))
        intervals.append(total_time * (t_after - t_before))
    return intervals


def _ease_in_out_intervals(n: int, total_time: float) -> List[float]:
    """起步和结束都慢、中间快（ease-in-out），加速度变化更明显，适合滑块轨迹校验。"""
    if n <= 0:
        return []
    if n == 1:
        return [total_time]
    import math
    # 平滑的 ease-in-out：前半段 ease-in，后半段 ease-out
    intervals = []
    for i in range(n):
        progress_after = (i + 1) / n
        progress_before = i / n
        # 使用 smoothstep 近似: 3t^2 - 2t^3，归一化时间 t 与 progress 关系
        def progress_to_t(p: float) -> float:
            if p <= 0.5:
                return 2 * p * p
            return 1 - 2 * (1 - p) * (1 - p)
        t_after = progress_to_t(progress_after)
        t_before = progress_to_t(progress_before)
        intervals.append(total_time * (t_after - t_before))
    return intervals


def _perturb_intervals(intervals: List[float], factor: float = INTERVAL_PERTURB_FACTOR) -> List[float]:
    """对每段间隔加随机扰动，总和不变，避免匀速感。"""
    if not intervals or factor <= 0:
        return intervals
    n = len(intervals)
    total = sum(intervals)
    # 每段乘以 (1 + factor * (-1..1))，再按比例缩放回 total
    perturbed = [
        max(0.005, intervals[i] * (1.0 + factor * (2 * random.random() - 1)))
        for i in range(n)
    ]
    scale = total / sum(perturbed)
    return [p * scale for p in perturbed]


def _add_path_jitter(
    points: List[Tuple[float, float]],
    max_px: float = PATH_JITTER_PX,
    skip_first_last: bool = True,
) -> List[Tuple[float, float]]:
    """对路径中间点加垂直于运动方向的轻微抖动，轨迹更接近人手。首尾点可选保留。"""
    if not points or max_px <= 0:
        return points
    n = len(points)
    out: List[Tuple[float, float]] = []
    for i in range(n):
        x, y = points[i]
        if skip_first_last and (i == 0 or i == n - 1):
            out.append((x, y))
            continue
        # 运动方向：从前一点到后一点
        if i == 0:
            dx, dy = points[1][0] - x, points[1][1] - y
        elif i == n - 1:
            dx, dy = x - points[i - 1][0], y - points[i - 1][1]
        else:
            dx = (points[i + 1][0] - points[i - 1][0]) / 2.0
            dy = (points[i + 1][1] - points[i - 1][1]) / 2.0
        length = (dx * dx + dy * dy) ** 0.5
        if length < 1e-6:
            out.append((x, y))
            continue
        # 单位法向 (垂直方向)，加随机正负
        nx, ny = -dy / length, dx / length
        if random.random() < 0.5:
            nx, ny = -nx, -ny
        jitter = max_px * (2 * random.random() - 1)
        out.append((x + nx * jitter, y + ny * jitter))
    return out


def _move_along_path(
    points: List[Tuple[float, float]],
    interval: Optional[float] = None,
    total_time: Optional[float] = None,
    ease_in_out: bool = False,
    perturb_intervals: bool = True,
) -> None:
    """沿路径逐点移动。若传 total_time 则整段在 total_time 内完成，采用缓动间隔并可加时间扰动；否则用固定 interval。"""
    import pyautogui
    if not points:
        return
    if total_time is not None and total_time > 0:
        intervals = (
            _ease_in_out_intervals(len(points), total_time)
            if ease_in_out
            else _ease_out_intervals(len(points), total_time)
        )
        if perturb_intervals:
            intervals = _perturb_intervals(intervals, INTERVAL_PERTURB_FACTOR)
    else:
        if interval is None:
            interval = MOVE_INTERVAL
        intervals = [interval] * len(points)
    for i, (x, y) in enumerate(points):
        tx, ty = int(round(x)), int(round(y))
        pyautogui.moveTo(tx, ty)
        time.sleep(intervals[i])
        actual = pyautogui.position()
        print(f"[_move_along_path] step {i + 1}/{len(points)} target=({tx}, {ty}) actual=({actual[0]}, {actual[1]}) delta=({actual[0] - tx}, {actual[1] - ty})")


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
    _captcha_log(tool.agent, "验证码识别中")
    answer, err = _upload_and_query(tool.agent, b64, remark)
    if err is not None:
        return err
    _captcha_log(tool.agent, "验证码识别完成")
    index_map, err = vc.get_index_map(tool.agent)
    if err is not None:
        return err
    pos = vc.resolve_index(index_map, index_input_area)
    _captcha_log(tool.agent, "模拟人工操作")
    actions = ActionTools(dry_run=False, paste_key=["command", "v"] if platform.system() == "Darwin" else ["ctrl", "v"])
    actions._click(pos)
    time.sleep(0.1)
    actions._type_text(answer)
    _captcha_log(tool.agent, "操作结束")
    return Response(
        message=f"Goal: {goal}. Captcha answer entered into index {index_input_area}. Verify on next screenshot.",
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
    _captcha_log(tool.agent, "验证码识别中")
    answer, err = _upload_and_query(tool.agent, b64, remark)
    if err is not None:
        return err
    _captcha_log(tool.agent, "验证码识别完成")
    rel = _parse_coords_result(answer)
    if not rel:
        return Response(message="No coordinates in answer.", break_loop=False)
    index_map, err = vc.get_index_map(tool.agent)
    if err is not None:
        return err
    screen_points = _relative_to_screen(index_map, index_captcha_area, rel)
    _captcha_log(tool.agent, "模拟人工操作")
    import pyautogui
    actions = ActionTools(dry_run=False, paste_key=["command", "v"] if platform.system() == "Darwin" else ["ctrl", "v"])
    for i, target in enumerate(screen_points):
        # 每次移动前随机等待，模拟人工节奏（参考 crack 逻辑）
        time.sleep(PRE_MOVE_DELAY_MIN + random.random() * (PRE_MOVE_DELAY_MAX - PRE_MOVE_DELAY_MIN))
        current = pyautogui.position()
        path_pts = mouse_path.mouse_path([current[0], current[1]], target, num_points=BEZIER_POINTS)
        # 单次移动总时长 0.1~0.35s，按路径点数均分 interval
        total_time = MOVE_TOTAL_TIME_MIN + random.random() * (MOVE_TOTAL_TIME_MAX - MOVE_TOTAL_TIME_MIN)
        _move_along_path(path_pts, total_time=total_time)
        actions._click(target)
    _captcha_log(tool.agent, "操作结束")
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
    _captcha_log(tool.agent, "验证码识别中")
    answer, err = _upload_and_query(tool.agent, b64, remark)
    if err is not None:
        return err
    _captcha_log(tool.agent, "验证码识别完成")
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
    _captcha_log(tool.agent, "模拟人工操作")
    # 多点串联成完整贝塞尔轨迹；滑块时加轨迹抖动与缓动时长，满足后端轨迹/耗时/加速度校验
    full_path = mouse_path.mouse_path_through_points(
        [[float(p[0]), float(p[1])] for p in screen_points],
        num_points_per_segment=BEZIER_POINTS,
    )
    if not full_path:
        return Response(message="Path generation failed.", break_loop=False)
    if is_slider:
        full_path = _add_path_jitter(full_path, max_px=PATH_JITTER_PX, skip_first_last=True)

    import pyautogui
    time.sleep(PRE_MOVE_DELAY_MIN + random.random() * (PRE_MOVE_DELAY_MAX - PRE_MOVE_DELAY_MIN))
    current = pyautogui.position()
    to_start = mouse_path.mouse_path([current[0], current[1]], [full_path[0][0], full_path[0][1]], num_points=BEZIER_POINTS)
    total_time = MOVE_TOTAL_TIME_MIN + random.random() * (MOVE_TOTAL_TIME_MAX - MOVE_TOTAL_TIME_MIN)
    _move_along_path(to_start, total_time=total_time)
    pyautogui.mouseDown()
    time.sleep(0.05)
    if is_slider:
        slider_time = SLIDER_TOTAL_TIME_MIN + random.random() * (SLIDER_TOTAL_TIME_MAX - SLIDER_TOTAL_TIME_MIN)
        _move_along_path(
            full_path[1:],
            total_time=slider_time,
            ease_in_out=True,
            perturb_intervals=True,
        )
    else:
        _move_along_path(full_path[1:], interval=DRAG_MOVE_INTERVAL)
    time.sleep(0.05)
    pyautogui.mouseUp()
    time.sleep(0.1)
    _captcha_log(tool.agent, "操作结束")
    return Response(
        message=f"Goal: {goal}. Drag along {len(screen_points)} point(s). Verify on next screenshot.",
        break_loop=False,
    )


class CaptchaVerifyTool(Tool):
    """验证码验证：type（输入）、click（点选）、drag（拖动）。"""

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
