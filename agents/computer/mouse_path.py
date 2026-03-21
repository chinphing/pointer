"""
鼠标轨迹：三次贝塞尔 / 三次样条采样，支持两点一段与多点串联。
弯曲度由 curvature 控制；p1/p2 在弦向+法向有随机微扰（control_jitter_px，默认约 2px，0 关闭）。
bend_pixels 可覆盖弯曲；bend_sign 固定或随机弯向。
"""
from __future__ import annotations

import random
from typing import List, Optional, Tuple

import numpy as np

# 基准：法向偏移 ≈ chord_length * CURVATURE_BASE_RATIO，再乘 curvature，并夹在 [MIN, MAX] 像素
_CURVATURE_BASE_RATIO = 0.12
_MIN_BEND_PX = 5.0
_MAX_BEND_PX = 60.0
# p1、p2 在切向/法向各加 uniform[-j,j]（像素）；None 用默认值
_DEFAULT_CONTROL_JITTER_PX = 2.0


def _bezier_segment(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    num_points: int = 10,
) -> List[Tuple[float, float]]:
    """
    三次贝塞尔曲线 B(t) = (1-t)^3 P0 + 3(1-t)^2 t P1 + 3(1-t) t^2 P2 + t^3 P3。
    p0..p3 为 (x,y)，返回 num_points 个插值点（不含起点，含终点，避免重复拼接时重复）。
    """
    if num_points < 1:
        num_points = 1
    t = np.linspace(0, 1, num_points + 1)[1:]  # 不含 t=0，含 t=1
    one_t = 1 - t
    x = (
        one_t ** 3 * p0[0]
        + 3 * one_t ** 2 * t * p1[0]
        + 3 * one_t * t ** 2 * p2[0]
        + t ** 3 * p3[0]
    )
    y = (
        one_t ** 3 * p0[1]
        + 3 * one_t ** 2 * t * p1[1]
        + 3 * one_t * t ** 2 * p2[1]
        + t ** 3 * p3[1]
    )
    return list(zip(x.tolist(), y.tolist()))


def _segment_control_points(
    point_from: List[float],
    point_to: List[float],
    *,
    curvature: float = 1.0,
    bend_sign: Optional[int] = None,
    bend_pixels: Optional[float] = None,
    control_jitter_px: Optional[float] = None,
) -> Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float], Tuple[float, float]]:
    """
    四个控制点：p0、p3 为端点；p1、p2 在弦的 1/3、2/3 处，并沿左法向偏移 bend。

    - bend_pixels 非 None：直接使用该有符号像素偏移（覆盖 curvature / bend_sign）。
    - 否则：base = clip(0.12 * 弦长, 5, 60)，bend = curvature * base * sign；
      curvature <= 0 为直线；bend_sign 为 +1 / -1 固定弯向，None 则随机 ±1。
    - control_jitter_px：对 p1、p2 在切向、法向各加独立均匀随机扰动；None 用模块默认，0 关闭。
    """
    x0, y0 = float(point_from[0]), float(point_from[1])
    x1, y1 = float(point_to[0]), float(point_to[1])
    diff_x = x1 - x0
    diff_y = y1 - y0
    L = float(np.hypot(diff_x, diff_y))
    p0 = (x0, y0)
    p3 = (x1, y1)
    if L < 1e-6:
        return p0, p0, p3, p3
    nx, ny = -diff_y / L, diff_x / L
    tx, ty = diff_x / L, diff_y / L

    if bend_pixels is not None:
        bend = float(bend_pixels)
    elif curvature <= 0:
        bend = 0.0
    else:
        base = min(_MAX_BEND_PX, max(_MIN_BEND_PX, _CURVATURE_BASE_RATIO * L))
        mag = float(curvature) * base
        if bend_sign is None:
            sign_f = random.choice([-1.0, 1.0])
        else:
            sign_f = 1.0 if bend_sign > 0 else -1.0
        bend = sign_f * mag

    p1x = x0 + diff_x / 3 + nx * bend
    p1y = y0 + diff_y / 3 + ny * bend
    p2x = x1 - diff_x / 3 + nx * bend
    p2y = y1 - diff_y / 3 + ny * bend

    j = _DEFAULT_CONTROL_JITTER_PX if control_jitter_px is None else float(control_jitter_px)
    if j > 0:
        a1, b1 = j * (2 * random.random() - 1), j * (2 * random.random() - 1)
        a2, b2 = j * (2 * random.random() - 1), j * (2 * random.random() - 1)
        p1x += tx * a1 + nx * b1
        p1y += ty * a1 + ny * b1
        p2x += tx * a2 + nx * b2
        p2y += ty * a2 + ny * b2

    p1 = (p1x, p1y)
    p2 = (p2x, p2y)
    return p0, p1, p2, p3


