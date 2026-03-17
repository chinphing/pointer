"""
Composite action tool: type_text_at_index, type_text_at, scroll_at_index.
One-call combos (click+type or move+scroll) — prefer over multiple tool calls.
"""
from __future__ import annotations

import os
import platform
import sys
import time
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


class CompositeActionTool(Tool):
    """One-call combos: type at index/coords, scroll at index. Prefer when one call achieves the goal."""

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
        actions = self._get_actions()
        handler = _HANDLERS.get(method)
        if handler is None:
            return Response(
                message="Use method: type_text_at_index, type_text_at, or scroll_at_index.",
                break_loop=False,
            )
        return handler(self, args, actions, goal)


def _do_type_text_at_index(tool: CompositeActionTool, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
    index_map, err = vc.get_index_map(tool.agent)
    if err is not None:
        return err
    pos, err = vc.get_single_index_pos(tool.agent, args, index_map)
    if err is not None:
        return err
    text = args.get("text", "")
    if not text:
        return Response(message="Missing 'text' in tool_args for type_text_at_index.", break_loop=False)
    clear_first = (
        args.get("clear_first")
        if isinstance(args.get("clear_first"), bool)
        else str(args.get("clear_first", "")).lower() in ("true", "1", "yes")
    )
    actions._click(pos)
    if clear_first:
        mod = "command" if platform.system() == "Darwin" else "ctrl"
        actions._press_keys([mod, "a"])
        time.sleep(0.1)
    actions._type_text(str(text))
    return _action_done(goal, args)


def _do_type_text_at(tool: CompositeActionTool, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
    pos, err = vc.get_coord_pos(tool.agent, args)
    if err is not None:
        return err
    text = args.get("text", "")
    if not text:
        return Response(message="Missing 'text' in tool_args for type_text_at.", break_loop=False)
    actions._click(pos)
    actions._type_text(str(text))
    return _action_done(goal, args)


def _do_scroll_at_index(tool: CompositeActionTool, args: Dict[str, Any], actions: ActionTools, goal: str) -> Response:
    index_map, err = vc.get_index_map(tool.agent)
    if err is not None:
        return err
    pos, err = vc.get_single_index_pos(tool.agent, args, index_map)
    if err is not None:
        return err
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
        result_msg, screen_changed = actions._scroll_at(pos, amount)
    except Exception as e:
        return Response(message=str(e), break_loop=False)
    scroll_effect = ""
    if screen_changed is not None:
        scroll_effect = " " + vc.scroll_effect_message_from_changed(screen_changed)
    return Response(message=_action_done(goal, args).message + scroll_effect, break_loop=False)


_HANDLERS: Dict[str, Any] = {
    "type_text_at_index": _do_type_text_at_index,
    "type_text_at": _do_type_text_at,
    "scroll_at_index": _do_scroll_at_index,
}
