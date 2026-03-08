"""
Partially-done save tool for Computer Agent: persist staged progress (goal, plan,
completed/pending, current step, last error, experience). Tool_args are already the merged
snapshot—the tool only saves and inserts into history; no LLM merge call.
"""
from __future__ import annotations

import os
import sys
from typing import Any

from agent import Agent
from python.helpers import files
from python.helpers.tool import Tool, Response

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)

PREFIX_INSERT = "[Partially done]\n\n"

_SECTIONS = (
    ("Goal", "goal"),
    ("Plan", "plan"),
    ("Completed", "completed"),
    ("Pending", "pending"),
    ("Current step", "current_step"),
    ("Last error", "last_error"),
    ("Experience", "experience"),
)


def _get_partially_done_path(agent: Agent, step: int | None = None, version: str | None = None) -> str:
    """Return absolute path for this session's partially-done file."""
    base = files.get_abs_path("agents", "computer", "partially_done")
    context_id = getattr(agent.context, "id", None) or "default"
    session_dir = os.path.join(base, context_id)
    if step is not None:
        name = f"partially_done_{step}.md"
    elif version:
        name = f"partially_done_{version}.md"
    else:
        name = "partially_done.md"
    return os.path.join(session_dir, name)


def _save_partially_done(path: str, content: str) -> None:
    """Write content to path; create parent dir if needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _tool_args_to_markdown(tool_args: dict[str, Any]) -> str:
    """Format tool_args as Markdown with ## headers. Only include non-empty fields."""
    parts = []
    for title, key in _SECTIONS:
        v = tool_args.get(key)
        if v is not None and str(v).strip():
            parts.append(f"## {title}\n\n{v.strip()}")
    return "\n\n".join(parts) if parts else ""


class PartiallyDoneTool(Tool):
    """Save partially-done: tool_args are the merged snapshot; save to file and insert into history (no LLM)."""

    async def execute(self, **kwargs: Any) -> Response:
        args = dict(self.args or {})
        for k, v in kwargs.items():
            if v is not None:
                args[k] = v

        if self.method != "save":
            return Response(
                message=f"partially_done only supports method 'save', got '{self.method}'.",
                break_loop=False,
            )

        allowed = {"goal", "plan", "completed", "pending", "current_step", "last_error", "experience",
                   "trim_history_before", "step", "version", "clear"}
        tool_args = {k: v for k, v in args.items() if k in allowed}
        has_update = any(
            tool_args.get(k) not in (None, "") and str(tool_args.get(k)).strip()
            for k in ("goal", "plan", "completed", "pending", "current_step", "last_error", "experience")
        )
        if not has_update and not tool_args.get("clear"):
            return Response(
                message="Provide at least one of: goal, plan, completed, pending, current_step, last_error, experience (or clear: true to reset).",
                break_loop=False,
            )

        step = tool_args.get("step")
        version = tool_args.get("version")
        trim_before = bool(tool_args.get("trim_history_before"))
        do_clear = bool(tool_args.get("clear"))

        path = _get_partially_done_path(self.agent, step=step, version=version)

        if do_clear:
            _save_partially_done(path, "")
            self.agent.hist_add_message(False, content="[Partially done] Session partially-done file has been cleared.")
            return Response(message="Partially-done file cleared.", break_loop=False)

        content = _tool_args_to_markdown(tool_args)
        if not content:
            return Response(
                message="No content to save; provide at least one of goal, plan, completed, pending, current_step, last_error, experience.",
                break_loop=False,
            )

        _save_partially_done(path, content)
        self.agent.hist_add_message(False, content=PREFIX_INSERT + content)

        if trim_before:
            msgs = self.agent.history.current.messages
            if len(msgs) >= 2:
                first_user = next((m for m in msgs if not getattr(m, "ai", True)), None)
                if first_user is not None:
                    self.agent.history.current.messages = [first_user, msgs[-1]]
                else:
                    self.agent.history.current.messages = [msgs[0], msgs[-1]]

        return Response(
            message="Partially done saved; inserted into history."
            + (" History trimmed to first user message + this result." if trim_before else ""),
            break_loop=False,
        )
