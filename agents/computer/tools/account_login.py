"""
Fill username/password from local credential profiles. Secrets are never passed in tool_args (model context).

Methods: fill_at_indices, fill_at_coordinates.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from python.helpers.tool import Tool, Response

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPUTER_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)

import credential_store  # noqa: E402
from actions import ActionTools  # noqa: E402
from tools import vision_common as vc  # noqa: E402

_FILL_MODES = frozenset({"username", "password"})
_FORBIDDEN_SECRET_KEYS = frozenset(
    {"password", "username", "user_name", "passwd", "secret", "user_password"}
)


def _param_provided(args: Dict[str, Any], key: str) -> bool:
    return key in args and args[key] is not None


def _redacted_args_for_log(args: Dict[str, Any], method: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "goal": args.get("goal"),
        "system": args.get("system"),
        "user_label": args.get("user_label"),
        "fill": args.get("fill"),
    }
    m = (method or "").strip()
    if m == "fill_at_indices":
        for k in ("username_index", "password_index"):
            if k in args:
                out[k] = args[k]
    elif m == "fill_at_coordinates":
        for k in ("username_coord", "password_coord"):
            if k in args:
                out[k] = args[k]
    return out


def _reject_secret_literals(args: Dict[str, Any]) -> Optional[Response]:
    for k in _FORBIDDEN_SECRET_KEYS:
        v = args.get(k)
        if isinstance(v, str) and v.strip():
            return Response(
                message=(
                    f"Do not pass '{k}' in tool_args (would appear in chat history). "
                    "Use **system** and optional **user_label** only; store secrets in computer_credentials.json."
                ),
                break_loop=False,
            )
    return None


def _parse_coord_value(raw: Any) -> Tuple[Optional[Tuple[float, float]], Optional[Response]]:
    """Parse normalized [x, y] (same scale as other computer coordinate tools)."""
    if raw is None:
        return None, Response(message="Missing coordinate value.", break_loop=False)
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("["):
            try:
                raw = json.loads(s)
            except (json.JSONDecodeError, TypeError):
                return None, Response(message="coord string must be a JSON array [x, y].", break_loop=False)
    if isinstance(raw, dict):
        try:
            x, y = float(raw["x"]), float(raw["y"])
            return (x, y), None
        except (KeyError, TypeError, ValueError):
            return None, Response(message="coord object must have numeric x and y.", break_loop=False)
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        try:
            return (float(raw[0]), float(raw[1])), None
        except (TypeError, ValueError):
            pass
    return None, Response(
        message="coord must be [x, y] with two numeric normalized coordinates.",
        break_loop=False,
    )


def _user_label_from_args(args: Dict[str, Any]) -> Optional[str]:
    if "user_label" not in args:
        return None
    v = args["user_label"]
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _resolve_credentials(args: Dict[str, Any]) -> Tuple[Optional[Dict[str, str]], Optional[Response]]:
    system = str(args.get("system", "") or "").strip()
    ul = _user_label_from_args(args)
    row, err = credential_store.resolve_account(system, ul)
    if err:
        return None, Response(message=err, break_loop=False)
    assert row is not None
    return row, None


def _parse_fill_optional(args: Dict[str, Any]) -> Tuple[Optional[str], Optional[Response]]:
    raw = args.get("fill")
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        return None, None
    s = str(raw).strip().lower()
    if s in ("user_name", "user", "username_only"):
        s = "username"
    if s in ("pass", "pwd", "password_only"):
        s = "password"
    if s not in _FILL_MODES:
        return None, Response(
            message="fill must be omitted, or exactly 'username' or 'password'.",
            break_loop=False,
        )
    return s, None


def _fill_one_field(
    actions: ActionTools,
    pos: List[int],
    value: str,
    *,
    kind: str,
) -> None:
    actions._click(pos)
    time.sleep(0.08)
    log_label = "[username]" if kind == "username" else "[password]"
    actions._type_text(value, clear_field_first=True, log_text=log_label)


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
) -> Response:
    actions = ActionTools(
        dry_run=False,
        paste_key=["command", "v"] if platform.system() == "Darwin" else ["ctrl", "v"],
    )
    parts: List[str] = []

    for kind, pos in steps:
        if kind == "username":
            _fill_one_field(actions, pos, profile.get("username") or "", kind="username")
            parts.append(
                "Username field: Type action executed (saved username). "
                "Please verify result on next screenshot."
            )
        elif kind == "password":
            _fill_one_field(actions, pos, profile.get("password") or "", kind="password")
            parts.append(
                "Password field: Type action executed (saved password). "
                "Please verify result on next screenshot."
            )

    msg = f"Goal: {goal}. " + " ".join(parts)
    return Response(message=msg, break_loop=False)


def _resolve_index_step(
    index_map: Dict[int, Dict[str, float]], args: Dict[str, Any], key: str, label: str
) -> Tuple[Optional[List[int]], Optional[Response]]:
    if not _param_provided(args, key):
        return None, Response(message=f"{key} required ({label}).", break_loop=False)
    try:
        return vc.resolve_index(index_map, int(args[key])), None
    except (TypeError, ValueError) as e:
        return None, Response(message=str(e), break_loop=False)


def _build_index_steps(
    args: Dict[str, Any],
    index_map: Dict[int, Dict[str, float]],
    fill_restrict: Optional[str],
) -> Tuple[List[Tuple[str, List[int]]], Optional[Response]]:
    has_u = _param_provided(args, "username_index")
    has_p = _param_provided(args, "password_index")

    if fill_restrict == "username":
        pos, err = _resolve_index_step(index_map, args, "username_index", "fill is username")
        if err:
            return [], err
        assert pos is not None
        return [("username", pos)], None

    if fill_restrict == "password":
        pos, err = _resolve_index_step(index_map, args, "password_index", "fill is password")
        if err:
            return [], err
        assert pos is not None
        return [("password", pos)], None

    if not has_u and not has_p:
        return [], Response(
            message="Provide at least one of username_index or password_index.",
            break_loop=False,
        )

    steps: List[Tuple[str, List[int]]] = []
    if has_u:
        pos, err = _resolve_index_step(index_map, args, "username_index", "username fill")
        if err:
            return [], err
        assert pos is not None
        steps.append(("username", pos))
    if has_p:
        pos, err = _resolve_index_step(index_map, args, "password_index", "password fill")
        if err:
            return [], err
        assert pos is not None
        steps.append(("password", pos))
    return steps, None


def _coord_to_screen_pos(
    tool: "AccountLoginTool", args: Dict[str, Any], xy: Tuple[float, float]
) -> Tuple[Optional[List[int]], Optional[Response]]:
    return vc.get_coord_pos(tool.agent, {**args, "x": xy[0], "y": xy[1]})


def _build_coord_steps(
    tool: "AccountLoginTool",
    args: Dict[str, Any],
    fill_restrict: Optional[str],
) -> Tuple[List[Tuple[str, List[int]]], Optional[Response]]:
    has_u = _param_provided(args, "username_coord")
    has_p = _param_provided(args, "password_coord")

    def one(kind: str, key: str) -> Tuple[Optional[List[int]], Optional[Response]]:
        xy, cerr = _parse_coord_value(args[key])
        if cerr is not None:
            return None, cerr
        assert xy is not None
        return _coord_to_screen_pos(tool, args, xy)

    if fill_restrict == "username":
        if not has_u:
            return [], Response(
                message="username_coord required when fill is username.",
                break_loop=False,
            )
        pos, err = one("username", "username_coord")
        if err:
            return [], err
        assert pos is not None
        return [("username", pos)], None

    if fill_restrict == "password":
        if not has_p:
            return [], Response(
                message="password_coord required when fill is password.",
                break_loop=False,
            )
        pos, err = one("password", "password_coord")
        if err:
            return [], err
        assert pos is not None
        return [("password", pos)], None

    if not has_u and not has_p:
        return [], Response(
            message="Provide at least one of username_coord or password_coord (normalized [x, y]).",
            break_loop=False,
        )

    steps: List[Tuple[str, List[int]]] = []
    if has_u:
        pos, err = one("username", "username_coord")
        if err:
            return [], err
        assert pos is not None
        steps.append(("username", pos))
    if has_p:
        pos, err = one("password", "password_coord")
        if err:
            return [], err
        assert pos is not None
        steps.append(("password", pos))
    return steps, None


def _do_fill_at_indices(tool: "AccountLoginTool", args: Dict[str, Any], goal: str) -> Response:
    err = _reject_secret_literals(args)
    if err:
        return err
    fill_restrict, ferr = _parse_fill_optional(args)
    if ferr:
        return ferr
    profile, perr = _resolve_credentials(args)
    if perr:
        return perr

    index_map, im_err = vc.get_index_map(tool.agent)
    if im_err is not None:
        return im_err

    steps, serr = _build_index_steps(args, index_map, fill_restrict)
    if serr:
        return serr
    pre = _preflight_profile(profile, steps)
    if pre:
        return pre
    return _run_fill_steps(goal, steps, profile)


def _do_fill_at_coordinates(tool: "AccountLoginTool", args: Dict[str, Any], goal: str) -> Response:
    err = _reject_secret_literals(args)
    if err:
        return err
    fill_restrict, ferr = _parse_fill_optional(args)
    if ferr:
        return ferr
    profile, perr = _resolve_credentials(args)
    if perr:
        return perr

    steps, serr = _build_coord_steps(tool, args, fill_restrict)
    if serr:
        return serr
    pre = _preflight_profile(profile, steps)
    if pre:
        return pre
    return _run_fill_steps(goal, steps, profile)


class AccountLoginTool(Tool):
    """Fill login fields from local credentials via system + optional user_label; never pass username/password in tool_args."""

    async def before_execution(self, **kwargs: Any) -> None:
        orig = self.args
        try:
            self.args = _redacted_args_for_log(dict(orig or {}), (self.method or "").strip())
            await super().before_execution(**kwargs)
        finally:
            self.args = orig

    async def after_execution(self, response: Response, **kwargs: Any) -> None:
        red = _redacted_args_for_log(dict(self.args or {}), (self.method or "").strip())
        vc.vision_after_execution(
            self.agent,
            self.name,
            (self.method or "").strip(),
            red,
            (response.message or "").strip(),
        )
        await super().after_execution(response, **kwargs)

    def get_log_object(self):
        red = _redacted_args_for_log(dict(self.args or {}), (self.method or "").strip())
        if self.method:
            heading = f"icon://construction {self.agent.agent_name}: Using tool '{self.name}:{self.method}'"
        else:
            heading = f"icon://construction {self.agent.agent_name}: Using tool '{self.name}'"
        return self.agent.context.log.log(
            type="tool",
            heading=heading,
            content="",
            kvps=red,
            _tool_name=self.name,
        )

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
            return _do_fill_at_indices(self, args, goal)
        if method == "fill_at_coordinates":
            return _do_fill_at_coordinates(self, args, goal)
        return Response(
            message="Use method: fill_at_indices or fill_at_coordinates.",
            break_loop=False,
        )
