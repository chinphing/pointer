"""
Task data memory system for Computer Agent.
Unified handling of: fragment save, fragment merge per task, load by task IDs, load all and cleanup,
execution checkpoint (plans / progress / session learnings).
Used by extract_data (memory) tool and task_done tool.
"""
from __future__ import annotations

import glob
import os
import re
import shutil
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent import Agent

import storage_paths

# Agent data key: set to False to skip cleanup when load_all_tasks runs (default True).
LOAD_ALL_CLEANUP_KEY = "computer_load_all_cleanup"

EXECUTION_STATE_FILENAME = "execution_state.md"
LEARNINGS_MAX_CHARS = 8000
READ_SUMMARY_LEARNINGS_MAX = 4000

# Turns since any task_done-family tool succeeded; incremented each computer screen inject (see extension).
COMPUTER_TURNS_SINCE_TASK_DONE_KEY = "computer_turns_since_task_done"


def _extract_dir(agent: "Agent") -> str:
    base = storage_paths.computer_extract_data_dir()
    context_id = getattr(agent.context, "id", None) or "default"
    return os.path.join(base, context_id)


def _task_done_dir(agent: "Agent") -> str:
    base = storage_paths.computer_task_done_dir()
    context_id = getattr(agent.context, "id", None) or "default"
    return os.path.join(base, context_id)


def _execution_checkpoint_dir(agent: "Agent") -> str:
    base = storage_paths.computer_execution_checkpoint_dir()
    context_id = getattr(agent.context, "id", None) or "default"
    return os.path.join(base, context_id)


def _execution_state_path(agent: "Agent") -> str:
    return os.path.join(_execution_checkpoint_dir(agent), EXECUTION_STATE_FILENAME)


def _parse_execution_state_sections(raw: str) -> dict[str, str]:
    """Split execution_state.md into Plans / Progress / Experience and fixes."""
    sections: dict[str, str] = {"Plans": "", "Progress": "", "Experience and fixes": ""}
    current: str | None = None
    buf: list[str] = []
    for line in raw.splitlines():
        if line.strip() == "## Plans":
            if current:
                sections[current] = "\n".join(buf).strip()
            current = "Plans"
            buf = []
            continue
        if line.strip() == "## Progress":
            if current:
                sections[current] = "\n".join(buf).strip()
            current = "Progress"
            buf = []
            continue
        if line.strip() == "## Experience and fixes":
            if current:
                sections[current] = "\n".join(buf).strip()
            current = "Experience and fixes"
            buf = []
            continue
        buf.append(line)
    if current:
        sections[current] = "\n".join(buf).strip()
    return sections


def _format_execution_state(sections: dict[str, str]) -> str:
    p = sections.get("Plans", "").strip()
    g = sections.get("Progress", "").strip()
    e = sections.get("Experience and fixes", "").strip()
    return (
        "## Plans\n\n"
        f"{p}\n\n"
        "## Progress\n\n"
        f"{g}\n\n"
        "## Experience and fixes\n\n"
        f"{e}\n"
    )


def _trim_learnings(text: str, max_chars: int = LEARNINGS_MAX_CHARS) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return "…(truncated)\n" + t[-max_chars:]


