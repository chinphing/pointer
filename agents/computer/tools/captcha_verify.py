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
from mouse_move import CompositeMove, SimpleMove  # noqa: E402

from tools import vision_common as vc  # noqa: E402

# 轨迹每段插值点数、移动间隔（秒）
BEZIER_POINTS = 10
# 弯曲度：0 直线，1 为默认强度（见 mouse_path）；None 的 bend_sign 表示每段随机左右弯
MOUSE_PATH_CURVATURE = 1.0
MOUSE_PATH_BEND_SIGN = None  # 设为 +1 / -1 可固定弯向
# p1/p2 切向+法向随机微扰（像素）；0 关闭；None 使用 mouse_path 模块默认（约 2px）
MOUSE_PATH_CONTROL_JITTER_PX = 2.0
MOVE_INTERVAL = 0.03
DRAG_MOVE_INTERVAL = 0.02
# 每次移动到目标前的随机等待（秒），模拟人工节奏
PRE_MOVE_DELAY_MIN, PRE_MOVE_DELAY_MAX = 0.5, 1.5
# 鼠标到达起始点（拖动：手柄起点；点选：首次轨迹终点）后，在指针附近 ±N 像素内随机跳 3 次，再继续按下/点击
PRE_REAL_MOVE_JITTER_STEPS = 3
PRE_REAL_MOVE_JITTER_RADIUS_PX = 10
PRE_REAL_MOVE_JITTER_SLEEP_MIN = 0.2
PRE_REAL_MOVE_JITTER_SLEEP_MAX = 0.5
# 单次移动总时长范围（秒）
MOVE_TOTAL_TIME_MIN, MOVE_TOTAL_TIME_MAX = 0.3, 1
# 滑块滑动总时长（秒）：后端常校验耗时，过短会被判异常，建议 0.35～0.8
SLIDER_TOTAL_TIME_MIN, SLIDER_TOTAL_TIME_MAX = 0.35, 0.75
# 轨迹/时间扰动：路径点垂直方向抖动像素、每段间隔随机波动比例
PATH_JITTER_PX = 2
INTERVAL_PERTURB_FACTOR = 0.2
CLICK_DELAY_MIN, CLICK_DELAY_MAX = 1.0, 5.0
QUERY_TIMEOUT = 60.0

# 点选/非抖动段：缓动 + 时间扰动，路径不抖动（CompositeMove path_jitter_max_px=0）
_CAPTCHA_MOVE_COMPOSITE = CompositeMove(
    path_jitter_max_px=0.0,
    default_interval=MOVE_INTERVAL,
    interval_perturb_factor=INTERVAL_PERTURB_FACTOR,
)
# 滑块主轨迹：贝塞尔 + 法向抖动 + 同上间隔策略
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
    """按 mouse_move 产出的轨迹与间隔执行指针移动（与轨迹生成解耦）。"""
    import pyautogui

    for (x, y), dt in zip(path, intervals):
        pyautogui.moveTo(int(round(x)), int(round(y)))
        time.sleep(dt)


def _mouse_jitter_near_cursor(jitter_radius_px: int = PRE_REAL_MOVE_JITTER_RADIUS_PX) -> None:
    """在当前鼠标位置周围 ±PRE_REAL_MOVE_JITTER_RADIUS_PX 内随机取点，连续移动若干次（无缓动轨迹）。"""
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
    actions._type_text(answer, clear_field_first=True)
    _captcha_log(tool.agent, "操作结束")
    return Response(
        message=(
            f"Goal: {goal}. Type action executed, cleared first.  Please verify result on next screenshot."
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
        path_pts = mouse_path.mouse_path(
            [current[0], current[1]],
            target,
            num_points=BEZIER_POINTS,
            curvature=MOUSE_PATH_CURVATURE,
            bend_sign=MOUSE_PATH_BEND_SIGN,
            control_jitter_px=MOUSE_PATH_CONTROL_JITTER_PX,
        )
        # 单次移动总时长 0.1~0.35s；间隔由 CompositeMove（ease-out + 时间扰动）分配
        total_time = MOVE_TOTAL_TIME_MIN + random.random() * (MOVE_TOTAL_TIME_MAX - MOVE_TOTAL_TIME_MIN)
        p, iv = _CAPTCHA_MOVE_COMPOSITE.plan(path_pts, total_time=total_time)
        _apply_mouse_plan(p, iv)
        actions._click(target)

        if i < len(screen_points) - 1:
            jitter_radius_px = int(PRE_REAL_MOVE_JITTER_RADIUS_PX / (i + 1))
            _mouse_jitter_near_cursor(jitter_radius_px)
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
    _mouse_jitter_near_cursor()
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
