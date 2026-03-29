"""
Composite action tool: type_text_at_index, type_text_at, type_text_at_focused_input, scroll_at_index.
One-call combos (click+type or move+scroll) — prefer over multiple tool calls.
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
from actions import RawAction  # noqa: E402

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


def _type_action_done(goal: str, context: str) -> Response:
    """Type-related composite actions; model should confirm on the next screenshot."""
    ctx = context.rstrip(".")
    return Response(
        message=(
            f"Goal: {goal}. Type action executed ({ctx}). "
            "Please verify result on next screenshot."
        ),
        break_loop=False,
    )


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

    async def execute(self, **kwargs: Any) -> Response:
        args = dict(self.args or {})
        for k, v in kwargs.items():
            if v is not None:
                args[k] = v
        goal = str(args.get("goal", "")).strip()
        if not goal:
            return Response(message="Missing required 'goal' in tool_args.", break_loop=False)
        method = (self.method or "").strip()
        handler = _HANDLERS.get(method)
        if handler is None:
            return Response(
                message="Use method: type_text_at_index, type_text_at, type_text_at_focused_input, or scroll_at_index.",
                break_loop=False,
            )
        return handler(self, args, goal)


def _do_type_text_at_index(tool: CompositeActionTool, args: Dict[str, Any], goal: str) -> Response:
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
    human_like = _get_human_like(args)
    
    # Move to position and click
    MouseHelper.click_at(pos, human_like=human_like)
    
    # Type text
    actions = RawAction(dry_run=False)
    actions._type_text(str(text), clear_field_first=clear_first)
    return _type_action_done(goal, "into field at annotated index (composite_action).")


def _do_type_text_at(tool: CompositeActionTool, args: Dict[str, Any], goal: str) -> Response:
    pos, err = vc.get_coord_pos(tool.agent, args)
    if err is not None:
        return err
    text = args.get("text", "")
    if not text:
        return Response(message="Missing 'text' in tool_args for type_text_at.", break_loop=False)
    human_like = _get_human_like(args)
    
    # Move to position and click
    MouseHelper.click_at(pos, human_like=human_like)
    
    # Type text
    actions = RawAction(dry_run=False)
    actions._type_text(str(text))
    return _type_action_done(goal, "normalized coordinates, composite_action")


def _do_type_text_at_focused_input(tool: CompositeActionTool, args: Dict[str, Any], goal: str) -> Response:
    """Type into the currently focused input (no click). Use when an input already has focus."""
    text = args.get("text", "")
    if not text:
        return Response(message="Missing 'text' in tool_args for type_text_at_focused_input.", break_loop=False)
    clear_existing = (
        args.get("clear_existing")
        if isinstance(args.get("clear_existing"), bool)
        else str(args.get("clear_existing", "")).lower() in ("true", "1", "yes")
    )
    actions = RawAction(dry_run=False)
    actions._type_text(str(text), clear_field_first=clear_existing)
    return _type_action_done(goal, "currently focused input, composite_action")


def _do_scroll_at_index(tool: CompositeActionTool, args: Dict[str, Any], goal: str) -> Response:
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
    
    # Move to position
    human_like = _get_human_like(args)
    MouseHelper.move_to_position(pos, human_like=human_like)
    
    # Scroll
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
    "type_text_at_index": _do_type_text_at_index,
    "type_text_at": _do_type_text_at,
    "type_text_at_focused_input": _do_type_text_at_focused_input,
    "scroll_at_index": _do_scroll_at_index,
}
