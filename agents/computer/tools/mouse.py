"""
Mouse tool: click, double-click, right-click, hover, drag, scroll at current.
Uses index_map or normalized coordinates; no delta_x/delta_y/target_in_bbox.
"""
from __future__ import annotations

import os
import platform
import sys
from typing import Any, Dict

from agent import Agent, LoopData
from python.helpers.tool import Tool, Response

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)
from actions import ActionTools  # noqa: E402

from tools import vision_common as vc  # noqa: E402


def _action_done(goal: str, args: Dict[str, Any], extra: str = "") -> Response:
    msg = f"Goal: {goal}. Action executed; verify result on next screenshot."
    if extra:
        msg = f"Goal: {goal}. {extra} Verify result on next screenshot."
    return Response(message=msg, break_loop=False)


class MouseTool(Tool):
    """Mouse actions by index or coordinates: click, double_click, right_click, hover, drag, scroll_at_current."""

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
        if not method:
            return Response(message="Missing method (e.g. click_index, click_at).", break_loop=False)
        actions = self._get_actions()
        handler = _HANDLERS.get(method)
        if handler is None:
            return Response(
                message=f"Unknown method: {method}. Use: click_index, double_click_index, right_click_index, hover_index, drag_index_to_index, click_at, double_click_at, right_click_at, hover_at, scroll_at_current.",
                break_loop=False,
            )
        return handler(self, args, actions, goal)


def _do_click_index(tool: MouseTool, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
    index_map, err = vc.get_index_map(tool.agent)
    if err is not None:
        return err
    pos, err = vc.get_single_index_pos(tool.agent, args, index_map)
    if err is not None:
        return err
    actions._click(pos)
    return _action_done(goal, args)


def _do_double_click_index(tool: MouseTool, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
    index_map, err = vc.get_index_map(tool.agent)
    if err is not None:
        return err
    pos, err = vc.get_single_index_pos(tool.agent, args, index_map)
    if err is not None:
        return err
    actions._double_click(pos)
    return _action_done(goal, args)


def _do_right_click_index(tool: MouseTool, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
    index_map, err = vc.get_index_map(tool.agent)
    if err is not None:
        return err
    pos, err = vc.get_single_index_pos(tool.agent, args, index_map)
    if err is not None:
        return err
    actions._right_click(pos)
    return _action_done(goal, args)


def _do_hover_index(tool: MouseTool, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
    index_map, err = vc.get_index_map(tool.agent)
    if err is not None:
        return err
    pos, err = vc.get_single_index_pos(tool.agent, args, index_map)
    if err is not None:
        return err
    actions._hover(pos)
    return _action_done(goal, args)


def _do_drag_index_to_index(tool: MouseTool, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
    index_map, err = vc.get_index_map(tool.agent)
    if err is not None:
        return err
    pos, err = vc.get_single_index_pos(tool.agent, args, index_map, for_drag=True)
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
        to_pos = vc.resolve_index(index_map, to_index)
    except ValueError as e:
        return Response(message=str(e), break_loop=False)
    actions._drag(pos, to_pos)
    return _action_done(goal, args)


def _do_click_at(tool: MouseTool, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
    pos, err = vc.get_coord_pos(tool.agent, args)
    if err is not None:
        return err
    actions._click(pos)
    return _action_done(goal, args)


def _do_double_click_at(tool: MouseTool, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
    pos, err = vc.get_coord_pos(tool.agent, args)
    if err is not None:
        return err
    actions._double_click(pos)
    return _action_done(goal, args)


def _do_right_click_at(tool: MouseTool, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
    pos, err = vc.get_coord_pos(tool.agent, args)
    if err is not None:
        return err
    actions._right_click(pos)
    return _action_done(goal, args)


def _do_hover_at(tool: MouseTool, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
    pos, err = vc.get_coord_pos(tool.agent, args)
    if err is not None:
        return err
    actions._hover(pos)
    return _action_done(goal, args)


def _do_scroll_at_current(tool: MouseTool, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
    amount_arg = args.get("amount")
    if amount_arg is None:
        return Response(message="Missing 'amount' in tool_args (positive=up, negative=down).", break_loop=False)
    try:
        amount = int(amount_arg)
    except (TypeError, ValueError):
        return Response(message=f"Invalid 'amount' value: {amount_arg}.", break_loop=False)
    if amount == 0:
        return Response(message="Amount cannot be 0.", break_loop=False)
    amount = vc.clamp_scroll_amount(amount)
    try:
        result_msg, screen_changed = actions._scroll(amount)
    except Exception as e:
        return Response(message=str(e), break_loop=False)
    scroll_effect = ""
    if screen_changed is not None:
        scroll_effect = " " + vc.scroll_effect_message_from_changed(screen_changed)
    return Response(message=_action_done(goal, args).message + scroll_effect, break_loop=False)


_HANDLERS: Dict[str, Any] = {
    "click_index": _do_click_index,
    "double_click_index": _do_double_click_index,
    "right_click_index": _do_right_click_index,
    "hover_index": _do_hover_index,
    "drag_index_to_index": _do_drag_index_to_index,
    "click_at": _do_click_at,
    "double_click_at": _do_double_click_at,
    "right_click_at": _do_right_click_at,
    "hover_at": _do_hover_at,
    "scroll_at_current": _do_scroll_at_current,
}
