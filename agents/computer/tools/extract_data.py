"""
Agent Zero Tool for ComputerUse: extract structured data from the current screen using the vision LLM.
Takes a screenshot, sends it to the chat model with an extraction instruction, returns the extracted content.
"""
from __future__ import annotations

import base64
import os
import sys
from io import BytesIO
from typing import Any

from agent import Agent, LoopData
from python.helpers.tool import Tool, Response

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402


EXTRACT_SYSTEM = """You are a data extraction assistant. You receive a screenshot of the current screen and an extraction instruction.
Your task is to extract the requested information from the image and return it in a clear, structured form (e.g. plain text, JSON, list, or table) as appropriate to the instruction.
Return only the extracted content, without extra commentary or markdown unless the user asks for a specific format. If something cannot be found or is unclear, say so briefly."""


def _pil_to_base64_jpeg(pil_img, quality: int = 85) -> str:
    buf = BytesIO()
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")
    pil_img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


class ExtractDataTool(Tool):
    """Extract data from the current screen using the vision model."""

    async def execute(self, **kwargs: Any) -> Response:
        args = dict(self.args or {})
        for k, v in kwargs.items():
            if v is not None:
                args[k] = v

        if not getattr(self.agent.config.chat_model, "vision", False):
            return Response(
                message="Data extraction requires a vision-capable chat model. Enable chat_model_vision.",
                break_loop=False,
            )

        instruction = args.get("instruction") or args.get("query") or ""
        if not (instruction and str(instruction).strip()):
            return Response(
                message="Missing 'instruction' (or 'query') in tool_args. Describe what to extract from the screen (e.g. 'extract all visible links', 'list the table rows as JSON').",
                break_loop=False,
            )

        try:
            import screen as screen_mod  # noqa: E402
            img, _mon_bbox = screen_mod.screenshot_current_monitor()
        except Exception as e:
            return Response(
                message=f"Screen capture failed: {e}.",
                break_loop=False,
            )

        b64 = _pil_to_base64_jpeg(img)
        user_content = [
            {"type": "text", "text": str(instruction).strip()},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]

        messages = [
            SystemMessage(content=EXTRACT_SYSTEM),
            HumanMessage(content=user_content),
        ]

        try:
            response, _reasoning = await self.agent.call_chat_model(
                messages=messages,
                explicit_caching=False,
            )
        except Exception as e:
            return Response(
                message=f"Extraction model call failed: {e}.",
                break_loop=False,
            )

        return Response(
            message=(response or "").strip() or "(No content extracted.)",
            break_loop=False,
        )

    async def after_execution(self, response: Response, **kwargs: Any) -> None:
        self.agent.set_data(
            "computer_last_vision_action",
            {
                "tool": self.name,
                "method": self.method or "extract",
                "args": dict(self.args or {}),
                "result": (response.message or "").strip()[:500],
            },
        )
        await super().after_execution(response, **kwargs)
