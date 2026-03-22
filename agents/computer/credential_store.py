"""
Load login accounts from a local JSON file. Secrets are never read from LLM tool_args.

Schema: {"version": 1, "accounts": [{system, user_label, username, password, system_aliases?, user_aliases?}]}
Legacy {"profiles": {id: {...}}} is migrated in memory on read.

Default file: usr/computer_credentials.json (override via settings computer_credentials_path).
"""
from __future__ import annotations

import json
import os
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

_ACCOUNT_KEYS = frozenset(
    {"system", "user_label", "username", "password", "system_aliases", "user_aliases"}
)
_MAX_ACCOUNTS = 64


def default_credentials_path() -> str:
    from python.helpers import files

    return files.get_abs_path("usr", "computer_credentials.json")


def resolve_credentials_path() -> str:
    """Absolute path to credentials JSON; empty setting uses default."""
    try:
        from python.helpers import settings

        p = (settings.get_settings().get("computer_credentials_path") or "").strip()
        if p:
            return os.path.abspath(os.path.expanduser(p))
    except Exception:
        pass
    return default_credentials_path()


def _norm(s: str) -> str:
    """Normalize for case-insensitive / fuzzy equality (strip + NFKC + casefold)."""
    t = unicodedata.normalize("NFKC", (s or "").strip())
    return t.casefold()


