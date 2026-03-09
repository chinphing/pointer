"""
Task-done tool for Computer Agent:
- save: when a subtask is complete, read its extract_data temp file, merge via LLM, save as formal file
- read: read all saved task_done files, return to model, and clean up the directory
"""
from __future__ import annotations

import glob
import os
import sys
from typing import Any

from agent import Agent
from python.helpers import files
from python.helpers.tool import Tool, Response

from langchain_core.messages import HumanMessage, SystemMessage

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)


def _get_extract_data_dir(agent: Agent) -> str:
    base = files.get_abs_path("agents", "computer", "extract_data")
    context_id = getattr(agent.context, "id", None) or "default"
    return os.path.join(base, context_id)


def _get_task_extracts_path(agent: Agent, task_index: int) -> str:
    return os.path.join(_get_extract_data_dir(agent), f"task_{task_index}_extracts.md")


def _get_task_done_dir(agent: Agent) -> str:
    base = files.get_abs_path("agents", "computer", "task_done")
    context_id = getattr(agent.context, "id", None) or "default"
    return os.path.join(base, context_id)


def _get_task_done_path(agent: Agent, task_index: int) -> str:
    return os.path.join(_get_task_done_dir(agent), f"task_{task_index}.md")


class TaskDoneTool(Tool):
    """Task done: save subtask results or read all results for final response."""

    async def execute(self, **kwargs: Any) -> Response:
        args = dict(self.args or {})
        for k, v in kwargs.items():
            if v is not None:
                args[k] = v

        method = getattr(self, "method", None)

        if method == "save":
            return await self._execute_save(args)
        elif method == "read":
            return await self._execute_read(args)
        else:
            return Response(
                message=f"task_done supports methods 'save' (for completing a subtask) or 'read' (for loading all results), got '{method}'.",
                break_loop=False,
            )

    async def _execute_save(self, args: dict) -> Response:
        """Save: merge extracts for a single task and save to file."""
        task_index_arg = args.get("task_index")
        if task_index_arg is None:
            return Response(
                message="task_done:save requires 'task_index' (the subtask index whose extractions to merge).",
                break_loop=False,
            )
        try:
            task_index = int(task_index_arg)
        except (TypeError, ValueError):
            return Response(
                message="task_index must be an integer.",
                break_loop=False,
            )

        extracts_path = _get_task_extracts_path(self.agent, task_index)
        if not os.path.isfile(extracts_path):
            return Response(
                message=f"No extracts file found for task {task_index} at {extracts_path}. Run extract_data first.",
                break_loop=False,
            )

        with open(extracts_path, "r", encoding="utf-8") as f:
            raw_content = f.read()
        if not raw_content.strip():
            return Response(
                message=f"Extracts file for task {task_index} is empty.",
                break_loop=False,
            )

        system = (
            "You are a document merging assistant. You receive a file that contains multiple extraction segments "
            "(each with a Target and Content in markdown). Merge them into one coherent markdown document. "
            "Preserve structure: headings, paragraphs, lists, tables. Remove duplicate or overlapping parts. "
            "Output only the merged markdown, no commentary or JSON wrapper."
        )
        user_content = f"Merge these extraction segments into one coherent markdown document:\n\n{raw_content}"
        try:
            response, _ = await self.agent.call_chat_model(
                messages=[
                    SystemMessage(content=system),
                    HumanMessage(content=user_content),
                ],
                explicit_caching=False,
            )
        except Exception as e:
            return Response(message=f"Merge call failed: {e}", break_loop=False)

        if not response or not str(response).strip():
            return Response(message="Merge returned no content.", break_loop=False)

        raw = str(response).strip()
        merged = raw
        if raw.startswith("{") and ("content" in raw or "text" in raw):
            try:
                import json
                d = json.loads(raw)
                merged = d.get("content") or d.get("text") or raw
            except Exception:
                pass
        merged = str(merged).strip() or raw
        out_path = _get_task_done_path(self.agent, task_index)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)

        return Response(
            message=f"Task {task_index} completed and saved. Continue with next subtask or call task_done:read to load all results for further usage.",
            break_loop=False,
        )

    async def _execute_read(self, args: dict) -> Response:
        """Read: load all saved task results and clean up the directory."""
        task_done_dir = _get_task_done_dir(self.agent)

        if not os.path.isdir(task_done_dir):
            return Response(
                message="No task_done directory found. No saved results to load.",
                break_loop=False,
            )

        # Find all task files
        task_files = sorted(glob.glob(os.path.join(task_done_dir, "task_*.md")))

        if not task_files:
            return Response(
                message="No saved task results found in task_done directory.",
                break_loop=False,
            )

        # Read all files
        contents = []
        for task_file in task_files:
            try:
                with open(task_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        task_name = os.path.basename(task_file)
                        contents.append(f"=== {task_name} ===\n{content}")
            except Exception:
                continue

        if not contents:
            return Response(
                message="No content found in task_done files.",
                break_loop=False,
            )

        # Aggregate all content
        aggregated = "\n\n".join(contents)

        # Clean up: remove all task files and directory
        try:
            for task_file in task_files:
                os.remove(task_file)
            # Also remove extracts files to clean up
            extract_dir = _get_extract_data_dir(self.agent)
            if os.path.isdir(extract_dir):
                extract_files = glob.glob(os.path.join(extract_dir, "task_*_extracts.md"))
                for ef in extract_files:
                    try:
                        os.remove(ef)
                    except Exception:
                        pass
                try:
                    os.rmdir(extract_dir)
                except Exception:
                    pass
            try:
                os.rmdir(task_done_dir)
            except Exception:
                pass
        except Exception as e:
            # Cleanup errors are non-critical
            pass

        return Response(
            message=f"[All Task Results Loaded]\n\n{aggregated}\n\n[Directory cleaned] All task_done and extract_data files have been removed. You can now use the data above.",
            break_loop=False,
        )
