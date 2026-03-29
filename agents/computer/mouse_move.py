"""
Mouse movement planning and execution.
Provides high-level MouseMove class for external use.
Path generation uses Bézier curves; timing supports ease-out and ease-in-out.
"""
from __future__ import annotations

import math
import random
import time
from typing import Any, Final, List, Optional, Tuple

import mouse_path as _mouse_path


# Default jitter configuration constants
DEFAULT_JITTER_STEPS: Final[int] = 3
DEFAULT_JITTER_RADIUS_PX: Final[int] = 10
DEFAULT_JITTER_SLEEP_MIN: Final[float] = 0.2
DEFAULT_JITTER_SLEEP_MAX: Final[float] = 0.5


def _ease_out_intervals(n: int, total_time: float) -> List[float]:
    """Ease-out: `n` intervals (seconds) sum to `total_time`. Internal function."""
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


def _ease_in_out_intervals(n: int, total_time: float) -> List[float]:
    """Ease-in-out: slow start/end, faster middle. Internal function."""
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


def _add_path_jitter(
    points: List[Tuple[float, float]],
    max_px: float,
    *,
    skip_first_last: bool = True,
) -> List[Tuple[float, float]]:
    """Random normal jitter on interior path points; if max_px<=0 return unchanged. Internal function."""
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


def _spread_interval_perturbation(intervals: List[float], factor: float) -> List[float]:
    """Random multiplicative perturbation per interval; total sum preserved. Internal function."""
    if not intervals or factor <= 0:
        return intervals
    total = sum(intervals)
    perturbed = [
        max(0.005, intervals[i] * (1.0 + factor * (2 * random.random() - 1)))
        for i in range(len(intervals))
    ]
    scale = total / sum(perturbed)
    return [p * scale for p in perturbed]


def _mouse_jitter_near_cursor(
    jitter_radius_px: int = DEFAULT_JITTER_RADIUS_PX,
    steps: int = DEFAULT_JITTER_STEPS,
    sleep_min: float = DEFAULT_JITTER_SLEEP_MIN,
    sleep_max: float = DEFAULT_JITTER_SLEEP_MAX,
    move_to_func: Optional[Any] = None,
) -> None:
    """
    Move to random points within ±jitter_radius_px of cursor (no eased path). Internal function.

    Args:
        jitter_radius_px: Maximum distance from current cursor position.
        steps: Number of jitter movements to perform.
        sleep_min: Minimum sleep time between movements (seconds).
        sleep_max: Maximum sleep time between movements (seconds).
        move_to_func: Optional custom move function. If None, uses pyautogui.moveTo.
    """
    import pyautogui

    if move_to_func is None:
        move_to_func = pyautogui.moveTo

    screen_width, screen_height = pyautogui.size()
    current_x, current_y = (int(pyautogui.position()[0]), int(pyautogui.position()[1]))

    for _ in range(steps):
        new_x = current_x + random.randint(-jitter_radius_px, jitter_radius_px)
        new_y = current_y + random.randint(-jitter_radius_px, jitter_radius_px)
        new_x = max(0, min(screen_width - 1, new_x))
        new_y = max(0, min(screen_height - 1, new_y))
        move_to_func(new_x, new_y)
        time.sleep(random.uniform(sleep_min, sleep_max))


