"""
Mouse movement planning: only produces processed coordinate paths and per-step dwell times;
does not call low-level pointer APIs (caller uses moveTo/sleep, etc.).
Path sampling: `mouse_path` Bézier / `mouse_path_spline` cubic spline; timing is implemented by Move subclasses.
"""
from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import mouse_path as _mouse_path


def ease_out_intervals(n: int, total_time: float) -> List[float]:
    """Ease-out: `n` intervals (seconds) sum to `total_time`."""
    if n <= 0:
        return []
    if n == 1:
        return [total_time]
    intervals = []
    for i in range(n):
        progress_after = (i + 1) / n
        progress_before = i / n
        t_after = 1.0 - math.sqrt(max(0, 1.0 - progress_after))
        t_before = 1.0 - math.sqrt(max(0, 1.0 - progress_before))
        intervals.append(total_time * (t_after - t_before))
    return intervals


def ease_in_out_intervals(n: int, total_time: float) -> List[float]:
    """Ease-in-out: slow start/end, faster middle."""
    if n <= 0:
        return []
    if n == 1:
        return [total_time]

    def progress_to_t(p: float) -> float:
        if p <= 0.5:
            return 2 * p * p
        return 1 - 2 * (1 - p) * (1 - p)

    intervals = []
    for i in range(n):
        progress_after = (i + 1) / n
        progress_before = i / n
        t_after = progress_to_t(progress_after)
        t_before = progress_to_t(progress_before)
        intervals.append(total_time * (t_after - t_before))
    return intervals


def add_path_jitter(
    points: List[Tuple[float, float]],
    max_px: float,
    *,
    skip_first_last: bool = True,
) -> List[Tuple[float, float]]:
    """Random normal jitter on interior path points; if max_px<=0 return unchanged."""
    if not points or max_px <= 0:
        return points
    n = len(points)
    out: List[Tuple[float, float]] = []
    for i in range(n):
        x, y = points[i]
        if skip_first_last and (i == 0 or i == n - 1):
            out.append((x, y))
            continue
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
        nx, ny = -dy / length, dx / length
        if random.random() < 0.5:
            nx, ny = -nx, -ny
        jitter = max_px * (2 * random.random() - 1)
        out.append((x + nx * jitter, y + ny * jitter))
    return out


def spread_interval_perturbation(intervals: List[float], factor: float) -> List[float]:
    """Random multiplicative perturbation per interval; total sum preserved."""
    if not intervals or factor <= 0:
        return intervals
    total = sum(intervals)
    perturbed = [
        max(0.005, intervals[i] * (1.0 + factor * (2 * random.random() - 1)))
        for i in range(len(intervals))
    ]
    scale = total / sum(perturbed)
    return [p * scale for p in perturbed]


