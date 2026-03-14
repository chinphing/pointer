"""
Task data memory system for Computer Agent.
Unified handling of: fragment save, fragment merge per task, load by task IDs, load all and cleanup.
Used by extract_data (memory) tool and task_done tool.
"""
from __future__ import annotations

import glob
import os
from typing import TYPE_CHECKING

from python.helpers import files

if TYPE_CHECKING:
    from agent import Agent

# Agent data key: set to False to skip cleanup when load_all_tasks runs (default True).
LOAD_ALL_CLEANUP_KEY = "computer_load_all_cleanup"


def _extract_dir(agent: "Agent") -> str:
    base = files.get_abs_path("agents", "computer", "extract_data")
    context_id = getattr(agent.context, "id", None) or "default"
    return os.path.join(base, context_id)


def _task_done_dir(agent: "Agent") -> str:
    base = files.get_abs_path("agents", "computer", "task_done")
    context_id = getattr(agent.context, "id", None) or "default"
    return os.path.join(base, context_id)


class TaskDataMemory:
    """
    Memory system for task-related extracted data.
    - save_fragment: append one fragment (one screenshot's extraction) for a task.
    - merge_task: merge all fragments for one task via LLM and save to task_done.
    - load_tasks: load saved content for given task IDs (for use in the middle of the flow).
    - load_all_tasks: load all saved tasks and cleanup; use once at the end before response.
    """

    def __init__(self, agent: "Agent"):
        self.agent = agent

    def save_fragment(self, task_index: int, instruction: str, content: str) -> None:
        """Append one fragment (one screenshot extraction) to the task's temp file."""
        path = os.path.join(_extract_dir(self.agent), f"task_{task_index}_extracts.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        block = f"\n\n---\n\n## Target\n{instruction}\n\n## Content\n{content}\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(block)

    async def merge_task(self, task_index: int) -> tuple[str | None, str | None]:
        """
        Merge all fragments for this task via LLM and save to task_done dir.
        Returns (out_path, merged_content) on success, (None, None) if no fragments or merge failed.
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        extracts_path = os.path.join(_extract_dir(self.agent), f"task_{task_index}_extracts.md")
        if not os.path.isfile(extracts_path):
            return None, None
        with open(extracts_path, "r", encoding="utf-8") as f:
            raw_content = f.read()
        if not raw_content.strip():
            return None, None
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
        except Exception:
            return None, None
        if not response or not str(response).strip():
            return None, None
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
        out_dir = _task_done_dir(self.agent)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"task_{task_index}.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
        return out_path, merged

    async def load_tasks(self, task_indices: list[int]) -> tuple[str, list[int]]:
        """
        Load saved content for the given task IDs.
        Prefer merged file (task_done dir). If not merged but fragments exist, merge them and then return (and persist).
        Returns (aggregated_content, list_of_missing_ids).
        """
        parts: list[str] = []
        missing: list[int] = []
        out_dir = _task_done_dir(self.agent)
        extract_dir = _extract_dir(self.agent)
        for ti in task_indices:
            merged_path = os.path.join(out_dir, f"task_{ti}.md")
            extracts_path = os.path.join(extract_dir, f"task_{ti}_extracts.md")
            content: str | None = None
            if os.path.isfile(merged_path):
                with open(merged_path, "r", encoding="utf-8") as f:
                    content = f.read()
            elif os.path.isfile(extracts_path):
                _, merged = await self.merge_task(ti)
                content = merged
            if content is None:
                missing.append(ti)
                continue
            parts.append(f"=== Task {ti} ===\n{content}")
        return "\n\n".join(parts), missing

    async def load_all_tasks(self, cleanup: bool | None = None) -> tuple[str, bool]:
        """
        Load all saved tasks via load_tasks. Optionally cleanup (extract_data + task_done dirs).
        cleanup: if None, use agent data key LOAD_ALL_CLEANUP_KEY (default True).
        Returns (aggregated_content, success). success=False if no task data found.
        """
        import re
        if cleanup is None:
            v = self.agent.get_data(LOAD_ALL_CLEANUP_KEY)
            cleanup = bool(v) if v is not None else True
        out_dir = _task_done_dir(self.agent)
        extract_dir = _extract_dir(self.agent)
        indices: set[int] = set()
        for path in glob.glob(os.path.join(out_dir, "task_*.md")):
            m = re.match(r"task_(\d+)\.md$", os.path.basename(path))
            if m:
                indices.add(int(m.group(1)))
        for path in glob.glob(os.path.join(extract_dir, "task_*_extracts.md")):
            m = re.match(r"task_(\d+)_extracts\.md$", os.path.basename(path))
            if m:
                indices.add(int(m.group(1)))
        if not indices:
            return "", False
        aggregated, _ = await self.load_tasks(sorted(indices))
        if not aggregated.strip():
            return "", False
        if cleanup:
            try:
                for path in glob.glob(os.path.join(out_dir, "task_*.md")):
                    os.remove(path)
                if os.path.isdir(extract_dir):
                    for ef in glob.glob(os.path.join(extract_dir, "task_*_extracts.md")):
                        try:
                            os.remove(ef)
                        except Exception:
                            pass
                    try:
                        os.rmdir(extract_dir)
                    except Exception:
                        pass
                try:
                    os.rmdir(out_dir)
                except Exception:
                    pass
            except Exception:
                pass
        return aggregated, True
