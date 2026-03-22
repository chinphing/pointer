import os
import sys
from typing import Any, Dict, List

from python.helpers.api import ApiHandler, Request
from python.helpers import files, settings

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_COMPUTER_DIR = os.path.join(_ROOT, "agents", "computer")
if _COMPUTER_DIR not in sys.path:
    sys.path.insert(0, _COMPUTER_DIR)
import credential_store  # noqa: E402


class ComputerCredentialsSet(ApiHandler):
    async def process(self, input: Dict[str, Any], request: Request) -> dict:
        ph = settings.PASSWORD_PLACEHOLDER
        if "accounts" not in input:
            return {"success": False, "error": "Missing 'accounts' in request body."}
        raw_in = input["accounts"]
        if not isinstance(raw_in, list):
            return {
                "success": False,
                "error": "'accounts' must be a list of account objects.",
            }

        path = credential_store.resolve_credentials_path()
        cleaned: List[Dict[str, Any]] = []
        for i, sub in enumerate(raw_in):
            if not isinstance(sub, dict):
                return {"success": False, "error": f"accounts[{i}] must be an object."}
            cleaned.append(
                {
                    "system": sub.get("system", ""),
                    "user_label": sub.get("user_label", ""),
                    "username": sub.get("username", ""),
                    "password": sub.get("password", ""),
                    "system_aliases": sub.get("system_aliases", []),
                    "user_aliases": sub.get("user_aliases", []),
                }
            )

        merged = credential_store.merge_saved_passwords(cleaned, ph, path)
        merged = credential_store.merge_alias_fields_from_previous(merged, path)

        err = credential_store.save_accounts_to_file(merged, path)
        if err:
            return {"success": False, "error": err}

        try:
            rel = files.deabsolute_path(path)
        except Exception:
            rel = path
        return {"success": True, "path": rel}