def mouse_path_spline(
    point_from: List[float],
    point_to: List[float],
    num_points: int = 10,
    *,
    curvature: float = 1.0,
    bend_sign: Optional[int] = None,
    bend_pixels: Optional[float] = None,
    control_jitter_px: Optional[float] = None,
) -> List[Tuple[float, float]]:
    """
    与 mouse_path 共用四控制点；对 x(u)、y(u) 做 CubicSpline 并采样。
    curvature：弯曲度，0 为直线，1 为默认强度，可 >1 更弯。
    bend_sign：+1 / -1 固定法向侧，None 时随机（仅当未传 bend_pixels 且 curvature>0）。
    bend_pixels：若给定则直接作为有符号像素偏移，忽略 curvature / bend_sign。
    control_jitter_px：p1/p2 随机扰动幅度（像素），0 关闭，None 用默认。
    无 scipy 时回退为 mouse_path（贝塞尔）。
    """
    if num_points < 1:
        num_points = 1
    p0, p1, p2, p3 = _segment_control_points(
        point_from,
        point_to,
        curvature=curvature,
        bend_sign=bend_sign,
        bend_pixels=bend_pixels,
        control_jitter_px=control_jitter_px,
    )
    try:
        from scipy.interpolate import CubicSpline
    except ImportError:
        return mouse_path(
            point_from,
            point_to,
            num_points=num_points,
            curvature=curvature,
            bend_sign=bend_sign,
            bend_pixels=bend_pixels,
            control_jitter_px=control_jitter_px,
        )

    knots = np.array([p0, p1, p2, p3], dtype=np.float64)
    u = np.array([0.0, 1.0, 2.0, 3.0], dtype=np.float64)
    cx = CubicSpline(u, knots[:, 0])
    cy = CubicSpline(u, knots[:, 1])
    u_sample = np.linspace(0.0, 3.0, num_points + 1)[1:]
    x_i = cx(u_sample)
    y_i = cy(u_sample)
    return list(zip(x_i.tolist(), y_i.tolist()))


def mouse_path(
    point_from: List[float],
    point_to: List[float],
    num_points: int = 10,
    *,
    curvature: float = 1.0,
    bend_sign: Optional[int] = None,
    bend_pixels: Optional[float] = None,
    control_jitter_px: Optional[float] = None,
) -> List[Tuple[float, float]]:
    """
    从 point_from 到 point_to 的三次贝塞尔轨迹。参数语义同 mouse_path_spline。
    """
    p0, p1, p2, p3 = _segment_control_points(
        point_from,
        point_to,
        curvature=curvature,
        bend_sign=bend_sign,
        bend_pixels=bend_pixels,
        control_jitter_px=control_jitter_px,
    )
    return _bezier_segment(p0, p1, p2, p3, num_points)


def mouse_path_through_points(
    points: List[List[float]],
    num_points_per_segment: int = 10,
    *,
    curvature: float = 1.0,
    bend_sign: Optional[int] = None,
    bend_pixels: Optional[float] = None,
    control_jitter_px: Optional[float] = None,
) -> List[Tuple[float, float]]:
    """
    多点串联：每段调用 mouse_path。
    bend_sign=None 时每段独立随机弯向；若需整段同侧可传 bend_sign=±1。
    每段 p1/p2 独立扰动。
    """
    if not points or len(points) < 2:
        return []
    out: List[Tuple[float, float]] = []
    n = len(points)
    for i in range(n - 1):
        seg = mouse_path(
            points[i],
            points[i + 1],
            num_points=num_points_per_segment,
            curvature=curvature,
            bend_sign=bend_sign,
            bend_pixels=bend_pixels,
            control_jitter_px=control_jitter_px,
        )
        if i == 0:
            out.append((float(points[0][0]), float(points[0][1])))
        out.extend(seg[:-1] if i < n - 2 else seg)
    return out
