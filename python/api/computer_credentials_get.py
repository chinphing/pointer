import os
import sys

from python.helpers.api import ApiHandler, Request
from python.helpers import files, settings

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_COMPUTER_DIR = os.path.join(_ROOT, "agents", "computer")
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)
import credential_store  # noqa: E402


class ComputerCredentialsGet(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict:
        path = credential_store.resolve_credentials_path()
        accounts = credential_store.load_accounts(path)
        ph = settings.PASSWORD_PLACEHOLDER
        out: list[dict[str, object]] = []
        for raw in accounts:
            pw = str(raw.get("password", "") or "")
            row: dict[str, object] = {
                "system": str(raw.get("system", "") or ""),
                "user_label": str(raw.get("user_label", "") or ""),
                "username": str(raw.get("username", "") or ""),
                "password": ph if pw else "",
            }
            sa = raw.get("system_aliases") or []
            ua = raw.get("user_aliases") or []
            if sa:
                row["system_aliases"] = list(sa)
            if ua:
                row["user_aliases"] = list(ua)
            out.append(row)
        try:
            rel = files.deabsolute_path(path)
        except Exception:
            rel = path
        return {
            "success": True,
            "path": rel,
            "password_placeholder": ph,
            "accounts": out,
        }

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["GET", "POST"]
