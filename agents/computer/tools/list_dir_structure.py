"""
List directory structure (including subdirectories) for the Computer Agent.
Use at the start of a subtask that involves a folder to get the full tree without exploring folder by folder.
"""
from __future__ import annotations

import os
from typing import Any

from python.helpers.tool import Tool, Response

MAX_DEPTH_DEFAULT = 20
MAX_ENTRIES_DEFAULT = 1000


def _norm_rel(path: str) -> str:
    """Normalize path to use forward slashes (find-style)."""
    return path.replace("\\", "/")


def _format_tree(root: str, max_depth: int, max_entries: int) -> str:
    """Walk root and return one full relative path per line (find-style). Stops at max_depth and max_entries."""
    root = os.path.normpath(os.path.abspath(root))
    lines: list[str] = []
    count = 0

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            rel_dir = ""
        depth = rel_dir.count(os.sep) + (1 if rel_dir else 0)
        if depth > max_depth:
            dirnames.clear()
            continue
        prefix = (rel_dir + os.sep) if rel_dir else ""
        if rel_dir == "":
            lines.append(".")
            count += 1
        if count >= max_entries:
            lines.append("... (truncated by max_entries)")
            return "\n".join(lines)
        for d in sorted(dirnames):
            if count >= max_entries:
                lines.append("... (truncated by max_entries)")
                return "\n".join(lines)
            lines.append(_norm_rel(prefix + d + "/"))
            count += 1
        for f in sorted(filenames):
            if count >= max_entries:
                lines.append("... (truncated by max_entries)")
                return "\n".join(lines)
            lines.append(_norm_rel(prefix + f))
            count += 1
    return "\n".join(lines) if lines else "(empty)"


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
            max_depth = int(args.get("max_depth") or MAX_DEPTH_DEFAULT)
        except (TypeError, ValueError):
            max_depth = MAX_DEPTH_DEFAULT
        try:
            max_entries = int(args.get("max_entries") or MAX_ENTRIES_DEFAULT)
        except (TypeError, ValueError):
            max_entries = MAX_ENTRIES_DEFAULT

        tree = _format_tree(path_abs, max_depth=max_depth, max_entries=max_entries)
        return Response(
            message=f"**Directory structure** (path={path_abs}, max_depth={max_depth}, max_entries={max_entries}):\n\n```\n{tree}\n```\n\nUse this to plan navigation or file selection without opening each subfolder.",
            break_loop=False,
        )
