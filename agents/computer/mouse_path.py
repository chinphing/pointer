"""
Mouse trajectories: cubic Bézier / cubic-spline sampling for one segment or chained points.
Bend is controlled by `curvature`; p1/p2 get tangential + normal jitter (`control_jitter_px`, default ~2px, 0 disables).
`bend_pixels` overrides bend; `bend_sign` fixes or randomizes bend direction.
"""
from __future__ import annotations

import random
from typing import List, Optional, Tuple

import numpy as np

# Normal offset ≈ chord_length * CURVATURE_BASE_RATIO, scaled by curvature, clamped to [MIN, MAX] px
_CURVATURE_BASE_RATIO = 0.12
_MIN_BEND_PX = 5.0
_MAX_BEND_PX = 60.0
# p1/p2: tangential/normal uniform[-j,j] jitter (px); None uses default
_DEFAULT_CONTROL_JITTER_PX = 2.0


def _bezier_segment(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    num_points: int = 10,
) -> List[Tuple[float, float]]:
    """
    Cubic Bézier B(t) = (1-t)^3 P0 + 3(1-t)^2 t P1 + 3(1-t) t^2 P2 + t^3 P3.
    p0..p3 are (x,y); returns `num_points` samples (excludes start, includes end to avoid duplicate joints).
    """
    if num_points < 1:
        num_points = 1
    t = np.linspace(0, 1, num_points + 1)[1:]  # skip t=0, include t=1
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
    Four control points: p0/p3 endpoints; p1/p2 at 1/3 and 2/3 along chord, offset by `bend` along left normal.

    - If `bend_pixels` is set: use that signed pixel offset (overrides curvature / bend_sign).
    - Else: base = clip(0.12 * chord, 5, 60), bend = curvature * base * sign;
      curvature <= 0 → straight; bend_sign +1 / -1 fixes side, None → random ±1.
    - control_jitter_px: independent uniform jitter on p1/p2 in tangent and normal; None → module default, 0 off.
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
    Same four control points as `mouse_path`; fit CubicSpline on x(u), y(u) and sample.
    curvature: 0 straight, 1 default strength, >1 stronger bend.
    bend_sign: +1 / -1 fixes normal side; None random (only if bend_pixels unset and curvature>0).
    bend_pixels: if set, signed pixel offset; ignores curvature / bend_sign.
    control_jitter_px: p1/p2 jitter amplitude (px), 0 off, None default.
    Falls back to `mouse_path` (Bézier) if scipy is missing.
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
    Cubic Bézier from point_from to point_to. Parameters match `mouse_path_spline`.
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
    Chain segments with `mouse_path`.
    bend_sign=None → random bend per segment; pass ±1 for consistent side.
    Independent p1/p2 jitter per segment.
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
