"""
Hotkey tool: press key combinations (e.g. Cmd+C, Ctrl+V).
"""
from __future__ import annotations

import json
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


class HotkeyTool(Tool):
    """Press key combinations (e.g. Cmd+C, Ctrl+V)."""

    async def after_execution(self, response: Response, **kwargs: Any) -> None:
        vc.vision_after_execution(
            self.agent,
            self.name,
            "",
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
        keys = args.get("keys")
        if not keys:
            return Response(message='Missing \'keys\' in tool_args (e.g. ["ctrl", "c"]).', break_loop=False)
        if isinstance(keys, str):
            if keys.startswith("[") and keys.endswith("]"):
                keys = json.loads(keys)
            else:
                keys = [k.strip() for k in keys.split(",")]
        else:
            keys = list(keys)
        try:
            self._get_actions()._press_keys(keys)
            return Response(message=f"Goal: {goal}. Action executed; verify result on next screenshot.", break_loop=False)
        except Exception as e:
            return Response(message=str(e), break_loop=False)
