"""
Fill username/password from local credential profiles. Secrets are never passed in tool_args (model context).

Methods: fill_at_indices, fill_at_coordinates.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from python.helpers.tool import Tool, Response

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)

import credential_store  # noqa: E402
from mouse_move import MouseHelper  # noqa: E402
from actions import RawAction  # noqa: E402
from tools import vision_common as vc  # noqa: E402


def _get_human_like_default() -> bool:
    """Get default human_like setting from config."""
    try:
        from python.helpers import settings as settings_mod
        return bool(settings_mod.get_settings().get("computer_human_like", False))
    except Exception:
        return False


def _get_human_like(args: Dict[str, Any]) -> bool:
    """Get human_like value from args or config default."""
    if "human_like" in args:
        return bool(args["human_like"])
    return _get_human_like_default()


def _reject_secret_literals(args: Dict[str, Any]) -> Optional[Response]:
    """Prevent accidental secret exposure via tool_args."""
    for key in ("username", "password"):
        if args.get(key):
            return Response(
                message=f"Do not pass '{key}' in tool_args. Use the credential store.",
                break_loop=False,
            )
    return None


def _parse_fill_optional(args: Dict[str, Any]) -> Tuple[Optional[str], Optional[Response]]:
    """Parse optional fill parameter (username_only / password_only)."""
    fill = args.get("fill")
    if fill is None:
        return None, None
    fill_str = str(fill).strip().lower()
    if fill_str in ("username_only", "password_only"):
        return fill_str, None
    return None, Response(
        message="Invalid 'fill' value. Use 'username_only' or 'password_only'.",
        break_loop=False,
    )


def _resolve_credentials(args: Dict[str, Any]) -> Tuple[Optional[Dict[str, str]], Optional[Response]]:
    """Load credentials from the store by profile name."""
    profile_name = str(args.get("profile_name") or "").strip()
    if not profile_name:
        return None, Response(message="Missing 'profile_name' in tool_args.", break_loop=False)
    try:
        profile = credential_store.load_profile(profile_name)
    except Exception as e:
        return None, Response(message=f"Failed to load profile '{profile_name}': {e}", break_loop=False)
    if not profile:
        return None, Response(message=f"Profile '{profile_name}' not found.", break_loop=False)
    return profile, None


def _build_index_steps(
    args: Dict[str, Any],
    index_map: Dict[int, Dict[str, float]],
    fill_restrict: Optional[str],
) -> Tuple[List[Tuple[str, List[int]]], Optional[Response]]:
    """Build list of (kind, position) steps for index-based fill."""
    steps: List[Tuple[str, List[int]]] = []

    def _resolve_index(idx: Any, label: str) -> Tuple[Optional[List[int]], Optional[Response]]:
        if idx is None:
            return None, Response(message=f"Missing '{label}' in tool_args.", break_loop=False)
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            return None, Response(message=f"'{label}' must be an integer.", break_loop=False)
        if idx not in index_map:
            return None, Response(message=f"Index {idx} not found in index_map.", break_loop=False)
        return vc.resolve_index(index_map, idx), None

    if fill_restrict != "password_only":
        pos, err = _resolve_index(args.get("username_index"), "username_index")
        if err:
            return [], err
        if pos:
            steps.append(("username", pos))

    if fill_restrict != "username_only":
        pos, err = _resolve_index(args.get("password_index"), "password_index")
        if err:
            return [], err
        if pos:
            steps.append(("password", pos))

    return steps, None


def _build_coord_steps(
    tool: "AccountLoginTool",
    args: Dict[str, Any],
    fill_restrict: Optional[str],
) -> Tuple[List[Tuple[str, List[int]]], Optional[Response]]:
    """Build list of (kind, position) steps for coordinate-based fill."""
    steps: List[Tuple[str, List[int]]] = []

    def _resolve_coords(coords: Any, label: str) -> Tuple[Optional[List[int]], Optional[Response]]:
        if coords is None:
            return None, Response(message=f"Missing '{label}' in tool_args.", break_loop=False)
        if isinstance(coords, str):
            try:
                coords = json.loads(coords)
            except json.JSONDecodeError as e:
                return None, Response(message=f"Invalid JSON in '{label}': {e}", break_loop=False)
        if not isinstance(coords, (list, tuple)) or len(coords) != 2:
            return None, Response(message=f"'{label}' must be [x, y].", break_loop=False)
        try:
            x, y = int(coords[0]), int(coords[1])
        except (TypeError, ValueError):
            return None, Response(message=f"'{label}' coordinates must be integers.", break_loop=False)
        return [x, y], None

    if fill_restrict != "password_only":
        pos, err = _resolve_coords(args.get("username_coords"), "username_coords")
        if err:
            return [], err
        if pos:
            steps.append(("username", pos))

    if fill_restrict != "username_only":
        pos, err = _resolve_coords(args.get("password_coords"), "password_coords")
        if err:
            return [], err
        if pos:
            steps.append(("password", pos))

    return steps, None


def _fill_one_field(
    pos: List[int],
    value: str,
    *,
    kind: str,
    human_like: bool = False,
) -> None:
    """Fill a single field at the given position."""
    # Move to position and click
    MouseHelper.click_at(pos, human_like=human_like)
    time.sleep(0.08)
    
    # Type text
    actions = RawAction(dry_run=False)
    actions._type_text(value, clear_field_first=True)


def _preflight_profile(
    profile: Dict[str, str], steps: List[Tuple[str, List[int]]]
) -> Optional[Response]:
    for kind, _ in steps:
        if kind == "username":
            if not (profile.get("username") or "").strip():
                return Response(
                    message="Profile has empty username; cannot fill username.",
                    break_loop=False,
                )
        elif kind == "password":
            if not (profile.get("password") or "").strip():
                return Response(
                    message="Profile has empty password; cannot fill password.",
                    break_loop=False,
                )
    return None


def _run_fill_steps(
    goal: str,
    steps: List[Tuple[str, List[int]]],
    profile: Dict[str, str],
    human_like: bool = False,
) -> Response:
    parts: List[str] = []

    for kind, pos in steps:
        if kind == "username":
            _fill_one_field(pos, profile.get("username") or "", kind="username", human_like=human_like)
            parts.append(
                "Username field: Type action executed (saved username). "
                "Please verify result on next screenshot."
            )
        elif kind == "password":
            _fill_one_field(pos, profile.get("password") or "", kind="password", human_like=human_like)
            parts.append(
                "Password field: Type action executed (saved password). "
                "Please verify result on next screenshot."
            )

    return Response(message=f"Goal: {goal}. {' '.join(parts)}", break_loop=False)


class AccountLoginTool(Tool):
    """Fill username/password from local credential profiles."""

    async def after_execution(self, response: Response, **kwargs: Any) -> None:
        vc.vision_after_execution(
            self.agent,
            self.name,
            (self.method or "").strip(),
            self.args or {},
            (response.message or "").strip(),
        )
        await super().after_execution(response, **kwargs)

    async def execute(self, **kwargs: Any) -> Response:
        args = dict(self.args or {})
        for k, v in kwargs.items():
            if v is not None:
                args[k] = v
        goal = str(args.get("goal", "")).strip()
        if not goal:
            return Response(message="Missing required 'goal' in tool_args.", break_loop=False)
        method = (self.method or "").strip()
        if method == "fill_at_indices":
            return self._do_fill_at_indices(args, goal)
        if method == "fill_at_coordinates":
            return self._do_fill_at_coordinates(args, goal)
        return Response(
            message="Use method 'fill_at_indices' or 'fill_at_coordinates'.",
            break_loop=False,
        )

    def _do_fill_at_indices(self, args: Dict[str, Any], goal: str) -> Response:
        err = _reject_secret_literals(args)
        if err:
            return err
        fill_restrict, ferr = _parse_fill_optional(args)
        if ferr:
            return ferr
        profile, perr = _resolve_credentials(args)
        if perr:
            return perr

        index_map, err = vc.get_index_map(self.agent)
        if err is not None:
            return err

        steps, serr = _build_index_steps(args, index_map, fill_restrict)
        if serr:
            return serr
        pre = _preflight_profile(profile, steps)
        if pre:
            return pre
        human_like = _get_human_like(args)
        return _run_fill_steps(goal, steps, profile, human_like=human_like)

    def _do_fill_at_coordinates(self, args: Dict[str, Any], goal: str) -> Response:
        err = _reject_secret_literals(args)
        if err:
            return err
        fill_restrict, ferr = _parse_fill_optional(args)
        if ferr:
            return ferr
        profile, perr = _resolve_credentials(args)
        if perr:
            return perr

        steps, serr = _build_coord_steps(self, args, fill_restrict)
        if serr:
            return serr
        pre = _preflight_profile(profile, steps)
        if pre:
            return pre
        human_like = _get_human_like(args)
        return _run_fill_steps(goal, steps, profile, human_like=human_like)
