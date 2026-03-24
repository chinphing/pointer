"""
Task-done tool for Computer Agent.
Uses TaskDataMemory for merge, execution checkpoint (plans / progress / learnings), and full load.
- checkpoint: Merge fragments for task_index; write execution state; truncate (see prompts).
- read: Load all saved task results (then cleanup); append session learnings summary for final response.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Optional, Tuple

from python.helpers.tool import Tool, Response

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)
from task_data_memory import (  # noqa: E402
    COMPUTER_TURNS_SINCE_TASK_DONE_KEY,
    TaskDataMemory,
)

SAVED_TASK_LIST_KEY = "computer_saved_task_indices"


def _saved_summary_line(task_index: int, merged_content: str, max_chars: int = 80) -> str:
    brief = (merged_content or "").strip().replace("\n", " ")[:max_chars]
    if len((merged_content or "").strip()) > max_chars:
        brief = brief.rstrip() + "…"
    return (
        f"Task {task_index}: saved {brief or '(empty)'} data. "
        "Rely on **Persisted execution state** and extract summaries in thread for mid-flow context; "
        "use **task_done:read** at the end for full aggregation."
    )


def _reset_task_done_turn_counter(agent: Any) -> None:
    agent.set_data(COMPUTER_TURNS_SINCE_TASK_DONE_KEY, 0)


def _learnings_from_args(args: dict, default_task_index: Optional[int] = None) -> Tuple[Optional[str], Optional[int]]:
    raw = args.get("learnings")
    if raw is None:
        raw = args.get("experience_delta")
    if raw is None:
        return None, None
    s = str(raw).strip()
    if not s:
        return None, None
    lti = args.get("learnings_task_index")
    try:
        li = int(lti) if lti is not None else None
    except (TypeError, ValueError):
        li = None
    if li is None and default_task_index is not None:
        li = default_task_index
    return s, li


def _append_saved_task(agent: Any, task_index: int) -> list:
    saved_list: list = list(agent.get_data(SAVED_TASK_LIST_KEY) or [])
    if task_index not in saved_list:
        saved_list.append(task_index)
        saved_list.sort()
        agent.set_data(SAVED_TASK_LIST_KEY, saved_list)
    return saved_list


class TaskDoneTool(Tool):
    """Checkpoint (merge + persist + truncate) or read all saved tasks for final response."""

    async def execute(self, **kwargs: Any) -> Response:
        args = dict(self.args or {})
        for k, v in kwargs.items():
            if v is not None:
                args[k] = v

        method = (getattr(self, "method", None) or "").strip().lower()

        if method == "read":
            return await self._execute_read(args)
        if method == "checkpoint":
            return await self._execute_checkpoint(args)

        return Response(
            message=(
                "task_done supports only **task_done:checkpoint** or **task_done:read**. "
                "Use **task_done:checkpoint** with `task_index`, `plans`, and optional `progress` / `learnings` "
                "to merge extracts, persist state, and truncate topic history. "
                "Use **task_done:read** once at the end to load all saved tasks."
            ),
            break_loop=False,
        )

    def _write_state_from_args(self, memory: TaskDataMemory, args: dict, *, task_index: Optional[int]) -> None:
        plans = args.get("plans")
        progress = args.get("progress")
        ld, lti = _learnings_from_args(args, default_task_index=task_index)
        if plans is None and progress is None and ld is None:
            return
        memory.write_execution_state(
            plans_markdown=str(plans).strip() if plans is not None else None,
            progress_note=str(progress).strip() if progress is not None else None,
            current_task_index=task_index,
            learnings_delta=ld,
            learnings_task_index=lti,
        )

    async def _execute_checkpoint(self, args: dict) -> Response:
        plans = args.get("plans")
        if plans is None or not str(plans).strip():
            return Response(
                message="task_done:checkpoint requires non-empty 'plans' (markdown, same as <plans> in your reply).",
                break_loop=False,
            )
        try:
            task_index = int(args.get("task_index"))
        except (TypeError, ValueError):
            return Response(
                message="task_done:checkpoint requires integer 'task_index' (fragments for this task are merged).",
                break_loop=False,
            )
        memory = TaskDataMemory(self.agent)
        merged_path, merged_content = await memory.merge_task(task_index)
        merge_note = ""
        if merged_path and merged_content:
            merge_note = f"Task {task_index} extracts were merged and saved.\n**Saved data summary:**\n{_saved_summary_line(task_index, merged_content)}\n\n"
            _append_saved_task(self.agent, task_index)
            saved_list = list(self.agent.get_data(SAVED_TASK_LIST_KEY) or [])
            list_hint = f" Checkpoint-merged task indices: {saved_list}." if saved_list else ""
            merge_note += list_hint + "\n\n"
        else:
            merge_note = f"No extract fragments for task {task_index} (merge skipped).\n\n"

        self._write_state_from_args(memory, args, task_index=task_index)
        self.agent.truncate_current_topic_messages()
        _reset_task_done_turn_counter(self.agent)

        return Response(
            message=(
                f"[Checkpoint]\n\n{merge_note}"
                "Execution state (plans / progress / experience) was persisted. "
                "Current conversation topic history was truncated; see **Persisted execution state** in the next screen inject. "
                "Continue work; call **task_done:checkpoint** again **only** when the **Mandatory (task_done reminder)** appears "
                "(assistant-turn threshold in Settings), not after every subtask. Finish with **task_done:read** when you need all saved data."
            ),
            break_loop=False,
        )

    async def _execute_read(self, args: dict) -> Response:
        memory = TaskDataMemory(self.agent)
        # Read learnings before load_all_tasks cleanup removes execution_checkpoint/.
        learnings = memory.read_learnings_for_summary()
        aggregated, success = await memory.load_all_tasks()
        self.agent.set_data(SAVED_TASK_LIST_KEY, [])
        _reset_task_done_turn_counter(self.agent)
        if not success:
            if memory.has_pending_task_storage():
                return Response(
                    message=(
                        "Saved task files exist (**task_done** merges and/or **extract_data** fragments) but **nothing usable was returned** "
                        "(for example files are empty or unreadable). "
                        "Try **task_done:checkpoint** with the correct `task_index`, then call **task_done:read** again. "
                        "If you have not extracted yet, use **extract_data:extract** during work; use **task_done:checkpoint** when the N-turn reminder fires."
                    ),
                    break_loop=False,
                )
            return Response(
                message="No saved task results found. Use **extract_data:extract** during work; call **task_done:checkpoint** when the N-turn reminder fires; at the end use **task_done:read** to load all tasks.",
                break_loop=False,
            )
        tail = ""
        if learnings and learnings.strip():
            tail = (
                "\n\n---\n\n## Session experience summary\n\n"
                f"{learnings}\n\n"
                "(Use the above when writing your final response to the user: summarize reusable tips and fixes; "
                "do not echo secrets.)\n"
            )
        return Response(
            message=f"[All Task Results Loaded]\n\n{aggregated}{tail}\n\n[Directory cleaned] You can now use the data above.",
            break_loop=False,
        )
