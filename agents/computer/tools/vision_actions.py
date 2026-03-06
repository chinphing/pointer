"""
Agent Zero Tool for ComputerUse: vision-based UI actions by index.
Dispatches click_index / double_click_index / type_text_at_index using index_map from screen-inject.
"""
from __future__ import annotations

import os
import sys
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
        """index_map -> 屏幕像素坐标 [x, y]。"""
        if not index_map:
            raise ValueError("index_map is empty. 请先通过视觉路由生成 index_map。")
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
        """将模型给出的归一化坐标 (x, y) 转为屏幕像素 [sx, sy]。"""
        screen_info = self.agent.get_data("computer_vision_screen_info") or {}
        w = screen_info.get("width")
        h = screen_info.get("height")
        mon_left = screen_info.get("mon_left", 0)
        mon_top = screen_info.get("mon_top", 0)
        if w is None or h is None:
            raise ValueError(
                "No screen info. Ensure the computer screen inject ran for this turn."
            )
        system = getattr(
            self.agent.config, "vision_coordinate_system", "qwen"
        )  # qwen: 1000×1000, kimi: 1×1
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

        actions = ActionTools(dry_run=False)
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
        if method == "close_popup":
            popup_method = args.get("method", "esc")
            if popup_method == "esc":
                try:
                    result = actions._close_popup(method="esc")
                    return Response(message=result, break_loop=False)
                except Exception as e:
                    return Response(message=str(e), break_loop=False)
            if popup_method in ("click_close", "click_cancel", "click_ok"):
                index_map_popup = self.agent.get_data("computer_vision_index_map") or {}
                if not index_map_popup:
                    return Response(
                        message="No index_map for close_popup click. Use method=esc or ensure screen inject ran.",
                        break_loop=False,
                    )
                idx_arg = args.get("index")
                if idx_arg is None:
                    return Response(
                        message="Missing 'index' for close_popup click (the button to click).",
                        break_loop=False,
                    )
                try:
                    idx = int(idx_arg)
                    pos = self._resolve_index(index_map_popup, idx)
                    result = actions._close_popup(method=popup_method, position=pos)
                    return Response(message=result, break_loop=False)
                except (ValueError, TypeError) as e:
                    return Response(message=str(e), break_loop=False)
            return Response(
                message="close_popup method must be 'esc' or 'click_close'/'click_cancel'/'click_ok'.",
                break_loop=False,
            )

        # Coordinate-based methods (when target has no index): x, y in model's native system
        def _get_xy_and_convert():
            x_arg, y_arg = args.get("x"), args.get("y")
            if x_arg is None or y_arg is None:
                return None, "Missing 'x' or 'y' in tool_args for coordinate-based action."
            try:
                pos = self._resolve_coord(float(x_arg), float(y_arg))
                return pos, None
            except ValueError as e:
                return None, str(e)

        if method == "click_at":
            pos, err = _get_xy_and_convert()
            if err:
                return Response(message=err, break_loop=False)
            result = actions._click(pos)
            return Response(message=result, break_loop=False)
        if method == "double_click_at":
            pos, err = _get_xy_and_convert()
            if err:
                return Response(message=err, break_loop=False)
            result = actions._double_click(pos)
            return Response(message=result, break_loop=False)
        if method == "right_click_at":
            pos, err = _get_xy_and_convert()
            if err:
                return Response(message=err, break_loop=False)
            result = actions._right_click(pos)
            return Response(message=result, break_loop=False)
        if method == "hover_at":
            pos, err = _get_xy_and_convert()
            if err:
                return Response(message=err, break_loop=False)
            result = actions._hover(pos)
            return Response(message=result, break_loop=False)
        if method == "type_text_at":
            pos, err = _get_xy_and_convert()
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
            click_result = actions._click(pos)
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
            result = actions._scroll_at(pos, amount)
            return Response(message=result, break_loop=False)

        return Response(
            message=f"Unknown method: {method}. Use index-based (click_index, double_click_index, type_text_at_index, right_click_index, hover_index, drag_index_to_index, scroll_at_index), coordinate-based (click_at, double_click_at, right_click_at, hover_at, type_text_at with x,y,text), type_text_focused (when field already focused), press_keys, wait, or close_popup.",
            break_loop=False,
        )