def _parse_alias_list(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return []


def _account_from_dict(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Single account entry with defaults."""
    return {
        "system": str(raw.get("system", "") or ""),
        "user_label": str(raw.get("user_label", "") or ""),
        "username": str(raw.get("username", "") or ""),
        "password": str(raw.get("password", "") or ""),
        "system_aliases": _parse_alias_list(raw.get("system_aliases")),
        "user_aliases": _parse_alias_list(raw.get("user_aliases")),
    }


def _migrate_profiles_to_accounts(profiles: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for pid, raw in profiles.items():
        if not isinstance(raw, dict):
            continue
        system = str(raw.get("system", "") or "")
        ul = str(raw.get("user_label", "") or "")
        if not ul.strip():
            ul = str(pid)
        entry = _account_from_dict({**raw, "system": system, "user_label": ul})
        out.append(entry)
    return out


def _load_raw_file(path: Optional[str] = None) -> Any:
    p = path or resolve_credentials_path()
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def load_accounts(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load all accounts (with secrets). Legacy profiles{} is migrated in memory only."""
    data = _load_raw_file(path)
    if data is None:
        return []
    if isinstance(data, dict) and isinstance(data.get("accounts"), list):
        acc = data["accounts"]
        return [_account_from_dict(x) for x in acc if isinstance(x, dict)]
    if isinstance(data, dict) and isinstance(data.get("profiles"), dict):
        return _migrate_profiles_to_accounts(data["profiles"])
    return []


def load_accounts_catalog(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Non-secret catalog for prompts: system, user_label, system_aliases, user_aliases only.
    Stable order: by (norm system, norm user_label).
    """
    rows: List[Dict[str, Any]] = []
    for a in load_accounts(path):
        rows.append(
            {
                "system": a.get("system", "") or "",
                "user_label": a.get("user_label", "") or "",
                "system_aliases": list(a.get("system_aliases") or []),
                "user_aliases": list(a.get("user_aliases") or []),
            }
        )
    rows.sort(key=lambda r: (_norm(r["system"]), _norm(r["user_label"])))
    return rows


def catalog_text_block(path: Optional[str] = None) -> str:
    """Human-readable block for injection into computer vision prompt."""
    cat = load_accounts_catalog(path)
    if not cat:
        return ""
    lines = [
        "**Saved login accounts (metadata only — no passwords):**",
        "Use **account_login** with **system** and optional **user_label** matching below. "
        "Do not put usernames or passwords in tool_args.",
        "",
    ]
    by_system: Dict[str, List[Dict[str, Any]]] = {}
    for row in cat:
        sys_key = row["system"] or "(empty system)"
        by_system.setdefault(sys_key, []).append(row)
    for sys_name in sorted(by_system.keys(), key=_norm):
        lines.append(f"- **System:** {sys_name}")
        for row in by_system[sys_name]:
            ul = row["user_label"] or "(default label empty — use only if this system has one account)"
            extra = []
            if row.get("system_aliases"):
                extra.append(f"aliases: {', '.join(row['system_aliases'])}")
            if row.get("user_aliases"):
                extra.append(f"user_aliases: {', '.join(row['user_aliases'])}")
            suf = f" ({'; '.join(extra)})" if extra else ""
            lines.append(f"  - **user_label:** {ul}{suf}")
        lines.append("")
    lines.append(
        "To log in with **all accounts** for a system in turn: call **account_login** once per row above "
        "(same **system**, different **user_label**), in list order, with **wait** / verification between attempts."
    )
    return "\n".join(lines).strip()


def _system_matches(account: Dict[str, Any], query_system: str) -> bool:
    nq = _norm(query_system)
    if not nq:
        return False
    if _norm(account.get("system", "") or "") == nq:
        return True
    for a in account.get("system_aliases") or []:
        if _norm(str(a)) == nq:
            return True
    return False


def _user_label_matches(account: Dict[str, Any], query_label: str) -> bool:
    nl = _norm(query_label)
    if not nl:
        return False
    if _norm(account.get("user_label", "") or "") == nl:
        return True
    for a in account.get("user_aliases") or []:
        if _norm(str(a)) == nl:
            return True
    return False


def _to_credential_row(account: Dict[str, Any]) -> Dict[str, str]:
    return {
        "username": str(account.get("username", "") or ""),
        "password": str(account.get("password", "") or ""),
        "system": str(account.get("system", "") or ""),
        "user_label": str(account.get("user_label", "") or ""),
    }


def resolve_account(
    system: str,
    user_label: Optional[str] = None,
    path: Optional[str] = None,
) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """
    Resolve (system, user_label?) to {username, password, system, user_label}.
    user_label may be omitted only when exactly one account matches system.
    """
    sys_q = (system or "").strip()
    if not sys_q:
        return None, "system is required in tool_args (identify the target product / site)."

    accounts = load_accounts(path)
    candidates = [a for a in accounts if _system_matches(a, sys_q)]
    if not candidates:
        systems = sorted({(a.get("system") or "") for a in accounts if (a.get("system") or "").strip()})
        hint = f" Known system names: {systems}." if systems else " No accounts configured."
        return None, f"No saved account matches system {sys_q!r}.{hint}"

    ul_raw = (user_label if user_label is not None else "") or ""
    ul_q = ul_raw.strip()

    if not ul_q:
        if len(candidates) == 1:
            return _to_credential_row(candidates[0]), None
        labels = sorted(
            {
                str(a.get("user_label") or "").strip() or "(empty)"
                for a in candidates
            }
        )
        return (
            None,
            f"System {sys_q!r} has {len(candidates)} accounts; set **user_label** to one of: {labels}.",
        )

    matches = [a for a in candidates if _user_label_matches(a, ul_q)]
    if len(matches) == 1:
        return _to_credential_row(matches[0]), None
    if not matches:
        labels = sorted(
            {
                str(a.get("user_label") or "").strip() or "(empty)"
                for a in candidates
            }
        )
        return (
            None,
            f"No account with user_label matching {ul_q!r} for system {sys_q!r}. Options: {labels}.",
        )

    return None, f"Ambiguous user_label {ul_q!r} for system {sys_q!r}; refine user_label or aliases in the credentials file."


def _account_identity_key(a: Dict[str, Any]) -> Tuple[str, str]:
    return (_norm(a.get("system", "") or ""), _norm(a.get("user_label", "") or ""))


def save_accounts_to_file(
    accounts: List[Dict[str, Any]],
    path: Optional[str] = None,
) -> Optional[str]:
    """
    Write {"version": 1, "accounts": [...]}. Validates count and uniqueness of (system, user_label).
    """
    if len(accounts) > _MAX_ACCOUNTS:
        return f"Too many accounts (max {_MAX_ACCOUNTS})."

    normalized: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str]] = set()

    for i, raw in enumerate(accounts):
        if not isinstance(raw, dict):
            return f"accounts[{i}] must be an object."
        a = _account_from_dict(raw)
        sys_v = (a["system"] or "").strip()
        if not sys_v:
            return f"accounts[{i}]: system is required."
        ul_v = (a["user_label"] or "").strip()
        key = _account_identity_key(a)
        if key in seen:
            return f"Duplicate (system, user_label) after normalize: {sys_v!r} / {ul_v!r}."
        seen.add(key)

        entry: Dict[str, Any] = {
            "system": sys_v,
            "user_label": ul_v,
            "username": str(a.get("username", "") or ""),
            "password": str(a.get("password", "") or ""),
        }
        sa = [str(x).strip() for x in (a.get("system_aliases") or []) if str(x).strip()]
        ua = [str(x).strip() for x in (a.get("user_aliases") or []) if str(x).strip()]
        if sa:
            entry["system_aliases"] = sa
        if ua:
            entry["user_aliases"] = ua
        normalized.append(entry)

    p = path or resolve_credentials_path()
    payload = {"version": 1, "accounts": normalized}
    try:
        parent = os.path.dirname(os.path.abspath(p))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError as e:
        return str(e)
    return None


def merge_saved_passwords(
    new_accounts: List[Dict[str, Any]],
    placeholder: str,
    path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Where password equals placeholder, copy from existing file by (system, user_label) identity."""
    old_list = load_accounts(path)
    old_by_key: Dict[Tuple[str, str], str] = {}
    for o in old_list:
        old_by_key[_account_identity_key(o)] = str(o.get("password", "") or "")

    out: List[Dict[str, Any]] = []
    for raw in new_accounts:
        if not isinstance(raw, dict):
            out.append(raw)
            continue
        a = dict(raw)
        pw = a.get("password", "")
        pw = "" if pw is None else str(pw)
        if pw == placeholder:
            tmp = _account_from_dict(a)
            k = _account_identity_key(tmp)
            if k in old_by_key:
                a["password"] = old_by_key[k]
        out.append(a)
    return out


def merge_alias_fields_from_previous(
    new_accounts: List[Dict[str, Any]],
    path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """If new row omits system_aliases/user_aliases, copy from previous file for same (system, user_label)."""
    old_list = load_accounts(path)
    old_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for o in old_list:
        old_by_key[_account_identity_key(o)] = o

    out: List[Dict[str, Any]] = []
    for raw in new_accounts:
        if not isinstance(raw, dict):
            out.append(raw)
            continue
        a = dict(raw)
        tmp = _account_from_dict(a)
        k = _account_identity_key(tmp)
        prev = old_by_key.get(k)
        if prev:
            if not _parse_alias_list(a.get("system_aliases")) and (prev.get("system_aliases") or []):
                a["system_aliases"] = list(prev.get("system_aliases") or [])
            if not _parse_alias_list(a.get("user_aliases")) and (prev.get("user_aliases") or []):
                a["user_aliases"] = list(prev.get("user_aliases") or [])
        out.append(a)
    return out