class MoveOptions:
    """Options for mouse movement execution."""

    # Duration mode constants
    DURATION_MODE_STEP = "step"  # duration is time per step
    DURATION_MODE_TOTAL = "total"  # duration is total time for entire move
    DURATION_MODE_TOTAL_PERTURB = "total_perturb"  # total time with interval perturbation

    def __init__(
        self,
        *,
        duration: float = 0.03,
        duration_mode: str = DURATION_MODE_STEP,
        ease_in_out: bool = False,
        interval_perturb_factor: float = 0.2,
        pre_delay: float = 0.0,
        post_delay: float = 0.0,
        pre_jitter: bool = False,
        pre_jitter_radius_px: int = DEFAULT_JITTER_RADIUS_PX,
        pre_jitter_steps: int = DEFAULT_JITTER_STEPS,
        pre_jitter_sleep_min: float = DEFAULT_JITTER_SLEEP_MIN,
        pre_jitter_sleep_max: float = DEFAULT_JITTER_SLEEP_MAX,
        path_jitter: bool = False,
        path_jitter_max_px: float = 2.0,
    ):
        """
        Initialize move options.

        Args:
            duration: Time duration in seconds.
                If duration_mode is "step", this is the interval between each move (default: 0.03).
                If duration_mode is "total", this is the total time for the entire move.
                If duration_mode is "total_perturb", same as "total" but with interval perturbation.
            duration_mode: "step" (default), "total", or "total_perturb".
            ease_in_out: Whether to use ease-in-out timing. Only applies with duration_mode="total" or "total_perturb".
            interval_perturb_factor: Factor for interval perturbation in DURATION_MODE_TOTAL_PERTURB.
            pre_delay: Delay before starting the move (seconds).
            post_delay: Delay after completing the move (seconds).
            pre_jitter: Whether to perform jitter movements before starting the move.
            pre_jitter_radius_px: Radius for pre-move jitter (pixels).
            pre_jitter_steps: Number of pre-move jitter movements.
            pre_jitter_sleep_min: Minimum sleep between pre-move jitter (seconds).
            pre_jitter_sleep_max: Maximum sleep between pre-move jitter (seconds).
            path_jitter: Whether to add jitter to the path points.
            path_jitter_max_px: Maximum jitter for path points (pixels).

        Note:
            Mouse button operations (mouse_down, mouse_up, click) should be handled
            externally by the caller, not by this class.
        """
        valid_modes = (
            self.DURATION_MODE_STEP,
            self.DURATION_MODE_TOTAL,
            self.DURATION_MODE_TOTAL_PERTURB,
        )
        if duration_mode not in valid_modes:
            raise ValueError(f"duration_mode must be one of {valid_modes}")

        self.duration = duration
        self.duration_mode = duration_mode
        self.ease_in_out = ease_in_out
        self.interval_perturb_factor = interval_perturb_factor
        self.pre_delay = pre_delay
        self.post_delay = post_delay
        self.pre_jitter = pre_jitter
        self.pre_jitter_radius_px = pre_jitter_radius_px
        self.pre_jitter_steps = pre_jitter_steps
        self.pre_jitter_sleep_min = pre_jitter_sleep_min
        self.pre_jitter_sleep_max = pre_jitter_sleep_max
        self.path_jitter = path_jitter
        self.path_jitter_max_px = path_jitter_max_px


