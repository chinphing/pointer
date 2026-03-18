"""
DaTi 验证码 API 客户端（精简版）。
仅保留：上传验证码图（JSON）、轮询查询答案；配置参数化。
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import requests

DEFAULT_API_URL = "https://api.laladama.com"


def _config(
    api_url: Optional[str] = None,
    authcode: Optional[str] = None,
    typeno: Optional[str] = None,
    author: Optional[str] = None,
) -> Dict[str, Any]:
    """从参数或环境变量读取配置。"""
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
    上传验证码图片（JSON）。base64string 需带前缀如 data:image/png;base64,...
    返回 {"status": 0, "msg": "题号"} 或 {"status": !=0, "msg": "错误信息"}。
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
        return {"status": -1, "msg": f"访问接口出错: {e}"}
    if r.status_code != 200:
        return {"status": -1, "msg": "访问接口出错"}
    try:
        return r.json()
    except Exception:
        return {"status": -1, "msg": "响应解析失败"}


def query(
    subjectno: str,
    api_url: Optional[str] = None,
    authcode: Optional[str] = None,
) -> Dict[str, Any]:
    """按题号查询答案。返回 {"status": 0, "msg": "答案"} 或其它 status。"""
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
        return {"status": -1, "msg": f"访问接口出错: {e}"}
    if r.status_code != 200:
        return {"status": -1, "msg": "访问接口出错"}
    try:
        return r.json()
    except Exception:
        return {"status": -1, "msg": "响应解析失败"}


def query_until_ready(
    subjectno: str,
    timeout_seconds: float = 60.0,
    poll_interval: float = 1.0,
    api_url: Optional[str] = None,
    authcode: Optional[str] = None,
) -> Optional[str]:
    """
    轮询查询直到 status==0 或超时。返回答案字符串，超时或失败返回 None。
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        out = query(subjectno=subjectno, api_url=api_url, authcode=authcode)
        if out.get("status") == 0:
            print(f"[dtsdk] query raw result (full response): {out}")
            return out.get("msg") if isinstance(out.get("msg"), str) else str(out.get("msg", ""))
        if out.get("status") not in (-100, None):
            break
        time.sleep(poll_interval)
    return None
