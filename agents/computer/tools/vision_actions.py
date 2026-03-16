"""
Agent Zero Tool for ComputerUse: vision-based UI actions by index.
Dispatches click_index / double_click_index / type_text_at_index using index_map from screen-inject.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from agent import Agent, LoopData
from python.helpers.tool import Tool, Response

# Resolve agents/computer so we can import actions (sibling of tools/)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)

from actions import ActionTools  # noqa: E402
from coord_convert import normalized_to_screen  # noqa: E402


LAST_VISION_ACTION_KEY = "computer_last_vision_action"

# Scroll amount: valid range 1–10 (up) or -10–-1 (down); typically use 10 or -10
SCROLL_AMOUNT_MIN, SCROLL_AMOUNT_MAX = 1, 10


def _clamp_scroll_amount(amount: int) -> int:
    """Clamp scroll amount to [1, 10] or [-10, -1]."""
    if amount > 0:
        return max(SCROLL_AMOUNT_MIN, min(SCROLL_AMOUNT_MAX, amount))
    return min(-SCROLL_AMOUNT_MIN, max(-SCROLL_AMOUNT_MAX, amount))


COORD_METHODS = ("click_at", "double_click_at", "right_click_at", "hover_at", "type_text_at")


def _scroll_effect_message_from_changed(screen_changed: bool) -> str:
    """Return the same descriptive text for scroll validation (from actions.py hash comparison)."""
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


def _parse_indices(indices_arg: Any) -> Tuple[Optional[List[int]], Optional[str]]:
    """Parse indices from args. Returns (index_list, None) or (None, error_message)."""
    if indices_arg is None:
        return None, "Missing 'indices' in tool_args for multi_select_by_index (list of item numbers to select, e.g. [1,2,3] or '1,2,3')."
    if indices_arg.startswith("[") and indices_arg.endswith("]"):
        index_list = json.loads(indices_arg)
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


class VisionActionsTool(Tool):
    """Execute vision_actions by index (click_index, double_click_index, type_text_at_index)."""

    async def after_execution(self, response: Response, **kwargs: Any) -> None:
        method = (self.method or "").strip()
        self.agent.set_data(
            LAST_VISION_ACTION_KEY,
            {
                "tool": self.name,
                "method": method,
                "args": self.args,
                "result": (response.message or "").strip(),
            },
        )
        time.sleep(0.3)
        await super().after_execution(response, **kwargs)

    def _resolve_index(
        self, index_map: Dict[int, Dict[str, float]], index: int
    ) -> List[int]:
        """Resolve index_map to screen pixel coordinates [x, y] (center)."""
        if not index_map:
            raise ValueError("index_map is empty. Ensure screen inject (vision route) has run to generate index_map.")
        if index not in index_map:
            raise ValueError(f"index {index} not found in index_map.")
        entry = index_map[index]
        try:
            x = int(round(float(entry["x"])))
            y = int(round(float(entry["y"])))
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Invalid index_map entry for index {index}: {e}.") from e
        return [x, y]

    def _tool_args_for_response(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Build tool_args for response message: exclude index/to_index (no raw coordinates)."""
        exclude = {"index", "to_index"}
        return {k: v for k, v in args.items() if k not in exclude}

    def _resolve_position(
        self,
        index_map: Dict[int, Dict[str, float]],
        index: int,
        delta_x: Any,
        delta_y: Any,
        target_in_bbox: str = "outside",
    ) -> List[int]:
        """Resolve position. Reference edge same for inside/outside (by delta sign). When target_in_bbox is 'inside', offset is negated (negative direction from edge into bbox)."""
        entry = index_map[index]
        cx = float(entry["x"])
        cy = float(entry["y"])
        left = float(entry.get("left", cx - 1))
        top = float(entry.get("top", cy - 1))
        right = float(entry.get("right", 2 * cx - left))
        bottom = float(entry.get("bottom", 2 * cy - top))
        try:
            dx_val = int(round(float(delta_x))) if delta_x is not None else 0
        except (TypeError, ValueError):
            dx_val = 0
        try:
            dy_val = int(round(float(delta_y))) if delta_y is not None else 0
        except (TypeError, ValueError):
            dy_val = 0
        if dx_val == 0 and dy_val == 0:
            return [int(round(cx)), int(round(cy))]
        inside = str(target_in_bbox).strip().lower() == "inside"
        offset_x = -dx_val if inside else dx_val
        offset_y = -dy_val if inside else dy_val
        base_x = right if dx_val > 0 else (left if dx_val < 0 else cx)
        base_y = bottom if dy_val > 0 else (top if dy_val < 0 else cy)
        return [int(round(base_x + offset_x)), int(round(base_y + offset_y))]

    def _infer_method(self, args: Dict[str, Any]) -> str:
        if "text" in args and args.get("text") is not None:
            return "type_text_at_index"
        return "click_index"

    def _action_done(self, goal: str, args: Dict[str, Any], extra: str = "") -> Response:
        msg = f"Goal: {goal}. tool_args: {self._tool_args_for_response(args)}. Action executed; verify result on next screenshot."
        if extra:
            msg = f"Goal: {goal}. {extra} Verify result on next screenshot."
        return Response(message=msg, break_loop=False)

    def _get_index_map(self) -> Tuple[Optional[Dict[int, Dict[str, float]]], Optional[Response]]:
        index_map = self.agent.get_data("computer_vision_index_map") or {}
        if not index_map:
            return None, Response(
                message="No index_map available. Ensure the computer screen inject ran for this turn.",
                break_loop=False,
            )
        return index_map, None

    def _get_single_index_pos(
        self, args: Dict[str, Any], index_map: Dict[int, Dict[str, float]], for_drag: bool = False
    ) -> Tuple[Optional[List[int]], Optional[Response]]:
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
            if for_drag:
                pos = self._resolve_index(index_map, index)
            else:
                in_bbox = (args.get("target_in_bbox") or "outside")
                if isinstance(in_bbox, str):
                    in_bbox = in_bbox.strip().lower()
                    if in_bbox not in ("inside", "outside"):
                        in_bbox = "outside"
                else:
                    in_bbox = "outside"
                pos = self._resolve_position(
                    index_map, index,
                    args.get("delta_x"), args.get("delta_y"),
                    target_in_bbox=in_bbox,
                )
        except ValueError as e:
            return None, Response(message=str(e), break_loop=False)
        return pos, None

    def _get_coord_pos(self, args: Dict[str, Any]) -> Tuple[Optional[List[int]], Optional[Response]]:
        screen_info = self.agent.get_data("computer_vision_screen_info") or {}
        coord_system = (self.agent.get_data("computer_vision_coordinate_system") or "qwen").strip().lower()
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

    # --- Method handlers (each returns Response) ---

    def _do_press_keys(self, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
        keys = args.get("keys")
        if not keys:
            return Response(
                message='Missing \'keys\' in tool_args (e.g. ["ctrl", "c"]).',
                break_loop=False,
            )
        if isinstance(keys, str):
            if keys.startswith("[") and keys.endswith("]"):
                keys = json.loads(keys)
            else:
                keys = [k.strip() for k in keys.split(",")]
        else:
            keys = list(keys)
        try:
            actions._press_keys(keys)
            return self._action_done(goal, args)
        except Exception as e:
            return Response(message=str(e), break_loop=False)

    def _do_wait(self, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
        sec_arg = args.get("seconds")
        if sec_arg is None:
            return Response(message="Missing 'seconds' in tool_args.", break_loop=False)
        try:
            sec = float(sec_arg)
        except (TypeError, ValueError):
            return Response(message=f"Invalid 'seconds' value: {sec_arg}.", break_loop=False)
        if sec < 0 or sec > 60:
            return Response(message="Seconds must be between 0 and 60.", break_loop=False)
        try:
            actions._wait(sec)
            return self._action_done(goal, args)
        except Exception as e:
            return Response(message=str(e), break_loop=False)

    def _do_scroll_at_current(self, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
        amount_arg = args.get("amount")
        if amount_arg is None:
            return Response(
                message="Missing 'amount' in tool_args (positive=scroll up, negative=scroll down).",
                break_loop=False,
            )
        try:
            amount = int(amount_arg)
        except (TypeError, ValueError):
            return Response(message=f"Invalid 'amount' value: {amount_arg}.", break_loop=False)
        if amount == 0:
            return Response(message="Amount cannot be 0.", break_loop=False)
        amount = _clamp_scroll_amount(amount)
        try:
            result_msg, screen_changed = actions._scroll(amount)
        except Exception as e:
            return Response(message=str(e), break_loop=False)
        scroll_effect = ""
        if screen_changed is not None:
            scroll_effect = " " + _scroll_effect_message_from_changed(screen_changed)
        base = self._action_done(goal, args).message
        return Response(message=base + scroll_effect, break_loop=False)

    def _do_click_at(self, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
        pos, err = self._get_coord_pos(args)
        if err is not None:
            return err
        actions._click(pos)
        return self._action_done(goal, args)

    def _do_double_click_at(self, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
        pos, err = self._get_coord_pos(args)
        if err is not None:
            return err
        actions._double_click(pos)
        return self._action_done(goal, args)

    def _do_right_click_at(self, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
        pos, err = self._get_coord_pos(args)
        if err is not None:
            return err
        actions._right_click(pos)
        return self._action_done(goal, args)

    def _do_hover_at(self, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
        pos, err = self._get_coord_pos(args)
        if err is not None:
            return err
        actions._hover(pos)
        return self._action_done(goal, args)

    def _do_type_text_at(self, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
        pos, err = self._get_coord_pos(args)
        if err is not None:
            return err
        text = args.get("text", "")
        if not text:
            return Response(message="Missing 'text' in tool_args for type_text_at.", break_loop=False)
        actions._click(pos)
        actions._type_text(str(text))
        return self._action_done(goal, args)

    def _do_type_text_focused(self, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
        text = args.get("text", "")
        if not text:
            return Response(message="Missing 'text' in tool_args.", break_loop=False)
        actions._type_text(str(text))
        return self._action_done(goal, args)

    def _do_click_indices_for_selection(
        self, args: Dict[str, Any], actions: ActionTools, goal: str
    ) -> Response:
        index_map, err = self._get_index_map()
        if err is not None:
            return err
        index_list, parse_err = _parse_indices(args.get("indices"))
        if parse_err is not None:
            return Response(message=parse_err, break_loop=False)
        positions: List[List[int]] = []
        try:
            for idx in index_list:
                if idx < 1 or idx not in index_map:
                    continue
                positions.append(self._resolve_index(index_map, idx))
        except ValueError as e:
            return Response(message=str(e), break_loop=False)
        if not positions:
            return Response(message="No valid indices resolved to positions.", break_loop=False)
        actions._click_add_to_selection_batch(positions)
        return Response(
            message=f"Goal: {goal}. Held modifier and clicked {len(positions)} item(s) for multi-select. Verify result on next screenshot.",
            break_loop=False,
        )

    def _do_click_index(self, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
        index_map, err = self._get_index_map()
        if err is not None:
            return err
        pos, err = self._get_single_index_pos(args, index_map)
        if err is not None:
            return err
        actions._click(pos)
        return self._action_done(goal, args)

    def _do_double_click_index(self, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
        index_map, err = self._get_index_map()
        if err is not None:
            return err
        pos, err = self._get_single_index_pos(args, index_map)
        if err is not None:
            return err
        actions._double_click(pos)
        return self._action_done(goal, args)

    def _do_type_text_at_index(self, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
        index_map, err = self._get_index_map()
        if err is not None:
            return err
        pos, err = self._get_single_index_pos(args, index_map)
        if err is not None:
            return err
        text = args.get("text", "")
        clear_first = (
            args.get("clear_first", False) if isinstance(args.get("clear_first"), bool)
            else str(args.get("clear_first", "")).lower() in ("true", "1", "yes")
        )
        actions._click(pos)
        if clear_first:
            mod = "command" if platform.system() == "Darwin" else "ctrl"
            actions._press_keys([mod, "a"])
            time.sleep(0.1)
        actions._type_text(str(text))
        return self._action_done(goal, args)

    def _do_right_click_index(self, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
        index_map, err = self._get_index_map()
        if err is not None:
            return err
        pos, err = self._get_single_index_pos(args, index_map)
        if err is not None:
            return err
        actions._right_click(pos)
        return self._action_done(goal, args)

    def _do_hover_index(self, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
        index_map, err = self._get_index_map()
        if err is not None:
            return err
        pos, err = self._get_single_index_pos(args, index_map)
        if err is not None:
            return err
        actions._hover(pos)
        return self._action_done(goal, args)

    def _do_drag_index_to_index(self, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
        index_map, err = self._get_index_map()
        if err is not None:
            return err
        pos, err = self._get_single_index_pos(args, index_map, for_drag=True)
        if err is not None:
            return err
        to_index_arg = args.get("to_index")
        if to_index_arg is None:
            return Response(message="Missing 'to_index' for drag_index_to_index.", break_loop=False)
        try:
            to_index = int(to_index_arg)
        except (TypeError, ValueError):
            return Response(message=f"Invalid 'to_index' value: {to_index_arg}.", break_loop=False)
        if to_index < 1:
            return Response(message="to_index must be >= 1.", break_loop=False)
        try:
            to_pos = self._resolve_index(index_map, to_index)
        except ValueError as e:
            return Response(message=str(e), break_loop=False)
        actions._drag(pos, to_pos)
        return self._action_done(goal, args)

    def _do_scroll_at_index(self, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
        index_map, err = self._get_index_map()
        if err is not None:
            return err
        pos, err = self._get_single_index_pos(args, index_map)
        if err is not None:
            return err
        amount_arg = args.get("amount")
        if amount_arg is None:
            return Response(
                message="Missing 'amount' in tool_args (positive=up, negative=down).",
                break_loop=False,
            )
        try:
            amount = int(amount_arg)
        except (TypeError, ValueError):
            return Response(message=f"Invalid 'amount' value: {amount_arg}.", break_loop=False)
        if amount == 0:
            return Response(message="Amount cannot be 0.", break_loop=False)
        amount = _clamp_scroll_amount(amount)
        try:
            result_msg, screen_changed = actions._scroll_at(pos, amount)
        except Exception as e:
            return Response(message=str(e), break_loop=False)
        scroll_effect = ""
        if screen_changed is not None:
            scroll_effect = " " + _scroll_effect_message_from_changed(screen_changed)
        base = self._action_done(goal, args).message
        return Response(message=base + scroll_effect, break_loop=False)

    async def execute(self, **kwargs: Any) -> Response:
        args = dict(self.args or {})
        for k, v in kwargs.items():
            if v is not None:
                args[k] = v

        goal = str(args.get("goal", "")).strip()
        if not goal:
            return Response(
                message="Missing required 'goal' in tool_args. Please describe the action and expected result.",
                break_loop=False,
            )

        paste_key = ["command", "v"] if platform.system() == "Darwin" else ["ctrl", "v"]
        actions = ActionTools(dry_run=False, paste_key=paste_key)
        method = (self.method or "").strip() or self._infer_method(args)

        handler = _METHOD_HANDLERS.get(method)
        if handler is not None:
            return handler(self, args, actions, goal)

        return Response(
            message=f"Unknown method: {method}. Use index-based (click_index, double_click_index, type_text_at_index, right_click_index, hover_index, drag_index_to_index, scroll_at_index, multi_select_by_index), scroll_at_current (scroll at cursor, no index), coordinate-based (click_at, double_click_at, right_click_at, hover_at, type_text_at with x,y in normalized coords), type_text_focused, press_keys, or wait.",
            break_loop=False,
        )


_METHOD_HANDLERS: Dict[str, Any] = {
    "press_keys": VisionActionsTool._do_press_keys,
    "wait": VisionActionsTool._do_wait,
    
    # coordinate-based tools for elements with no indices
    "click_at": VisionActionsTool._do_click_at,
    "double_click_at": VisionActionsTool._do_double_click_at,
    "right_click_at": VisionActionsTool._do_right_click_at,
    "hover_at": VisionActionsTool._do_hover_at,
    "type_text_at": VisionActionsTool._do_type_text_at,
    "type_text_focused": VisionActionsTool._do_type_text_focused,
    "scroll_at_current": VisionActionsTool._do_scroll_at_current,

    # index-based tools for elements with indices
    "multi_select_by_index": VisionActionsTool._do_click_indices_for_selection,
    "click_index": VisionActionsTool._do_click_index,
    "double_click_index": VisionActionsTool._do_double_click_index,
    "type_text_at_index": VisionActionsTool._do_type_text_at_index,
    "right_click_index": VisionActionsTool._do_right_click_index,
    "hover_index": VisionActionsTool._do_hover_index,
    "drag_index_to_index": VisionActionsTool._do_drag_index_to_index,
    "scroll_at_index": VisionActionsTool._do_scroll_at_index,
}
