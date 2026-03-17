"""
Shared helpers for computer UI tools (mouse, hotkey, modified_click, composite_action, wait).
Index/coord resolution, scroll clamping, and after_execution hook.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple

from python.helpers.tool import Response

# Resolve agents/computer for coord_convert
import sys
import os
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)
from coord_convert import normalized_to_screen  # noqa: E402

LAST_VISION_ACTION_KEY = "computer_last_vision_action"

SCROLL_AMOUNT_MIN, SCROLL_AMOUNT_MAX = 1, 10


def clamp_scroll_amount(amount: int) -> int:
    """Clamp scroll amount to [1, 10] or [-10, -1]."""
    if amount > 0:
        return max(SCROLL_AMOUNT_MIN, min(SCROLL_AMOUNT_MAX, amount))
    return min(-SCROLL_AMOUNT_MIN, max(-SCROLL_AMOUNT_MAX, amount))


def scroll_effect_message_from_changed(screen_changed: bool) -> str:
    """Return descriptive text for scroll validation."""
    if not screen_changed:
        return (
            "Scroll effect (pixel comparison): screen content **unchanged**. "
            "The scroll may have had no effect (e.g. already at top/bottom, wrong target or position). "
            "Consider trying a different scroll target or position, direction, or a different scroll tool."
        )
    return (
        "Scroll effect (pixel comparison): screen content **changed**. "
        "The scroll took effect; validate from the new screenshot."
    )


def parse_indices(indices_arg: Any) -> Tuple[Optional[List[int]], Optional[str]]:
    """Parse indices from args. Returns (index_list, None) or (None, error_message)."""
    if indices_arg is None:
        return None, "Missing 'indices' in tool_args (list of item numbers, e.g. [1,2,3] or '1,2,3')."
    if isinstance(indices_arg, str) and indices_arg.startswith("[") and indices_arg.endswith("]"):
        try:
            index_list = json.loads(indices_arg)
        except json.JSONDecodeError:
            return None, "Invalid 'indices' JSON."
    elif isinstance(indices_arg, str) and "," in indices_arg:
        index_list = []
        for part in indices_arg.split(","):
            try:
                index_list.append(int(part.strip()))
            except (TypeError, ValueError):
                continue
    else:
        try:
            index_list = [int(indices_arg)]
        except (TypeError, ValueError):
            return None, "'indices' must be a list of integers or comma-separated string."
    if not index_list:
        return None, "No valid indices in 'indices'."
    return index_list, None


def resolve_index(index_map: Dict[int, Dict[str, float]], index: int) -> List[int]:
    """Resolve index to screen pixel coordinates [x, y] (center)."""
    if not index_map:
        raise ValueError("index_map is empty. Ensure screen inject ran for this turn.")
    if index not in index_map:
        raise ValueError(f"index {index} not found in index_map.")
    entry = index_map[index]
    try:
        x = int(round(float(entry["x"])))
        y = int(round(float(entry["y"])))
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"Invalid index_map entry for index {index}: {e}.") from e
    return [x, y]


def get_index_map(agent: Any) -> Tuple[Optional[Dict[int, Dict[str, float]]], Optional[Response]]:
    """Get index_map from agent data. Returns (index_map, None) or (None, error Response)."""
    index_map = agent.get_data("computer_vision_index_map") or {}
    if not index_map:
        return None, Response(
            message="No index_map available. Ensure the computer screen inject ran for this turn.",
            break_loop=False,
        )
    return index_map, None


def get_single_index_pos(
    agent: Any,
    args: Dict[str, Any],
    index_map: Dict[int, Dict[str, float]],
    *,
    for_drag: bool = False,
) -> Tuple[Optional[List[int]], Optional[Response]]:
    """Resolve single index to position (center only; no delta_x/delta_y)."""
    index_arg = args.get("index")
    if index_arg is None:
        return None, Response(message="Missing 'index' in tool_args.", break_loop=False)
    try:
        index = int(index_arg)
    except (TypeError, ValueError):
        return None, Response(message=f"Invalid 'index' value: {index_arg}.", break_loop=False)
    if index < 1:
        return None, Response(
            message="Index must be >= 1 (indices in the annotated image start from 1).",
            break_loop=False,
        )
    try:
        pos = resolve_index(index_map, index)
    except ValueError as e:
        return None, Response(message=str(e), break_loop=False)
    return pos, None


def get_coord_pos(agent: Any, args: Dict[str, Any]) -> Tuple[Optional[List[int]], Optional[Response]]:
    """Resolve normalized x,y to screen pixel position."""
    screen_info = agent.get_data("computer_vision_screen_info") or {}
    coord_system = (agent.get_data("computer_vision_coordinate_system") or "qwen").strip().lower()
    mon_left = int(screen_info.get("mon_left") or 0)
    mon_top = int(screen_info.get("mon_top") or 0)
    width = int(screen_info.get("width") or 0)
    height = int(screen_info.get("height") or 0)
    x_arg, y_arg = args.get("x"), args.get("y")
    if x_arg is None or y_arg is None:
        return None, Response(
            message="Coordinate-based methods require 'x' and 'y' (normalized coordinates, same scale as in the prompt).",
            break_loop=False,
        )
    if width <= 0 or height <= 0:
        return None, Response(
            message="Screen dimensions not available; ensure screen inject ran this turn.",
            break_loop=False,
        )
    try:
        sx, sy = normalized_to_screen(
            float(x_arg), float(y_arg),
            coord_system, width, height, mon_left, mon_top,
        )
        return [sx, sy], None
    except (ValueError, TypeError) as e:
        return None, Response(message=str(e), break_loop=False)


def get_coord_positions(agent: Any, positions_arg: Any) -> Tuple[Optional[List[List[int]]], Optional[Response]]:
    """Parse positions (list of {x,y} or [[x,y],...]) and convert to screen pixel list."""
    if positions_arg is None:
        return None, Response(message="Missing 'positions' in tool_args (list of {x, y} or [[x,y], ...]).", break_loop=False)
    screen_info = agent.get_data("computer_vision_screen_info") or {}
    coord_system = (agent.get_data("computer_vision_coordinate_system") or "qwen").strip().lower()
    mon_left = int(screen_info.get("mon_left") or 0)
    mon_top = int(screen_info.get("mon_top") or 0)
    width = int(screen_info.get("width") or 0)
    height = int(screen_info.get("height") or 0)
    if width <= 0 or height <= 0:
        return None, Response(message="Screen dimensions not available; ensure screen inject ran this turn.", break_loop=False)
    if not isinstance(positions_arg, list) or len(positions_arg) == 0:
        return None, Response(message="'positions' must be a non-empty list of {x, y} or [x, y].", break_loop=False)
    result: List[List[int]] = []
    for i, item in enumerate(positions_arg):
        if isinstance(item, dict):
            x_arg, y_arg = item.get("x"), item.get("y")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            x_arg, y_arg = item[0], item[1]
        else:
            return None, Response(message=f"positions[{i}] must be {{x, y}} or [x, y].", break_loop=False)
        try:
            sx, sy = normalized_to_screen(
                float(x_arg), float(y_arg),
                coord_system, width, height, mon_left, mon_top,
            )
            result.append([sx, sy])
        except (ValueError, TypeError) as e:
            return None, Response(message=f"positions[{i}]: {e}", break_loop=False)
    return result, None


def vision_after_execution(
    agent: Any,
    tool_name: str,
    method: str,
    args: Dict[str, Any],
    response_message: str,
) -> None:
    """Set LAST_VISION_ACTION_KEY and sleep; call from each tool's after_execution."""
    agent.set_data(
        LAST_VISION_ACTION_KEY,
        {
            "tool": tool_name,
            "method": method,
            "args": args,
            "result": (response_message or "").strip(),
        },
    )
    time.sleep(0.3)
