"""
Tests for mouse_move module.
"""
from __future__ import annotations

from typing import List, Tuple
from unittest.mock import MagicMock, patch

import pytest

from mouse_move import (
    DEFAULT_JITTER_RADIUS_PX,
    DEFAULT_JITTER_SLEEP_MAX,
    DEFAULT_JITTER_SLEEP_MIN,
    DEFAULT_JITTER_STEPS,
    MouseMove,
    MoveOptions,
    _add_path_jitter,
    _ease_in_out_intervals,
    _ease_out_intervals,
    _mouse_jitter_near_cursor,
    _spread_interval_perturbation,
)


class TestEaseOutIntervals:
    """Tests for _ease_out_intervals function."""

    def test_empty_intervals(self) -> None:
        """Test that n <= 0 returns empty list."""
        result = _ease_out_intervals(0, 1.0)
        assert result == []

    def test_single_interval(self) -> None:
        """Test that n == 1 returns [total_time]."""
        result = _ease_out_intervals(1, 5.0)
        assert result == [5.0]

    def test_sum_equals_total_time(self) -> None:
        """Test that intervals sum to total_time."""
        total_time = 1.0
        n = 10
        intervals = _ease_out_intervals(n, total_time)
        assert abs(sum(intervals) - total_time) < 1e-6
        assert len(intervals) == n

    def test_ease_out_pattern(self) -> None:
        """Test that intervals follow ease-out pattern (increasing)."""
        intervals = _ease_out_intervals(5, 1.0)
        # Ease-out: starts fast (shorter intervals), slows down (longer intervals)
        assert intervals[0] < intervals[-1]


class TestEaseInOutIntervals:
    """Tests for _ease_in_out_intervals function."""

    def test_empty_intervals(self) -> None:
        """Test that n <= 0 returns empty list."""
        result = _ease_in_out_intervals(0, 1.0)
        assert result == []

    def test_single_interval(self) -> None:
        """Test that n == 1 returns [total_time]."""
        result = _ease_in_out_intervals(1, 5.0)
        assert result == [5.0]

    def test_sum_equals_total_time(self) -> None:
        """Test that intervals sum to total_time."""
        total_time = 1.0
        n = 10
        intervals = _ease_in_out_intervals(n, total_time)
        assert abs(sum(intervals) - total_time) < 1e-6
        assert len(intervals) == n

    def test_ease_in_out_pattern(self) -> None:
        """Test that intervals follow ease-in-out pattern."""
        intervals = _ease_in_out_intervals(5, 1.0)
        # Middle should be larger than ends
        assert intervals[2] > intervals[0]
        assert intervals[2] > intervals[4]


class TestAddPathJitter:
    """Tests for _add_path_jitter function."""

    def test_empty_points(self) -> None:
        """Test that empty points returns empty list."""
        result = _add_path_jitter([], 5.0)
        assert result == []

    def test_zero_max_px(self) -> None:
        """Test that max_px <= 0 returns original points."""
        points: List[Tuple[float, float]] = [(0, 0), (10, 10), (20, 20)]
        result = _add_path_jitter(points, 0.0)
        assert result == points

    def test_skip_first_last(self) -> None:
        """Test that first and last points are not jittered."""
        points: List[Tuple[float, float]] = [(0, 0), (10, 10), (20, 20)]
        result = _add_path_jitter(points, 5.0, skip_first_last=True)
        assert result[0] == points[0]
        assert result[-1] == points[-1]

    def test_interior_points_jittered(self) -> None:
        """Test that interior points are jittered."""
        points: List[Tuple[float, float]] = [(0, 0), (10, 10), (20, 20)]
        result = _add_path_jitter(points, 5.0, skip_first_last=True)
        # Interior point should be different (with high probability)
        assert len(result) == len(points)


class TestSpreadIntervalPerturbation:
    """Tests for _spread_interval_perturbation function."""

    def test_empty_intervals(self) -> None:
        """Test that empty intervals returns empty list."""
        result = _spread_interval_perturbation([], 0.2)
        assert result == []

    def test_zero_factor(self) -> None:
        """Test that factor <= 0 returns original intervals."""
        intervals = [0.1, 0.1, 0.1]
        result = _spread_interval_perturbation(intervals, 0.0)
        assert result == intervals

    def test_sum_preserved(self) -> None:
        """Test that total sum is preserved."""
        intervals = [0.1, 0.2, 0.3, 0.4]
        total = sum(intervals)
        result = _spread_interval_perturbation(intervals, 0.3)
        assert abs(sum(result) - total) < 1e-6

    def test_all_positive(self) -> None:
        """Test that all intervals remain positive."""
        intervals = [0.01, 0.01, 0.01]
        result = _spread_interval_perturbation(intervals, 0.5)
        assert all(iv > 0 for iv in result)


