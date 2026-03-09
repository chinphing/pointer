"""
Extract data from the current screen for the Computer Agent.
Output format: markdown. Trigger: when you need to read or extract page data for temporary storage.
Each call appends to a task-specific temp file; task_done later reads and summarizes that file.
"""
from __future__ import annotations

import base64
import os
import sys
from io import BytesIO
from typing import Any

from agent import Agent
from python.helpers import files
from python.helpers.tool import Tool, Response

from langchain_core.messages import HumanMessage, SystemMessage

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)


def _pil_to_base64_jpeg(pil_img, quality: int = 85) -> str:
    buf = BytesIO()
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")
    pil_img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _get_extract_data_dir(agent: Agent) -> str:
    """Return absolute path for this context's extract_data directory."""
    base = files.get_abs_path("agents", "computer", "extract_data")
    context_id = getattr(agent.context, "id", None) or "default"
    return os.path.join(base, context_id)


def _get_task_extracts_path(agent: Agent, task_index: int) -> str:
    """Path to the temp file for task_index (append mode)."""
    return os.path.join(_get_extract_data_dir(agent), f"task_{task_index}_extracts.md")


def _append_extract(agent: Agent, task_index: int, instruction: str, markdown_content: str) -> None:
    """Append one extraction (target + content) to the task's temp file."""
    path = _get_task_extracts_path(agent, task_index)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    block = f"\n\n---\n\n## Target\n{instruction}\n\n## Content\n{markdown_content}\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(block)


class ExtractDataTool(Tool):
    """Extract visible content from the current screen as markdown and append to task temp file."""

    async def execute(self, **kwargs: Any) -> Response:
        args = dict(self.args or {})
        for k, v in kwargs.items():
            if v is not None:
                args[k] = v

        instruction = args.get("instruction")
        task_index_arg = args.get("task_index")
        if not instruction or not str(instruction).strip():
            return Response(
                message="extract_data requires 'instruction' (what to extract) and 'task_index' (for file naming).",
                break_loop=False,
            )
        if task_index_arg is None:
            return Response(
                message="extract_data requires 'task_index' (subtask index for file naming).",
                break_loop=False,
            )
        try:
            task_index = int(task_index_arg)
        except (TypeError, ValueError):
            return Response(
                message="task_index must be an integer.",
                break_loop=False,
            )

        if getattr(self, "method", None) and self.method != "extract":
            return Response(
                message=f"extract_data only supports method 'extract', got '{self.method}'.",
                break_loop=False,
            )
        if not getattr(self.agent.config.chat_model, "vision", False):
            return Response(
                message="Data extraction requires a vision-capable chat model. Enable chat_model_vision.",
                break_loop=False,
            )

        try:
            import screen as screen_mod
            img, _ = screen_mod.screenshot_current_monitor()
        except Exception as e:
            return Response(message=f"Screen capture failed: {e}", break_loop=False)

        b64 = _pil_to_base64_jpeg(img)
        system = (
            "You are a data extraction assistant. You receive a screenshot and an extraction instruction. "
            "Extract the requested information from the image and return it in markdown only. "
            "Return only the extracted content in markdown (headings, paragraphs, lists, tables as markdown). "
            "No JSON, no commentary, no wrapper."
        )
        user_content = [
            {"type": "text", "text": f"Extract the following (return markdown only):\n{instruction}"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]
        try:
            response, _ = await self.agent.call_chat_model(
                messages=[
                    SystemMessage(content=system),
                    HumanMessage(content=user_content),
                ],
                explicit_caching=False,
            )
        except Exception as e:
            return Response(message=f"Extraction call failed: {e}", break_loop=False)

        if not response or not str(response).strip():
            return Response(message="Extraction returned no content.", break_loop=False)

        raw = str(response).strip()
        markdown_content = raw
        if raw.startswith("{") and ("content" in raw or "text" in raw):
            try:
                import json
                d = json.loads(raw)
                markdown_content = d.get("content") or d.get("text") or raw
            except Exception:
                pass
        markdown_content = str(markdown_content).strip() or raw
        _append_extract(self.agent, task_index, instruction, markdown_content)
        path = _get_task_extracts_path(self.agent, task_index)
        return Response(
            message=f"Current visible content for task {task_index} have been extracted. Don't call extract_data again, unless you do another vision_actions/... and changed the content.",
            break_loop=False,
        )