class TaskDataMemory:
    """
    Memory system for task-related extracted data.
    - save_fragment: append one fragment (one screenshot's extraction) for a task.
    - merge_task: merge all fragments for one task via LLM and save to task_done.
    - load_tasks: load saved content for given task IDs. Merged task_done files are read as-is; unmerged fragments are returned raw (no LLM merge).
    - load_all_tasks: load all saved tasks and cleanup; use once at the end before response.
    - write_execution_state / read_execution_state: persisted plans, progress, session learnings.
    """

    def __init__(self, agent: "Agent"):
        self.agent = agent

    def read_execution_state(self) -> str | None:
        """Full markdown for prompt inject; None if missing."""
        path = _execution_state_path(self.agent)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                s = f.read().strip()
            return s if s else None
        except OSError:
            return None

    def read_learnings_for_summary(self, max_chars: int = READ_SUMMARY_LEARNINGS_MAX) -> str | None:
        """Experience section only, for task_done:read tail."""
        raw = self.read_execution_state()
        if not raw:
            return None
        sec = _parse_execution_state_sections(raw).get("Experience and fixes", "").strip()
        if not sec:
            return None
        if len(sec) > max_chars:
            return sec[-max_chars:]
        return sec

    def write_execution_state(
        self,
        *,
        plans_markdown: str | None = None,
        progress_note: str | None = None,
        current_task_index: int | None = None,
        learnings_delta: str | None = None,
        learnings_task_index: int | None = None,
    ) -> None:
        """
        Read-modify-write execution_state.md. None means leave section unchanged (except learnings append).
        Appends to Experience and fixes when learnings_delta is non-empty.
        """
        path = _execution_state_path(self.agent)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    sections = _parse_execution_state_sections(f.read())
            except OSError:
                sections = {"Plans": "", "Progress": "", "Experience and fixes": ""}
        else:
            sections = {"Plans": "", "Progress": "", "Experience and fixes": ""}

        if plans_markdown is not None:
            sections["Plans"] = str(plans_markdown).strip()
        if progress_note is not None:
            extra = ""
            if current_task_index is not None:
                extra = f"(current task_index: {current_task_index})\n\n"
            sections["Progress"] = (extra + str(progress_note)).strip()
        elif current_task_index is not None and not (sections.get("Progress") or "").strip():
            sections["Progress"] = f"(current task_index: {current_task_index})"

        delta = (learnings_delta or "").strip()
        if delta:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
            prefix = f"[task {learnings_task_index}] " if learnings_task_index is not None else ""
            block = f"- {prefix}{ts} — {delta}\n"
            exp = (sections.get("Experience and fixes") or "").strip()
            if exp:
                exp = exp + "\n" + block
            else:
                exp = block.strip()
            sections["Experience and fixes"] = _trim_learnings(exp)

        out = _format_execution_state(sections)
        with open(path, "w", encoding="utf-8") as f:
            f.write(out)

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
        Returns (None, None) only if there are no fragments or the fragment file is empty.
        If the utility model fails or returns empty text, raw fragments are still written to task_done
        (with an HTML comment banner) so reads never silently drop data.
        """

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
        merged: str | None = None
        try:
            response, _ = await self.agent.call_utility_model(
                system=system,
                message=user_content,
                background=True,
            )
            if response and str(response).strip():
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
        except Exception:
            merged = None

        if not merged:
            # Utility merge failed or returned empty: still persist fragments so
            # checkpoint does not leave the model with no merged file for that task.
            merged = (
                "<!-- Saved without LLM merge (utility model failed or empty). "
                "Content below is raw extract_data fragments. -->\n\n"
                + raw_content.strip()
            )

        out_dir = _task_done_dir(self.agent)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"task_{task_index}.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged)
        try:
            os.remove(extracts_path)
        except OSError:
            pass
        return out_path, merged

    def _raw_fragments_for_task(self, task_index: int) -> str | None:
        """Read extract_data fragment file for task_index; None if missing or empty."""
        extracts_path = os.path.join(_extract_dir(self.agent), f"task_{task_index}_extracts.md")
        if not os.path.isfile(extracts_path):
            return None
        try:
            with open(extracts_path, "r", encoding="utf-8") as f:
                raw = f.read().strip()
        except OSError:
            return None
        return raw or None

    async def load_tasks(self, task_indices: list[int]) -> tuple[str, list[int]]:
        """
        Load saved content for the given task IDs.
        Prefer merged file (task_done dir). If only unmerged fragments exist, return them raw with a short
        notice — no LLM merge (avoids slow utility calls on task_done:read).
        Returns (aggregated_content, list_of_missing_ids).
        """
        parts: list[str] = []
        missing: list[int] = []
        out_dir = _task_done_dir(self.agent)
        for ti in task_indices:
            merged_path = os.path.join(out_dir, f"task_{ti}.md")
            content: str | None = None
            if os.path.isfile(merged_path):
                try:
                    with open(merged_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except OSError:
                    content = None
            if content is None:
                raw = self._raw_fragments_for_task(ti)
                if raw is not None:
                    content = (
                        f"**[Task {ti} — unmerged extract_data fragments]**\n\n"
                        "The following is the raw fragment file (no LLM merge on read). "
                        "To produce a merged file under task_done before finishing, call **task_done:checkpoint** with this `task_index`. "
                        "A final **task_done:read** removes merged files and these fragment files from disk.\n\n"
                        "---\n\n"
                        f"{raw}"
                    )
            if content is None:
                missing.append(ti)
                continue
            parts.append(f"=== Task {ti} ===\n{content}")
        return "\n\n".join(parts), missing

    def has_pending_task_storage(self) -> bool:
        """True if merged task files and/or unmerged extract fragments exist for this context."""
        out_dir = _task_done_dir(self.agent)
        extract_dir = _extract_dir(self.agent)
        if glob.glob(os.path.join(out_dir, "task_*.md")):
            return True
        if glob.glob(os.path.join(extract_dir, "task_*_extracts.md")):
            return True
        return False

    async def load_all_tasks(self, cleanup: bool | None = None) -> tuple[str, bool]:
        """
        Load all saved tasks via load_tasks. Optionally cleanup task_done, all task_*_extracts.md
        under extract_data for this context, and execution_checkpoint.
        cleanup: if None, use agent data key LOAD_ALL_CLEANUP_KEY (default True).
        Returns (aggregated_content, success). success=False if no task data found.
        """
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
                ec_dir = _execution_checkpoint_dir(self.agent)
                if os.path.isdir(ec_dir):
                    try:
                        shutil.rmtree(ec_dir)
                    except OSError:
                        pass
            except Exception:
                pass
        return aggregated, True