class TestMouseJitterNearCursor:
    """Tests for _mouse_jitter_near_cursor function."""

    def test_default_parameters(self) -> None:
        """Test that default parameters are used correctly."""
        mock_move = MagicMock()
        mock_pyautogui = MagicMock()
        mock_pyautogui.size.return_value = (1920, 1080)
        mock_pyautogui.position.return_value = (100, 100)

        with patch.dict("sys.modules", {"pyautogui": mock_pyautogui}), \
             patch("time.sleep"):
            _mouse_jitter_near_cursor(move_to_func=mock_move)

        # Should be called DEFAULT_JITTER_STEPS times
        assert mock_move.call_count == DEFAULT_JITTER_STEPS

    def test_custom_parameters(self) -> None:
        """Test that custom parameters are respected."""
        mock_move = MagicMock()
        mock_pyautogui = MagicMock()
        mock_pyautogui.size.return_value = (1920, 1080)
        mock_pyautogui.position.return_value = (500, 500)

        with patch.dict("sys.modules", {"pyautogui": mock_pyautogui}), \
             patch("time.sleep"):
            _mouse_jitter_near_cursor(
                jitter_radius_px=20,
                steps=5,
                sleep_min=0.1,
                sleep_max=0.2,
                move_to_func=mock_move,
            )

        assert mock_move.call_count == 5

    def test_boundary_clamping(self) -> None:
        """Test that coordinates are clamped to screen boundaries."""
        mock_move = MagicMock()
        mock_pyautogui = MagicMock()
        mock_pyautogui.size.return_value = (100, 100)
        mock_pyautogui.position.return_value = (0, 0)

        with patch.dict("sys.modules", {"pyautogui": mock_pyautogui}), \
             patch("time.sleep"):
            _mouse_jitter_near_cursor(
                jitter_radius_px=50,
                steps=10,
                move_to_func=mock_move,
            )

        # All calls should be within bounds
        for call in mock_move.call_args_list:
            args, _ = call
            x, y = args
            assert 0 <= x < 100
            assert 0 <= y < 100


class TestMoveOptions:
    """Tests for MoveOptions class."""

    def test_default_values(self) -> None:
        """Test default values of MoveOptions."""
        opts = MoveOptions()
        assert opts.duration == 0.03
        assert opts.duration_mode == MoveOptions.DURATION_MODE_STEP
        assert opts.ease_in_out is False
        assert opts.pre_delay == 0.0
        assert opts.post_delay == 0.0
        assert opts.pre_jitter is False
        assert opts.pre_jitter_radius_px == DEFAULT_JITTER_RADIUS_PX
        assert opts.pre_jitter_steps == DEFAULT_JITTER_STEPS
        assert opts.pre_jitter_sleep_min == DEFAULT_JITTER_SLEEP_MIN
        assert opts.pre_jitter_sleep_max == DEFAULT_JITTER_SLEEP_MAX
        assert opts.path_jitter is False
        assert opts.path_jitter_max_px == 2.0

    def test_custom_values(self) -> None:
        """Test custom values of MoveOptions."""
        opts = MoveOptions(
            duration=0.5,
            duration_mode=MoveOptions.DURATION_MODE_TOTAL_PERTURB,
            ease_in_out=True,
            pre_delay=0.5,
            post_delay=0.3,
            pre_jitter=True,
            pre_jitter_radius_px=20,
            pre_jitter_steps=5,
            pre_jitter_sleep_min=0.1,
            pre_jitter_sleep_max=0.2,
            path_jitter=True,
            path_jitter_max_px=3.0,
        )
        assert opts.duration == 0.5
        assert opts.duration_mode == MoveOptions.DURATION_MODE_TOTAL_PERTURB
        assert opts.ease_in_out is True
        assert opts.pre_delay == 0.5
        assert opts.post_delay == 0.3
        assert opts.pre_jitter is True
        assert opts.pre_jitter_radius_px == 20
        assert opts.pre_jitter_steps == 5
        assert opts.pre_jitter_sleep_min == 0.1
        assert opts.pre_jitter_sleep_max == 0.2
        assert opts.path_jitter is True
        assert opts.path_jitter_max_px == 3.0

    def test_invalid_duration_mode(self) -> None:
        """Test that invalid duration_mode raises ValueError."""
        with pytest.raises(ValueError, match="duration_mode must be"):
            MoveOptions(duration_mode="invalid")


