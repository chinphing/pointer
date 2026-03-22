"""
Computer Agent file storage under the user workdir (Settings → workdir_path, default usr/workdir).

Layout:
  {workdir}/computer/snapshots/<context_id>/   — screen inject debug PNGs (*_raw.png, *_raw_layouts.png, *_annotated.png, …)
  {workdir}/computer/extract_data/<context_id>/ — extract_data fragments
  {workdir}/computer/task_done/<context_id>/   — merged task outputs
  {workdir}/computer/execution_checkpoint/<context_id>/ — persisted plans, progress, session learnings (task_done checkpoint)

Previously these lived under agents/computer/… in the repo; they are now per-deployment data next to other workdir files.
"""
from __future__ import annotations

import os


def get_workdir_path() -> str:
    """Absolute path to the configured Agent Zero work directory."""
    try:
        from python.helpers import settings

        p = (settings.get_settings().get("workdir_path") or "").strip()
        if p:
            return os.path.abspath(os.path.expanduser(p))
    except Exception:
        pass
    from python.helpers import files

    return os.path.abspath(os.path.expanduser(files.get_abs_path_dockerized("usr", "workdir")))


def computer_snapshots_dir() -> str:
    return os.path.join(get_workdir_path(), "computer", "snapshots")


def computer_extract_data_dir() -> str:
    return os.path.join(get_workdir_path(), "computer", "extract_data")


def computer_task_done_dir() -> str:
    return os.path.join(get_workdir_path(), "computer", "task_done")


def computer_execution_checkpoint_dir() -> str:
    return os.path.join(get_workdir_path(), "computer", "execution_checkpoint")
