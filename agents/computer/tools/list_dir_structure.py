"""
List directory structure (including subdirectories) for the Computer Agent.
Use at the start of a subtask that involves a folder to get the full tree without exploring folder by folder.
Uses breadth-first traversal: top-level dirs and files first, then next level, so the model sees shallow structure before deep paths.
"""
from __future__ import annotations

import os
from collections import deque
from typing import Any, List, Tuple

from python.helpers.tool import Tool, Response

MAX_ENTRIES_DEFAULT = 100

TRUNCATE_HINT = (
    "Too many entries; call again for specific deeper directories when you need details (e.g. list_dir_structure with a subdir path)."
)


def _norm_rel(path: str) -> str:
    """Normalize path to use forward slashes (find-style)."""
    return path.replace("\\", "/")


def _format_tree_bfs(root: str, max_entries: int) -> Tuple[str, bool]:
    """
    Breadth-first: list top-level dirs and files first, then each dir's contents level by level.
    Returns (tree_text, truncated).
    """
    root = os.path.normpath(os.path.abspath(root))
    lines: List[str] = []
    count = 0
    truncated = False
    # (dir_abs_path, depth); depth 0 = root's direct children
    queue: deque[Tuple[str, int]] = deque([(root, 0)])

    while queue and count < max_entries:
        dir_abs, depth = queue.popleft()
        rel_dir = os.path.relpath(dir_abs, root)
        if rel_dir == ".":
            rel_dir = ""
        prefix = (rel_dir + os.sep) if rel_dir else ""
        if depth == 0 and not rel_dir:
            lines.append(".")
            count += 1

        try:
            names = os.listdir(dir_abs)
        except OSError:
            continue
        dirs_sorted: List[str] = []
        files_sorted: List[str] = []
        for name in names:
            if name.startswith("."):
                continue
            full = os.path.join(dir_abs, name)
            if os.path.isdir(full):
                dirs_sorted.append(name)
            else:
                files_sorted.append(name)
        dirs_sorted.sort()
        files_sorted.sort()

        for d in dirs_sorted:
            if count >= max_entries:
                truncated = True
                break
            lines.append(_norm_rel(prefix + d + "/"))
            count += 1
            queue.append((os.path.join(dir_abs, d), depth + 1))
        if truncated:
            break
        for f in files_sorted:
            if count >= max_entries:
                truncated = True
                break
            lines.append(_norm_rel(prefix + f))
            count += 1
        if truncated:
            break

    if truncated:
        lines.append("... (truncated by max_entries)")
    return ("\n".join(lines) if lines else "(empty)", truncated)


class ListDirStructureTool(Tool):
    """List full directory and file structure under a path (including subdirectories)."""

    async def execute(self, **kwargs: Any) -> Response:
        args = dict(self.args or {})
        for k, v in kwargs.items():
            if v is not None:
                args[k] = v

        path_arg = args.get("path")
        if not path_arg or not str(path_arg).strip():
            return Response(
                message="list_dir_structure requires 'path' (e.g. ~/Downloads, ~/Documents, or an absolute path).",
                break_loop=False,
            )
        path_str = os.path.expanduser(str(path_arg).strip())
        path_abs = os.path.abspath(path_str)
        if not os.path.isdir(path_abs):
            return Response(
                message=f"Path is not a directory or does not exist: {path_abs}",
                break_loop=False,
            )

        try:
            max_entries = int(args.get("max_entries") or MAX_ENTRIES_DEFAULT)
        except (TypeError, ValueError):
            max_entries = MAX_ENTRIES_DEFAULT

        tree, truncated = _format_tree_bfs(path_abs, max_entries=max_entries)
        hint = ""
        if truncated:
            hint = f"\n\n**Hint:** {TRUNCATE_HINT}"
        return Response(
            message=f"**Directory structure** (path={path_abs}, max_entries={max_entries}):\n\n```\n{tree}\n```\n\nUse this to plan navigation or file selection without opening each subfolder.{hint}",
            break_loop=False,
        )
