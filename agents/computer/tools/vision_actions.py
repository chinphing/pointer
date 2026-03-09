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
from coord_convert import normalized_to_screen  # noqa: E402


LAST_VISION_ACTION_KEY = "computer_last_vision_action"


class VisionActionsTool(Tool):
    """Execute vision_actions by index (click_index, double_click_index, type_text_at_index)."""

    async def after_execution(self, response: Response, **kwargs: Any) -> None:
        self.agent.set_data(
            LAST_VISION_ACTION_KEY,
            {
                "tool": self.name,
                "method": self.method or "",
                "args": dict(self.args or {}),
                "result": (response.message or "").strip(),
            },
        )
        await super().after_execution(response, **kwargs)

    def _resolve_index(
        self, index_map: Dict[int, Dict[str, float]], index: int
    ) -> List[int]:
        """Resolve index_map to screen pixel coordinates [x, y]."""
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

    def _resolve_coord(self, x_val: float, y_val: float) -> List[int]:
        """Convert model-normalized coordinates (x, y) to screen pixels [sx, sy]."""
        screen_info = self.agent.get_data("computer_vision_screen_info") or {}
        w = screen_info.get("width")
        h = screen_info.get("height")
        mon_left = screen_info.get("mon_left", 0)
        mon_top = screen_info.get("mon_top", 0)
        if w is None or h is None:
            raise ValueError(
                "No screen info. Ensure the computer screen inject ran for this turn."
            )
        # When inject set pixel mode, use it; else config (qwen/kimi) or default qwen
        system = self.agent.get_data("computer_vision_coordinate_system") or getattr(
            self.agent.config, "vision_coordinate_system", "qwen"
        )
        sx, sy = normalized_to_screen(
            float(x_val), float(y_val), system, int(w), int(h), int(mon_left), int(mon_top)
        )
        return [sx, sy]

    def _infer_method(self, args: Dict[str, Any]) -> str:
        if "text" in args and args.get("text") is not None:
            return "type_text_at_index"
        return "click_index"

    async def execute(self, **kwargs: Any) -> Response:
        args = dict(self.args or {})
        for k, v in kwargs.items():
            if v is not None:
                args[k] = v

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
                result = actions._press_keys(keys)
                return Response(message=result, break_loop=False)
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
                result = actions._wait(sec)
                return Response(message=result, break_loop=False)
            except Exception as e:
                return Response(message=str(e), break_loop=False)
        # Coordinate-based methods: absolute (x, y) or relative to anchor_index (pixels)
        def _get_pos_for_coord_action():
            anchor = args.get("anchor_index")
            if anchor is not None:
                index_map_rel = self.agent.get_data("computer_vision_index_map") or {}
                if not index_map_rel:
                    return None, "anchor_index requires index_map (ensure screen inject ran)."
                try:
                    base = self._resolve_index(index_map_rel, int(anchor))
                except (ValueError, TypeError) as e:
                    return None, str(e)
                offset_x, offset_y = args.get("offset_x"), args.get("offset_y")
                direction = (args.get("direction") or "").strip().lower()
                pixels = args.get("pixels")
                if offset_x is not None or offset_y is not None:
                    dx = int(round(float(offset_x or 0)))
                    dy = int(round(float(offset_y or 0)))
                elif direction and pixels is not None:
                    try:
                        p = int(round(float(pixels)))
                    except (TypeError, ValueError):
                        return None, f"Invalid 'pixels' value: {pixels}."
                    dir_map = {
                        "right": (p, 0), "left": (-p, 0),
                        "above": (0, -p), "up": (0, -p),
                        "below": (0, p), "down": (0, p),
                    }
                    if direction not in dir_map:
                        return None, "direction must be one of: left, right, above, below, up, down."
                    dx, dy = dir_map[direction]
                else:
                    return None, "With anchor_index provide offset_x/offset_y (pixels) or direction + pixels."
                return [base[0] + dx, base[1] + dy], None
            x_arg, y_arg = args.get("x"), args.get("y")
            if x_arg is None or y_arg is None:
                return None, "Missing 'x'/'y' or anchor_index (+ offset_x/offset_y or direction + pixels)."
            try:
                pos = self._resolve_coord(float(x_arg), float(y_arg))
                return pos, None
            except ValueError as e:
                return None, str(e)

        if method == "click_at":
            pos, err = _get_pos_for_coord_action()
            if err:
                return Response(message=err, break_loop=False)
            result = actions._click(pos)
            return Response(message=result, break_loop=False)
        if method == "double_click_at":
            pos, err = _get_pos_for_coord_action()
            if err:
                return Response(message=err, break_loop=False)
            result = actions._double_click(pos)
            return Response(message=result, break_loop=False)
        if method == "right_click_at":
            pos, err = _get_pos_for_coord_action()
            if err:
                return Response(message=err, break_loop=False)
            result = actions._right_click(pos)
            return Response(message=result, break_loop=False)
        if method == "hover_at":
            pos, err = _get_pos_for_coord_action()
            if err:
                return Response(message=err, break_loop=False)
            result = actions._hover(pos)
            return Response(message=result, break_loop=False)
        if method == "type_text_at":
            pos, err = _get_pos_for_coord_action()
            if err:
                return Response(message=err, break_loop=False)
            text = args.get("text", "")
            click_result = actions._click(pos)
            type_result = actions._type_text(str(text))
            return Response(
                message=f"{click_result} {type_result}", break_loop=False
            )
        if method == "type_text_focused":
            """Type text without clicking - use when the input field already has focus. No index needed."""
            text = args.get("text", "")
            if not text:
                return Response(message="Missing 'text' in tool_args.", break_loop=False)
            type_result = actions._type_text(str(text))
            return Response(message=type_result, break_loop=False)

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
            pos = self._resolve_index(index_map, index)
        except ValueError as e:
            return Response(message=str(e), break_loop=False)

        if method == "click_index":
            result = actions._click(pos)
            return Response(message=result, break_loop=False)
        if method == "double_click_index":
            result = actions._double_click(pos)
            return Response(message=result, break_loop=False)
        if method == "type_text_at_index":
            text = args.get("text", "")
            clear_first = args.get("clear_first", False) if isinstance(args.get("clear_first"), bool) else str(args.get("clear_first", "")).lower() in ("true", "1", "yes")
            click_result = actions._click(pos)
            if clear_first:
                # Select all (OS-specific) then type to replace existing content
                mod = "command" if platform.system() == "Darwin" else "ctrl"
                sel_result = actions._press_keys([mod, "a"])
                time.sleep(0.1)
            type_result = actions._type_text(str(text))
            return Response(
                message=f"{click_result} {type_result}", break_loop=False
            )
        if method == "right_click_index":
            result = actions._right_click(pos)
            return Response(message=result, break_loop=False)
        if method == "hover_index":
            result = actions._hover(pos)
            return Response(message=result, break_loop=False)
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
            result = actions._drag(pos, to_pos)
            return Response(message=result, break_loop=False)
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
            # Convert pixel-like amount to actual scroll count: amount/30, at least 1 step when non-zero
            scroll_count = round(amount / 30)
            if amount > 0 and scroll_count < 1:
                scroll_count = 1
            elif amount < 0 and scroll_count > -1:
                scroll_count = -1
            result = actions._scroll_at(pos, scroll_count)
            return Response(message=result, break_loop=False)

        return Response(
            message=f"Unknown method: {method}. Use index-based (click_index, double_click_index, type_text_at_index, right_click_index, hover_index, drag_index_to_index, scroll_at_index), coordinate-based (click_at, double_click_at, right_click_at, hover_at, type_text_at with x,y,text), type_text_focused (when field already focused), press_keys, or wait.",
            break_loop=False,
        )
