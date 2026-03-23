"""
Minimal DaTi CAPTCHA API client: upload image (JSON), poll for answer; config via params/env.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional, Tuple

import requests

DEFAULT_API_URL = "https://api.laladama.com"

# DaTi API status codes (per vendor docs); surfaced to the model with `msg` when present
_DATI_STATUS_MESSAGES: Dict[int, str] = {
    -100: "Insufficient question credits",
    -101: "System error (-101)",
    -102: "System error (-102)",
    -103: "System error (-103)",
    -104: "System error (-104)",
    -105: "System error (-105)",
    -110: "Missing authcode parameter",
    -111: "Invalid authcode",
    -112: "Account for this authcode is disabled",
    -120: "Developer account does not exist",
    -121: "Developer account is disabled",
    -130: "Invalid typeno",
    -131: "Typeno disabled",
    -132: "Developer does not match dedicated typeno",
    -133: "Missing typeno parameter",
    -134: "Contact support to adjust dedicated typeno pricing",
    -150: "Image file error (e.g. multiple uploads)",
    -151: "Image format error (jpg/png/gif/bmp supported)",
    -152: "Image size exceeds limit (default 1MB)",
    -153: "Uploaded file is empty",
    -154: "Server failed to create file",
    -155: "Server failed to save image file",
    -1: "Network or local request error",
}


def format_dati_error(status: Any, msg: Any) -> str:
    """
    Build a readable error for tool responses to the model.
    Do not call when status is 0 (success).
    """
    try:
        code = int(status)
    except (TypeError, ValueError):
        code = -999
    detail = str(msg).strip() if msg is not None else ""
    base = _DATI_STATUS_MESSAGES.get(code)
    if base is None:
        base = f"Unexpected API status code {code}"
    if detail and detail not in (base, str(code)):
        return f"CAPTCHA service error: {code} {detail}"
    return f"CAPTCHA service error: [{code}] {base}"


def _config(
    api_url: Optional[str] = None,
    authcode: Optional[str] = None,
    typeno: Optional[str] = None,
    author: Optional[str] = None,
) -> Dict[str, Any]:
    """Load config from arguments or environment variables."""
    import os
    return {
        "api_url": (api_url or os.environ.get("DATI_API_URL") or DEFAULT_API_URL).rstrip("/"),
        "authcode": authcode or os.environ.get("DATI_AUTHCODE") or "",
        "typeno": typeno or os.environ.get("DATI_TYPENO") or "",
        "author": author or os.environ.get("DATI_AUTHOR") or "",
    }


def upload(
    base64string: str,
    remark: str,
    api_url: Optional[str] = None,
    authcode: Optional[str] = None,
    typeno: Optional[str] = None,
    author: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Upload CAPTCHA image (JSON). base64string should include a prefix such as data:image/png;base64,...
    Returns {"status": 0, "msg": "<task id>"} or {"status": !=0, "msg": "..."}.
    """
    cfg = _config(api_url, authcode, typeno, author)
    payload = {
        "base64string": base64string,
        "authcode": cfg["authcode"],
        "typeno": cfg["typeno"],
        "author": cfg["author"],
        "remark": remark,
    }
    try:
        r = requests.post(
            f"{cfg['api_url']}/member/uploadjson",
            data=json.dumps(payload),
            headers={"content-type": "application/json"},
            timeout=30,
            verify=False,
        )
    except Exception as e:
        return {"status": -1, "msg": f"API request failed: {e}"}
    if r.status_code != 200:
        return {"status": -1, "msg": "API request failed"}
    try:
        return r.json()
    except Exception:
        return {"status": -1, "msg": "Failed to parse response JSON"}


def query(
    subjectno: str,
    api_url: Optional[str] = None,
    authcode: Optional[str] = None,
) -> Dict[str, Any]:
    """Query answer by task id. Returns {"status": 0, "msg": "<answer>"} or other status."""
    cfg = _config(api_url, authcode, None, None)
    payload = {"authcode": cfg["authcode"], "subjectno": subjectno}
    try:
        r = requests.post(
            f"{cfg['api_url']}/member/queryjson",
            data=json.dumps(payload),
            headers={"content-type": "application/json"},
            timeout=15,
            verify=False,
        )
    except Exception as e:
        return {"status": -1, "msg": f"API request failed: {e}"}
    if r.status_code != 200:
        return {"status": -1, "msg": "API request failed"}
    try:
        return r.json()
    except Exception:
        return {"status": -1, "msg": "Failed to parse response JSON"}


def query_until_ready(
    subjectno: str,
    timeout_seconds: float = 60.0,
    poll_interval: float = 1.0,
    api_url: Optional[str] = None,
    authcode: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Poll until status==0 or timeout.
    Returns (answer, None) on success; (None, error_text) on failure/timeout.
    """
    deadline = time.monotonic() + timeout_seconds
    last_out: Optional[Dict[str, Any]] = None
    while time.monotonic() < deadline:
        out = query(subjectno=subjectno, api_url=api_url, authcode=authcode)
        last_out = out
        st = out.get("status")
        if st == 0:
            print(f"[dtsdk] query raw result (full response): {out}")
            ans = out.get("msg")
            text = ans if isinstance(ans, str) else str(ans or "")
            return text, None
        if st not in (-100, None):
            return None, format_dati_error(st, out.get("msg"))
        time.sleep(poll_interval)
    tail = ""
    if last_out is not None:
        tail = f" Last response: status={last_out.get('status')!r}, msg={last_out.get('msg')!r}."
    return None, (
        f"Answer query timed out after {timeout_seconds:.0f}s.{tail}".strip()
    )
