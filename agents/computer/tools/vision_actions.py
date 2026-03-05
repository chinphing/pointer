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


class VisionActionsTool(Tool):
    """Execute vision_actions by index (click_index, double_click_index, type_text_at_index)."""

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
        if method == "scroll":
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
            try:
                result = actions._scroll(amount)
                return Response(message=result, break_loop=False)
            except Exception as e:
                return Response(message=str(e), break_loop=False)

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

        return Response(
            message=f"Unknown method: {method}. Use vision_actions:click_index, vision_actions:double_click_index, vision_actions:type_text_at_index, vision_actions:press_keys, or vision_actions:scroll.",
            break_loop=False,
        )