class MouseMove:
    """
    High-level mouse movement interface.
    Encapsulates path generation and movement execution.
    External code should only use this class for mouse movement.
    """

    def __init__(
        self,
        *,
        spline_num_points: int = 10,
        spline_curvature: float = 1.0,
        spline_bend_sign: Optional[int] = None,
        spline_control_jitter_px: float = 2.0,
    ):
        """
        Initialize MouseMove with configuration.

        Args:
            spline_num_points: Number of points per path segment.
            spline_curvature: Path curvature (0=straight, 1=default).
            spline_bend_sign: Bend direction (+1/-1/None for random).
            spline_control_jitter_px: Control point jitter in pixels.
        """
        self._spline_num_points = spline_num_points
        self._spline_curvature = spline_curvature
        self._spline_bend_sign = spline_bend_sign
        self._spline_control_jitter_px = spline_control_jitter_px

    def _generate_path(
        self,
        point_from: List[float],
        point_to: List[float],
        options: MoveOptions,
    ) -> List[Tuple[float, float]]:
        """
        Generate path between two points using mouse_path_spline.
        Applies path jitter if enabled in options.

        Args:
            point_from: Starting point [x, y].
            point_to: Target point [x, y].
            options: MoveOptions containing path configuration.

        Returns:
            List of path points as (x, y) tuples.
        """
        path = _mouse_path.mouse_path_spline(
            point_from,
            point_to,
            num_points=self._spline_num_points,
            curvature=self._spline_curvature,
            bend_sign=self._spline_bend_sign,
            control_jitter_px=self._spline_control_jitter_px,
        )

        # Apply path jitter if requested
        if options.path_jitter:
            path = _add_path_jitter(path, options.path_jitter_max_px)

        return path

    def _calculate_intervals(
        self,
        num_steps: int,
        options: MoveOptions,
    ) -> List[float]:
        """
        Calculate time intervals for each movement step.

        Args:
            num_steps: Number of steps in the path.
            options: MoveOptions containing duration configuration.

        Returns:
            List of interval times in seconds for each step.
        """
        if num_steps <= 0:
            return []

        if options.duration_mode in (MoveOptions.DURATION_MODE_TOTAL, MoveOptions.DURATION_MODE_TOTAL_PERTURB):
            # Total time mode: calculate intervals to fit within total duration
            intervals = (
                _ease_in_out_intervals(num_steps, options.duration)
                if options.ease_in_out
                else _ease_out_intervals(num_steps, options.duration)
            )
            # Apply perturbation if requested
            if options.duration_mode == MoveOptions.DURATION_MODE_TOTAL_PERTURB:
                intervals = _spread_interval_perturbation(intervals, options.interval_perturb_factor)
            return intervals
        else:
            # Step mode: fixed interval per step
            return [options.duration] * num_steps

    def _execute_move(
        self,
        path: List[Tuple[float, float]],
        options: MoveOptions,
        move_to_func: Optional[Any] = None,
    ) -> None:
        """Execute the actual mouse movement. Internal method."""
        import pyautogui

        if move_to_func is None:
            move_to_func = pyautogui.moveTo

        # Pre-delay
        if options.pre_delay > 0:
            time.sleep(options.pre_delay)

        # Pre-move jitter (at current cursor position)
        if options.pre_jitter:
            _mouse_jitter_near_cursor(
                jitter_radius_px=options.pre_jitter_radius_px,
                steps=options.pre_jitter_steps,
                sleep_min=options.pre_jitter_sleep_min,
                sleep_max=options.pre_jitter_sleep_max,
                move_to_func=move_to_func,
            )

        # Calculate and execute movement
        intervals = self._calculate_intervals(len(path), options)

        for (x, y), dt in zip(path, intervals):
            move_to_func(int(round(x)), int(round(y)))
            time.sleep(dt)

        # Post-delay
        if options.post_delay > 0:
            time.sleep(options.post_delay)

    def move_to_point(
        self,
        point_to: List[float],
        options: Optional[MoveOptions] = None,
        move_to_func: Optional[Any] = None,
    ) -> None:
        """
        Move from current position to target point.

        Args:
            point_to: Target point [x, y].
            options: MoveOptions for movement behavior.
            move_to_func: Optional custom move function.
        """
        if options is None:
            options = MoveOptions()

        import pyautogui

        current = pyautogui.position()
        path = self._generate_path([current[0], current[1]], point_to, options)
        self._execute_move(path, options, move_to_func)

    def move_through_points(
        self,
        points: List[List[float]],
        options: Optional[MoveOptions] = None,
        move_to_func: Optional[Any] = None,
    ) -> None:
        """
        Move through a series of points using Bezier path.
        Implemented by calling move_to_point for each segment.

        Args:
            points: List of points [[x1, y1], [x2, y2], ...].
            options: MoveOptions for movement behavior.
            move_to_func: Optional custom move function.
        """
        if not points:
            raise ValueError("points cannot be empty")

        if options is None:
            options = MoveOptions()

        # Move through each point sequentially
        # Only apply pre_delay and pre_jitter for the first point, post_delay for the last point
        # path_jitter is applied to all segments
        for i, point in enumerate(points):
            segment_options = MoveOptions(
                duration=options.duration,
                duration_mode=options.duration_mode,
                ease_in_out=options.ease_in_out,
                pre_delay=options.pre_delay if i == 0 else 0.0,
                post_delay=options.post_delay if i == len(points) - 1 else 0.0,
                pre_jitter=options.pre_jitter if i == 0 else False,
                pre_jitter_radius_px=options.pre_jitter_radius_px,
                pre_jitter_steps=options.pre_jitter_steps,
                pre_jitter_sleep_min=options.pre_jitter_sleep_min,
                pre_jitter_sleep_max=options.pre_jitter_sleep_max,
                path_jitter=options.path_jitter,
                path_jitter_max_px=options.path_jitter_max_px,
            )
            self.move_to_point(point, options=segment_options, move_to_func=move_to_func)
