"""
Extract data from the current screen for the Computer Agent.
- extract: capture visible content, append to task temp file, return a short summary in the response.
- load: load previously saved task data (after task_done) for use in later tasks; no re-extraction.
"""
from __future__ import annotations

import base64
import os
import sys
from io import BytesIO
from typing import Any

from agent import Agent
from python.helpers.tool import Tool, Response

from langchain_core.messages import HumanMessage, SystemMessage

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)
from task_data_memory import TaskDataMemory

SUMMARY_MAX_CHARS_DEFAULT = 400  # default max chars of saved content in extract response
AGENT_KEY_SUMMARY_MAX_CHARS = "computer_extract_summary_max_chars"


def _pil_to_base64_jpeg(pil_img, quality: int = 85) -> str:
    buf = BytesIO()
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")
    pil_img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _summary_of_content(text: str, max_chars: int = SUMMARY_MAX_CHARS_DEFAULT) -> str:
    """Return a short summary of content for the response (first lines/chars)."""
    if not (text or "").strip():
        return "(empty)"
    lines = text.strip().splitlines()
    out: list[str] = []
    n = 0
    for line in lines:
        if n + len(line) + 1 > max_chars:
            if n > 0:
                out.append(line[: max_chars - n] + "…")
            break
        out.append(line)
        n += len(line) + 1
    return "\n".join(out) if out else text[:max_chars] + "…"


class ExtractDataTool(Tool):
    """Extract visible content (extract) or load previously saved task data (load)."""

    def _parse_task_indices(self, task_index_arg: Any) -> list[int]:
        """Parse task_index as single int or list/seq of ints (e.g. [1,2,3] or '1,2,3')."""
        if task_index_arg is None:
            return []
        if isinstance(task_index_arg, list):
            out = []
            for x in task_index_arg:
                try:
                    out.append(int(x))
                except (TypeError, ValueError):
                    continue
            return out
        if isinstance(task_index_arg, str) and "," in task_index_arg:
            out = []
            for part in task_index_arg.split(","):
                try:
                    out.append(int(part.strip()))
                except (TypeError, ValueError):
                    continue
            return out
        try:
            return [int(task_index_arg)]
        except (TypeError, ValueError):
            return []

    async def _execute_load(self, args: dict) -> Response:
        """Load saved task data via memory system. Supports one or multiple task_index."""
        indices = self._parse_task_indices(args.get("task_index"))
        if not indices:
            return Response(
                message="extract_data:load requires 'task_index' (one number or list/comma-separated, e.g. 1 or [1,2] or '1,2').",
                break_loop=False,
            )
        memory = TaskDataMemory(self.agent)
        content, missing = await memory.load_tasks(indices)
        if missing:
            return Response(
                message=f"Task(s) {missing} not found. Complete those with task_done first. Loaded: {[i for i in indices if i not in missing]}.",
                break_loop=False,
            )
        saved_list = self.agent.get_data("computer_saved_task_indices") or []
        hint = f" (Saved tasks available for load: {saved_list})" if saved_list else ""
        return Response(
            message=f"[Loaded tasks {indices}]{hint}\n\n{content}",
            break_loop=False,
        )

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

        method = (getattr(self, "method", None) or "").strip().lower()
        if method == "load":
            return await self._execute_load(args)
        if method and method != "extract":
            return Response(
                message=f"extract_data supports 'extract' and 'load', got '{self.method}'.",
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
        memory = TaskDataMemory(self.agent)
        memory.save_fragment(task_index, instruction, markdown_content)
        max_chars = SUMMARY_MAX_CHARS_DEFAULT
        try:
            v = self.agent.get_data(AGENT_KEY_SUMMARY_MAX_CHARS)
            if v is not None:
                max_chars = int(v)
        except (TypeError, ValueError):
            pass
        summary = _summary_of_content(markdown_content, max_chars)
        return Response(
            message=(
                f"Task {task_index} extract saved.\n\n"
                f"**Saved data summary:**\n{summary}\n\n"
                "Next: scroll if needed and extract again, or call task_done with this task_index when the task is complete. "
                "To use this data in a later task, call extract_data:load with that task_index after it has been saved by task_done."
            ),
            break_loop=False,
        )