class BaseMove(ABC):
    """Subclasses implement path post-processing and per-step intervals; `plan` returns (path, intervals)."""

    default_interval: float = 0.03

    @abstractmethod
    def postprocess_path(self, points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Transform sampled points (e.g. jitter); return original or copy if no-op."""

    @abstractmethod
    def intervals_for_steps(
        self,
        num_steps: int,
        *,
        interval: Optional[float],
        total_time: Optional[float],
        ease_in_out: bool,
        perturb_intervals: bool,
    ) -> List[float]:
        """Sleep duration (seconds) after reaching each path point; same length as path."""

    def plan(
        self,
        points: List[Tuple[float, float]],
        *,
        interval: Optional[float] = None,
        total_time: Optional[float] = None,
        ease_in_out: bool = False,
        perturb_intervals: bool = True,
    ) -> Tuple[List[Tuple[float, float]], List[float]]:
        """Return (processed path, per-step intervals). Empty input → ([], [])."""
        if not points:
            return [], []
        path = self.postprocess_path(points)
        n = len(path)
        intervals = self.intervals_for_steps(
            n,
            interval=interval,
            total_time=total_time,
            ease_in_out=ease_in_out,
            perturb_intervals=perturb_intervals,
        )
        if len(intervals) != n:
            raise RuntimeError(f"intervals length {len(intervals)} != path length {n}")
        return path, intervals


class SimpleMove(BaseMove):
    """
    Between two points use `mouse_path_spline` (same control points as `mouse_path`).
    Bend: same `curvature` / `bend_sign` / `bend_pixels` / `control_jitter_px` as `mouse_path_spline`.
    """

    def __init__(
        self,
        default_interval: float = 0.03,
        num_points: int = 10,
        *,
        curvature: float = 1.0,
        bend_sign: Optional[int] = None,
        bend_pixels: Optional[float] = None,
        control_jitter_px: Optional[float] = None,
    ):
        self.default_interval = default_interval
        self.num_points = num_points
        self.curvature = curvature
        self.bend_sign = bend_sign
        self.bend_pixels = bend_pixels
        self.control_jitter_px = control_jitter_px

    def path_between(
        self,
        point_from: List[float],
        point_to: List[float],
        num_points: Optional[int] = None,
        *,
        curvature: Optional[float] = None,
        bend_sign: Optional[int] = None,
        bend_pixels: Optional[float] = None,
        control_jitter_px: Optional[float] = None,
    ) -> List[Tuple[float, float]]:
        n = num_points if num_points is not None else self.num_points
        return _mouse_path.mouse_path_spline(
            point_from,
            point_to,
            num_points=n,
            curvature=self.curvature if curvature is None else curvature,
            bend_sign=self.bend_sign if bend_sign is None else bend_sign,
            bend_pixels=self.bend_pixels if bend_pixels is None else bend_pixels,
            control_jitter_px=self.control_jitter_px if control_jitter_px is None else control_jitter_px,
        )

    def plan_segment(
        self,
        point_from: List[float],
        point_to: List[float],
        *,
        num_points: Optional[int] = None,
        interval: Optional[float] = None,
        total_time: Optional[float] = None,
        ease_in_out: bool = False,
        perturb_intervals: bool = True,
        curvature: Optional[float] = None,
        bend_sign: Optional[int] = None,
        bend_pixels: Optional[float] = None,
        control_jitter_px: Optional[float] = None,
    ) -> Tuple[List[Tuple[float, float]], List[float]]:
        pts = self.path_between(
            point_from,
            point_to,
            num_points=num_points,
            curvature=curvature,
            bend_sign=bend_sign,
            bend_pixels=bend_pixels,
            control_jitter_px=control_jitter_px,
        )
        return self.plan(
            pts,
            interval=interval,
            total_time=total_time,
            ease_in_out=ease_in_out,
            perturb_intervals=perturb_intervals,
        )

    def postprocess_path(self, points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        return points

    def intervals_for_steps(
        self,
        num_steps: int,
        *,
        interval: Optional[float],
        total_time: Optional[float],
        ease_in_out: bool,
        perturb_intervals: bool,
    ) -> List[float]:
        if num_steps <= 0:
            return []
        if total_time is not None and total_time > 0:
            t = total_time / num_steps
            return [t] * num_steps
        iv = interval if interval is not None else self.default_interval
        return [iv] * num_steps


class CompositeMove(BaseMove):
    """Bézier path + optional normal jitter; total-time mode uses ease-out / ease-in-out with interval perturbation."""

    def __init__(
        self,
        *,
        path_jitter_max_px: float = 2.0,
        default_interval: float = 0.03,
        interval_perturb_factor: float = 0.2,
    ):
        self.path_jitter_max_px = path_jitter_max_px
        self.default_interval = default_interval
        self.interval_perturb_factor = interval_perturb_factor

    def postprocess_path(self, points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        if self.path_jitter_max_px <= 0:
            return points
        return add_path_jitter(points, self.path_jitter_max_px, skip_first_last=True)

    def intervals_for_steps(
        self,
        num_steps: int,
        *,
        interval: Optional[float],
        total_time: Optional[float],
        ease_in_out: bool,
        perturb_intervals: bool,
    ) -> List[float]:
        if num_steps <= 0:
            return []
        if total_time is not None and total_time > 0:
            intervals = (
                ease_in_out_intervals(num_steps, total_time)
                if ease_in_out
                else ease_out_intervals(num_steps, total_time)
            )
            if perturb_intervals:
                intervals = spread_interval_perturbation(intervals, self.interval_perturb_factor)
            return intervals
        iv = interval if interval is not None else self.default_interval
        return [iv] * num_steps