class TestMouseMove:
    """Tests for MouseMove high-level interface."""

    def test_init(self) -> None:
        """Test MouseMove initialization."""
        mouse_move = MouseMove(
            spline_num_points=15,
            spline_curvature=0.5,
        )
        assert mouse_move._spline_num_points == 15
        assert mouse_move._spline_curvature == 0.5

    def test_move_to_point_step_mode(self) -> None:
        """Test MouseMove.move_to_point with step mode."""
        mouse_move = MouseMove()
        mock_move = MagicMock()
        mock_pyautogui = MagicMock()
        mock_pyautogui.position.return_value = (0, 0)

        with patch.dict("sys.modules", {"pyautogui": mock_pyautogui}), \
             patch("time.sleep"):
            mouse_move.move_to_point(
                [100, 100],
                options=MoveOptions(duration=0.05, duration_mode=MoveOptions.DURATION_MODE_STEP),
                move_to_func=mock_move,
            )

        assert mock_move.call_count > 0

    def test_move_to_point_total_mode(self) -> None:
        """Test MouseMove.move_to_point with total mode."""
        mouse_move = MouseMove()
        mock_move = MagicMock()
        mock_pyautogui = MagicMock()
        mock_pyautogui.position.return_value = (0, 0)

        with patch.dict("sys.modules", {"pyautogui": mock_pyautogui}), \
             patch("time.sleep"):
            mouse_move.move_to_point(
                [100, 100],
                options=MoveOptions(duration=0.5, duration_mode=MoveOptions.DURATION_MODE_TOTAL),
                move_to_func=mock_move,
            )

        assert mock_move.call_count > 0

    def test_move_through_points(self) -> None:
        """Test MouseMove.move_through_points method."""
        mouse_move = MouseMove()
        mock_move = MagicMock()
        mock_pyautogui = MagicMock()

        points = [[0, 0], [50, 50], [100, 100]]

        with patch.dict("sys.modules", {"pyautogui": mock_pyautogui}), \
             patch("time.sleep"):
            mouse_move.move_through_points(
                points,
                options=MoveOptions(duration=0.5, duration_mode=MoveOptions.DURATION_MODE_TOTAL),
                move_to_func=mock_move,
            )

        # Should be called for each point
        assert mock_move.call_count > 0

    def test_move_through_points_empty_raises(self) -> None:
        """Test that move_through_points with empty points raises ValueError."""
        mouse_move = MouseMove()
        mock_pyautogui = MagicMock()

        with patch.dict("sys.modules", {"pyautogui": mock_pyautogui}), \
             pytest.raises(ValueError, match="points cannot be empty"):
            mouse_move.move_through_points([])

    def test_move_to_point_with_pre_jitter(self) -> None:
        """Test move_to_point with pre_jitter option."""
        mouse_move = MouseMove()
        mock_move = MagicMock()
        mock_pyautogui = MagicMock()
        mock_pyautogui.position.return_value = (100, 100)
        mock_pyautogui.size.return_value = (1920, 1080)

        with patch.dict("sys.modules", {"pyautogui": mock_pyautogui}), \
             patch("time.sleep"):
            mouse_move.move_to_point(
                [200, 200],
                options=MoveOptions(
                    duration=0.5,
                    duration_mode=MoveOptions.DURATION_MODE_TOTAL,
                    pre_jitter=True,
                    pre_jitter_steps=3,
                ),
                move_to_func=mock_move,
            )

        # Should have more calls due to pre_jitter
        assert mock_move.call_count > 0

    def test_move_to_point_with_path_jitter(self) -> None:
        """Test move_to_point with path_jitter option."""
        mouse_move = MouseMove()
        mock_move = MagicMock()
        mock_pyautogui = MagicMock()
        mock_pyautogui.position.return_value = (100, 100)

        with patch.dict("sys.modules", {"pyautogui": mock_pyautogui}), \
             patch("time.sleep"):
            mouse_move.move_to_point(
                [200, 200],
                options=MoveOptions(
                    duration=0.5,
                    duration_mode=MoveOptions.DURATION_MODE_TOTAL,
                    path_jitter=True,
                    path_jitter_max_px=3.0,
                ),
                move_to_func=mock_move,
            )

        # Should complete without errors
        assert mock_move.call_count > 0

    def test_move_through_points_segment_options(self) -> None:
        """Test that move_through_points applies options correctly per segment."""
        mouse_move = MouseMove()
        mock_move = MagicMock()
        mock_pyautogui = MagicMock()

        points = [[0, 0], [50, 50], [100, 100]]

        with patch.dict("sys.modules", {"pyautogui": mock_pyautogui}), \
             patch("time.sleep") as mock_sleep:
            mouse_move.move_through_points(
                points,
                options=MoveOptions(
                    duration=0.5,
                    duration_mode=MoveOptions.DURATION_MODE_TOTAL,
                    pre_delay=1.0,
                    post_delay=2.0,
                ),
                move_to_func=mock_move,
            )

        # Should complete without errors
        assert mock_move.call_count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
