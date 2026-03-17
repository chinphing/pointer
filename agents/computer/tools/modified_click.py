"""
Modified-click tool: modifier+click for multi-select (e.g. Cmd/Ctrl+click).
Supports index-based (modified_click_index) and coordinate-based (modified_click_at).
"""
from __future__ import annotations

import os
import platform
import sys
from typing import Any, Dict, List

from agent import Agent, LoopData
from python.helpers.tool import Tool, Response

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)
from actions import ActionTools  # noqa: E402

from tools import vision_common as vc  # noqa: E402


class ModifiedClickTool(Tool):
    """Modifier+click (e.g. Cmd/Ctrl+click) to add multiple items to selection."""

    async def after_execution(self, response: Response, **kwargs: Any) -> None:
        vc.vision_after_execution(
            self.agent,
            self.name,
            (self.method or "").strip(),
            self.args or {},
            (response.message or "").strip(),
        )
        await super().after_execution(response, **kwargs)

    def _get_actions(self) -> ActionTools:
        paste_key = ["command", "v"] if platform.system() == "Darwin" else ["ctrl", "v"]
        return ActionTools(dry_run=False, paste_key=paste_key)

    async def execute(self, **kwargs: Any) -> Response:
        args = dict(self.args or {})
        for k, v in kwargs.items():
            if v is not None:
                args[k] = v
        goal = str(args.get("goal", "")).strip()
        if not goal:
            return Response(message="Missing required 'goal' in tool_args.", break_loop=False)
        method = (self.method or "").strip()
        if method == "modified_click_index":
            return self._do_modified_click_index(args, goal)
        if method == "modified_click_at":
            return self._do_modified_click_at(args, goal)
        return Response(
            message="Use method 'modified_click_index' (indices, goal) or 'modified_click_at' (goal, positions).",
            break_loop=False,
        )

    def _do_modified_click_index(self, args: Dict[str, Any], goal: str) -> Response:
        index_map, err = vc.get_index_map(self.agent)
        if err is not None:
            return err
        index_list, parse_err = vc.parse_indices(args.get("indices"))
        if parse_err is not None:
            return Response(message=parse_err, break_loop=False)
        range_select = args.get("range_select") in (True, "true", "1", "yes")
        positions: List[List[int]] = []
        try:
            for idx in index_list:
                if idx < 1 or idx not in index_map:
                    continue
                positions.append(vc.resolve_index(index_map, idx))
        except ValueError as e:
            return Response(message=str(e), break_loop=False)
        if not positions:
            return Response(message="No valid indices resolved to positions.", break_loop=False)
        actions = self._get_actions()
        if range_select:
            if len(positions) != 2:
                return Response(
                    message="For range_select, indices must be exactly two numbers [first, last] in order.",
                    break_loop=False,
                )
            actions._click_range_selection(positions[0], positions[1])
            return Response(
                message=f"Goal: {goal}. Shift+click range from first to last item selected. Verify result on next screenshot.",
                break_loop=False,
            )
        actions._click_add_to_selection_batch(positions)
        return Response(
            message=f"Goal: {goal}. Held modifier and clicked {len(positions)} item(s) for multi-select. Verify result on next screenshot.",
            break_loop=False,
        )

    def _do_modified_click_at(self, args: Dict[str, Any], goal: str) -> Response:
        positions, err = vc.get_coord_positions(self.agent, args.get("positions"))
        if err is not None:
            return err
        range_select = args.get("range_select") in (True, "true", "1", "yes")
        actions = self._get_actions()
        if range_select:
            if len(positions) != 2:
                return Response(
                    message="For range_select, positions must be exactly two [first, last] in order.",
                    break_loop=False,
                )
            actions._click_range_selection(positions[0], positions[1])
            return Response(
                message=f"Goal: {goal}. Shift+click range from first to last position selected. Verify result on next screenshot.",
                break_loop=False,
            )
        actions._click_add_to_selection_batch(positions)
        return Response(
            message=f"Goal: {goal}. Held modifier and clicked {len(positions)} position(s). Verify result on next screenshot.",
            break_loop=False,
        )
