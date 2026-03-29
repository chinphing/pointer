"""
Mouse tool: click, double-click, right-click, hover, scroll at current.
Uses index_map or normalized coordinates; no delta_x/delta_y/target_in_bbox.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict

from agent import Agent, LoopData
from python.helpers.tool import Tool, Response

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)
from mouse_move import MouseHelper  # noqa: E402

from tools import vision_common as vc  # noqa: E402


def _get_human_like_default() -> bool:
    """Get default human_like setting from config."""
    try:
        from python.helpers import settings as settings_mod
        return bool(settings_mod.get_settings().get("computer_human_like", False))
    except Exception:
        return False


def _get_human_like(args: Dict[str, Any]) -> bool:
    """Get human_like value from args or config default."""
    if "human_like" in args:
        return bool(args["human_like"])
    return _get_human_like_default()


def _action_done(goal: str, args: Dict[str, Any], extra: str = "") -> Response:
    msg = f"Goal: {goal}. Action executed; verify result on next screenshot."
    if extra:
        msg = f"Goal: {goal}. {extra} Verify result on next screenshot."
    return Response(message=msg, break_loop=False)


class MouseTool(Tool):
    """Mouse actions by index or coordinates: click, double_click, right_click, hover, scroll_at_current."""

    async def after_execution(self, response: Response, **kwargs: Any) -> None:
        vc.vision_after_execution(
            self.agent,
            self.name,
            (self.method or "").strip(),
            self.args or {},
            (response.message or "").strip(),
        )
        await super().after_execution(response, **kwargs)

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
        handler = _HANDLERS.get(method)
        if handler is None:
            return Response(
                message=f"Unknown method: {method}. Use: click_index, double_click_index, right_click_index, hover_index, click_at, double_click_at, right_click_at, hover_at, scroll_at_current.",
                break_loop=False,
            )
        return handler(self, args, goal)


def _do_click_index(tool: MouseTool, args: Dict[str, Any], goal: str) -> Response:
    index_map, err = vc.get_index_map(tool.agent)
    if err is not None:
        return err
    pos, err = vc.get_single_index_pos(tool.agent, args, index_map)
    if err is not None:
        return err
    human_like = _get_human_like(args)
    MouseHelper.click_at(pos, human_like=human_like)
    return _action_done(goal, args)


def _do_double_click_index(tool: MouseTool, args: Dict[str, Any], goal: str) -> Response:
    index_map, err = vc.get_index_map(tool.agent)
    if err is not None:
        return err
    pos, err = vc.get_single_index_pos(tool.agent, args, index_map)
    if err is not None:
        return err
    human_like = _get_human_like(args)
    MouseHelper.double_click_at(pos, human_like=human_like)
    return _action_done(goal, args)


def _do_right_click_index(tool: MouseTool, args: Dict[str, Any], goal: str) -> Response:
    index_map, err = vc.get_index_map(tool.agent)
    if err is not None:
        return err
    pos, err = vc.get_single_index_pos(tool.agent, args, index_map)
    if err is not None:
        return err
    human_like = _get_human_like(args)
    MouseHelper.right_click_at(pos, human_like=human_like)
    return _action_done(goal, args)


def _do_hover_index(tool: MouseTool, args: Dict[str, Any], goal: str) -> Response:
    index_map, err = vc.get_index_map(tool.agent)
    if err is not None:
        return err
    pos, err = vc.get_single_index_pos(tool.agent, args, index_map)
    if err is not None:
        return err
    human_like = _get_human_like(args)
    MouseHelper.hover_at(pos, human_like=human_like)
    return _action_done(goal, args)


def _do_click_at(tool: MouseTool, args: Dict[str, Any], goal: str) -> Response:
    pos, err = vc.get_coord_pos(tool.agent, args)
    if err is not None:
        return err
    human_like = _get_human_like(args)
    MouseHelper.click_at(pos, human_like=human_like)
    return _action_done(goal, args)


def _do_double_click_at(tool: MouseTool, args: Dict[str, Any], goal: str) -> Response:
    pos, err = vc.get_coord_pos(tool.agent, args)
    if err is not None:
        return err
    human_like = _get_human_like(args)
    MouseHelper.double_click_at(pos, human_like=human_like)
    return _action_done(goal, args)


def _do_right_click_at(tool: MouseTool, args: Dict[str, Any], goal: str) -> Response:
    pos, err = vc.get_coord_pos(tool.agent, args)
    if err is not None:
        return err
    human_like = _get_human_like(args)
    MouseHelper.right_click_at(pos, human_like=human_like)
    return _action_done(goal, args)


def _do_hover_at(tool: MouseTool, args: Dict[str, Any], goal: str) -> Response:
    pos, err = vc.get_coord_pos(tool.agent, args)
    if err is not None:
        return err
    human_like = _get_human_like(args)
    MouseHelper.hover_at(pos, human_like=human_like)
    return _action_done(goal, args)


def _do_scroll_at_current(tool: MouseTool, args: Dict[str, Any], goal: str) -> Response:
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
    # Scroll at current position using MouseHelper's scroll via RawAction
    from actions import RawAction
    actions = RawAction(dry_run=False)
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
    "click_at": _do_click_at,
    "double_click_at": _do_double_click_at,
    "right_click_at": _do_right_click_at,
    "hover_at": _do_hover_at,
    "scroll_at_current": _do_scroll_at_current,
}
