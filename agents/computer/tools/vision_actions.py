"""
Agent Zero Tool for ComputerUse: vision-based UI actions by index.
Dispatches click_index / double_click_index / type_text_at_index using index_map from screen-inject.
"""
from __future__ import annotations

import os
import platform
import sys
import time
from typing import Any, Dict, List

from agent import Agent, LoopData
from python.helpers.tool import Tool, Response

# Resolve agents/computer so we can import actions (sibling of tools/)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)

from actions import ActionTools  # noqa: E402


LAST_VISION_ACTION_KEY = "computer_last_vision_action"

COORD_METHODS = ("click_at", "double_click_at", "right_click_at", "hover_at", "type_text_at")


def _image_to_screen_pos(x: Any, y: Any, mon_left: int, mon_top: int) -> List[int]:
    """Convert screenshot (image) coordinates (origin top-left 0,0) to screen coordinates."""
    try:
        ix = int(round(float(x)))
        iy = int(round(float(y)))
    except (TypeError, ValueError):
        raise ValueError("x and y must be numeric (screenshot pixels, origin top-left).")
    return [ix + mon_left, iy + mon_top]


class VisionActionsTool(Tool):
    """Execute vision_actions by index (click_index, double_click_index, type_text_at_index)."""

    async def after_execution(self, response: Response, **kwargs: Any) -> None:
        self.agent.set_data(
            LAST_VISION_ACTION_KEY,
            {
                "tool": self.name,
                "method": self.method or "",
                "args": self.args,
                "result": (response.message or "").strip(),
            },
        )
        # wait for ui to load. 
        time.sleep(0.5)
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
    ) -> List[int]:
        """Resolve position: target is assumed outside the bbox. Reference = right when going right, left when going left; bottom when going down, top when going up; then add delta."""
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
        base_x = right if dx_val > 0 else (left if dx_val < 0 else cx)
        base_y = bottom if dy_val > 0 else (top if dy_val < 0 else cy)
        return [int(round(base_x + dx_val)), int(round(base_y + dy_val))]

    def _infer_method(self, args: Dict[str, Any]) -> str:
        if "text" in args and args.get("text") is not None:
            return "type_text_at_index"
        return "click_index"

    async def execute(self, **kwargs: Any) -> Response:
        args = dict(self.args or {})
        for k, v in kwargs.items():
            if v is not None:
                args[k] = v

        # Validate goal parameter for all methods
        goal = str(args.get("goal", "")).strip()
        if not goal:
            return Response(
                message="Missing required 'goal' in tool_args. Please describe the action and expected result.",
                break_loop=False,
            )

        # OS-specific paste key for _type_text (clipboard paste)
        paste_key = ["command", "v"] if platform.system() == "Darwin" else ["ctrl", "v"]
        actions = ActionTools(dry_run=False, paste_key=paste_key)
        method = (self.method or "").strip() or self._infer_method(args)

        # press_keys and scroll do not require index_map
        if method == "press_keys":
            keys = args.get("keys")
            if not keys:
                return Response(
                    message="Missing 'keys' in tool_args (e.g. [\"ctrl\", \"c\"]).",
                    break_loop=False,
                )
            if isinstance(keys, str):
                keys = [k.strip() for k in keys.split(",")]
            else:
                keys = list(keys)
            try:
                actions._press_keys(keys)
                return Response(message=f"Goal: {goal}. tool_args: {self._tool_args_for_response(args)}. Action executed; verify result on next screenshot.", break_loop=False)
            except Exception as e:
                return Response(message=str(e), break_loop=False)
        if method == "wait":
            sec_arg = args.get("seconds")
            if sec_arg is None:
                return Response(
                    message="Missing 'seconds' in tool_args.",
                    break_loop=False,
                )
            try:
                sec = float(sec_arg)
            except (TypeError, ValueError):
                return Response(
                    message=f"Invalid 'seconds' value: {sec_arg}.",
                    break_loop=False,
                )
            if sec < 0 or sec > 60:
                return Response(
                    message="Seconds must be between 0 and 60.",
                    break_loop=False,
                )
            try:
                actions._wait(sec)
                return Response(message=f"Goal: {goal}. tool_args: {self._tool_args_for_response(args)}. Action executed; verify result on next screenshot.", break_loop=False)
            except Exception as e:
                return Response(message=str(e), break_loop=False)
        # Coordinate-based methods: x, y in screenshot pixels (origin top-left 0,0); convert to screen via screen_info
        if method in COORD_METHODS:
            screen_info = self.agent.get_data("computer_vision_screen_info") or {}
            mon_left = int(screen_info.get("mon_left") or 0)
            mon_top = int(screen_info.get("mon_top") or 0)
            x_arg, y_arg = args.get("x"), args.get("y")
            if x_arg is None or y_arg is None:
                return Response(
                    message="Coordinate-based methods require 'x' and 'y' (screenshot pixels, origin top-left 0,0).",
                    break_loop=False,
                )
            try:
                pos = _image_to_screen_pos(x_arg, y_arg, mon_left, mon_top)
            except ValueError as e:
                return Response(message=str(e), break_loop=False)
            if method == "click_at":
                actions._click(pos)
                return Response(message=f"Goal: {goal}. tool_args: {self._tool_args_for_response(args)}. Action executed; verify result on next screenshot.", break_loop=False)
            if method == "double_click_at":
                actions._double_click(pos)
                return Response(message=f"Goal: {goal}. tool_args: {self._tool_args_for_response(args)}. Action executed; verify result on next screenshot.", break_loop=False)
            if method == "right_click_at":
                actions._right_click(pos)
                return Response(message=f"Goal: {goal}. tool_args: {self._tool_args_for_response(args)}. Action executed; verify result on next screenshot.", break_loop=False)
            if method == "hover_at":
                actions._hover(pos)
                return Response(message=f"Goal: {goal}. tool_args: {self._tool_args_for_response(args)}. Action executed; verify result on next screenshot.", break_loop=False)
            if method == "type_text_at":
                text = args.get("text", "")
                if not text:
                    return Response(message="Missing 'text' in tool_args for type_text_at.", break_loop=False)
                actions._click(pos)
                actions._type_text(str(text))
                return Response(message=f"Goal: {goal}. tool_args: {self._tool_args_for_response(args)}. Action executed; verify result on next screenshot.", break_loop=False)
        if method == "type_text_focused":
            """Type text without clicking - use when the input field already has focus. No index needed."""
            text = args.get("text", "")
            if not text:
                return Response(message="Missing 'text' in tool_args.", break_loop=False)
            actions._type_text(str(text))
            return Response(message=f"Goal: {goal}. tool_args: {self._tool_args_for_response(args)}. Action executed; verify result on next screenshot.", break_loop=False)

        # Index-based methods require index_map
        index_map: Dict[int, Dict[str, float]] = (
            self.agent.get_data("computer_vision_index_map") or {}
        )
        if not index_map:
            return Response(
                message="No index_map available. Ensure the computer screen inject ran for this turn.",
                break_loop=False,
            )
        index_arg = args.get("index")
        if index_arg is None:
            return Response(
                message="Missing 'index' in tool_args.",
                break_loop=False,
            )
        try:
            index = int(index_arg)
        except (TypeError, ValueError):
            return Response(
                message=f"Invalid 'index' value: {index_arg}.",
                break_loop=False,
            )
        if index < 1:
            return Response(
                message="Index must be >= 1 (indices in the annotated image start from 1).",
                break_loop=False,
            )
        try:
            if method == "drag_index_to_index":
                pos = self._resolve_index(index_map, index)
            else:
                pos = self._resolve_position(
                    index_map, index,
                    args.get("delta_x"), args.get("delta_y"),
                )
        except ValueError as e:
            return Response(message=str(e), break_loop=False)

        if method == "click_index":
            actions._click(pos)
            return Response(message=f"Goal: {goal}. tool_args: {self._tool_args_for_response(args)}. Action executed; verify result on next screenshot.", break_loop=False)
        if method == "double_click_index":
            actions._double_click(pos)
            return Response(message=f"Goal: {goal}. tool_args: {self._tool_args_for_response(args)}. Action executed; verify result on next screenshot.", break_loop=False)
        if method == "type_text_at_index":
            text = args.get("text", "")
            clear_first = args.get("clear_first", False) if isinstance(args.get("clear_first"), bool) else str(args.get("clear_first", "")).lower() in ("true", "1", "yes")
            actions._click(pos)
            if clear_first:
                # Select all (OS-specific) then type to replace existing content
                mod = "command" if platform.system() == "Darwin" else "ctrl"
                actions._press_keys([mod, "a"])
                time.sleep(0.1)
            actions._type_text(str(text))
            return Response(
                message=f"Goal: {goal}. tool_args: {self._tool_args_for_response(args)}. Action executed; verify result on next screenshot.", break_loop=False
            )
        if method == "right_click_index":
            actions._right_click(pos)
            return Response(message=f"Goal: {goal}. tool_args: {self._tool_args_for_response(args)}. Action executed; verify result on next screenshot.", break_loop=False)
        if method == "hover_index":
            actions._hover(pos)
            return Response(message=f"Goal: {goal}. tool_args: {self._tool_args_for_response(args)}. Action executed; verify result on next screenshot.", break_loop=False)
        if method == "drag_index_to_index":
            to_index_arg = args.get("to_index")
            if to_index_arg is None:
                return Response(
                    message="Missing 'to_index' for drag_index_to_index.",
                    break_loop=False,
                )
            try:
                to_index = int(to_index_arg)
            except (TypeError, ValueError):
                return Response(
                    message=f"Invalid 'to_index' value: {to_index_arg}.",
                    break_loop=False,
                )
            if to_index < 1:
                return Response(
                    message="to_index must be >= 1.",
                    break_loop=False,
                )
            try:
                to_pos = self._resolve_index(index_map, to_index)
            except ValueError as e:
                return Response(message=str(e), break_loop=False)
            actions._drag(pos, to_pos)
            return Response(message=f"Goal: {goal}. tool_args: {self._tool_args_for_response(args)}. Action executed; verify result on next screenshot.", break_loop=False)
        if method == "scroll_at_index":
            amount_arg = args.get("amount")
            if amount_arg is None:
                return Response(
                    message="Missing 'amount' in tool_args (positive=up, negative=down).",
                    break_loop=False,
                )
            try:
                amount = int(amount_arg)
            except (TypeError, ValueError):
                return Response(
                    message=f"Invalid 'amount' value: {amount_arg}.",
                    break_loop=False,
                )
            if amount == 0:
                return Response(message="Amount cannot be 0.", break_loop=False)
            scroll_count = amount
            actions._scroll_at(pos, scroll_count)
            return Response(message=f"Goal: {goal}. tool_args: {self._tool_args_for_response(args)}. Action executed; verify result on next screenshot.", break_loop=False)

        return Response(
            message=f"Unknown method: {method}. Use index-based (click_index, double_click_index, type_text_at_index, right_click_index, hover_index, drag_index_to_index, scroll_at_index), coordinate-based (click_at, double_click_at, right_click_at, hover_at, type_text_at with x,y in screenshot pixels), type_text_focused, press_keys, or wait.",
            break_loop=False,
        )
