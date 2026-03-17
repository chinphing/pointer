"""
Wait tool: pause for a number of seconds (e.g. after navigation or loading).
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


class WaitTool(Tool):
    """Wait for a specified number of seconds (e.g. for loading)."""

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
        if method != "wait":
            return Response(message="Only method 'wait' is supported. Provide goal and seconds.", break_loop=False)
        sec_arg = args.get("seconds")
        if sec_arg is None:
            return Response(message="Missing 'seconds' in tool_args.", break_loop=False)
        try:
            sec = float(sec_arg)
        except (TypeError, ValueError):
            return Response(message=f"Invalid 'seconds' value: {sec_arg}.", break_loop=False)
        if sec < 0 or sec > 60:
            return Response(message="Seconds must be between 0 and 60.", break_loop=False)
        try:
            self._get_actions()._wait(sec)
            return Response(message=f"Goal: {goal}. Waited {sec} seconds; verify result on next screenshot.", break_loop=False)
        except Exception as e:
            return Response(message=str(e), break_loop=False)
