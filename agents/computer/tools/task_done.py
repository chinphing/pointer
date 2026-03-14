"""
Task-done tool for Computer Agent.
Uses TaskDataMemory for merge and full load.
- Default (task_index): Mark a subtask complete; memory merges fragments for that task and saves.
- read: Load all saved task results via memory (then cleanup); call once at the end before response.
"""
from __future__ import annotations

import os, sys
from typing import Any

from agent import Agent
from python.helpers.tool import Tool, Response

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)
from task_data_memory import TaskDataMemory

SAVED_TASK_LIST_KEY = "computer_saved_task_indices"


def _saved_summary_line(task_index: int, merged_content: str, max_chars: int = 80) -> str:
    """One line for saved-data summary: Task N: saved … data; to use it, call extract_data:load with task_index=N."""
    brief = (merged_content or "").strip().replace("\n", " ")[:max_chars]
    if len((merged_content or "").strip()) > max_chars:
        brief = brief.rstrip() + "…"
    return f"Task {task_index}: saved {brief or '(empty)'} data. To use it, call extract_data:load with task_index={task_index}."


class TaskDoneTool(Tool):
    """Task done: save subtask results or read all results for final response."""

    async def execute(self, **kwargs: Any) -> Response:
        args = dict(self.args or {})
        for k, v in kwargs.items():
            if v is not None:
                args[k] = v

        method = (getattr(self, "method", None) or "").strip().lower()

        if method == "read":
            return await self._execute_read(args)
        # Default: complete task (task_index required). Auto-merge if fragments exist.
        task_index_arg = args.get("task_index")
        if task_index_arg is not None:
            return await self._execute_complete_task(args)
        return Response(
            message="task_done requires either 'task_index' (to mark a task complete; fragments are auto-merged) or method 'read' (no args) to load all saved results.",
            break_loop=False,
        )

    async def _execute_complete_task(self, args: dict) -> Response:
        """Mark task complete. Memory merges fragments for this task_index if they exist."""
        try:
            task_index = int(args.get("task_index"))
        except (TypeError, ValueError):
            return Response(
                message="task_index must be an integer.",
                break_loop=False,
            )
        memory = TaskDataMemory(self.agent)
        merged_path, merged_content = await memory.merge_task(task_index)
        if merged_path and merged_content:
            summary_line = _saved_summary_line(task_index, merged_content)
            saved_list: list = list(self.agent.get_data(SAVED_TASK_LIST_KEY) or [])
            if task_index not in saved_list:
                saved_list.append(task_index)
                saved_list.sort()
                self.agent.set_data(SAVED_TASK_LIST_KEY, saved_list)
            list_hint = f" Saved tasks (available for extract_data:load): {saved_list}." if saved_list else ""
            return Response(
                message=(
                    f"Task {task_index} completed. Extracts were merged and saved.\n\n"
                    f"**Saved data summary:**\n{summary_line}\n\n"
                    f"Continue with next subtask or call task_done:read when all tasks are done.{list_hint}"
                ),
                break_loop=False,
            )
        return Response(
            message=(
                f"Task {task_index} marked complete. No extract fragments were found for this task (nothing to merge). "
                "Note in plans that this task had no data; continue with next subtask or task_done:read when all are done. "
                "Continue with next subtask or call task_done:read when all tasks are done."
            ),
            break_loop=False,
        )

    async def _execute_read(self, args: dict) -> Response:
        """Read: load all saved task results via memory (cleanup done inside memory). Call once at the end before response."""
        memory = TaskDataMemory(self.agent)
        aggregated, success = await memory.load_all_tasks()
        self.agent.set_data(SAVED_TASK_LIST_KEY, [])
        if not success:
            return Response(
                message="No saved task results found. Complete tasks with task_done first, then call task_done:read when all are done.",
                break_loop=False,
            )
        return Response(
            message=f"[All Task Results Loaded]\n\n{aggregated}\n\n[Directory cleaned] You can now use the data above.",
            break_loop=False,
        )
