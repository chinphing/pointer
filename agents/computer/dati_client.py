"""
DaTi 验证码 API 客户端（精简版）。
仅保留：上传验证码图（JSON）、轮询查询答案；配置参数化。
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional, Tuple

import requests

DEFAULT_API_URL = "https://api.laladama.com"

# DaTi 接口 status 说明（与官方文档一致）；失败时与 msg 一并展示给大模型
_DATI_STATUS_MESSAGES: Dict[int, str] = {
    -100: "题分余额不足",
    -101: "系统出错（-101）",
    -102: "系统出错（-102）",
    -103: "系统出错（-103）",
    -104: "系统出错（-104）",
    -105: "系统出错（-105）",
    -110: "缺少 authcode 参数",
    -111: "无效的 authcode",
    -112: "authcode 对应的帐号已禁用",
    -120: "开发者帐号不存在",
    -121: "开发者帐号已禁用",
    -130: "题型编号错误",
    -131: "题型编号禁用",
    -132: "开发者与专属题型编号不一致",
    -133: "缺少 typeno 参数",
    -134: "联系客服修改专属题型价格",
    -150: "图片文件错误（如上传多张）",
    -151: "图片格式错误（支持 jpg/png/gif/bmp）",
    -152: "图片容量超过限制（默认 1M）",
    -153: "上传文件内容为空",
    -154: "系统创建文件出错",
    -155: "保存图片文件出错",
    -1: "网络或本地请求异常",
}


def format_dati_error(status: Any, msg: Any) -> str:
    """
    将上传/查询接口的 status 与 msg 拼成可读说明，供工具返回给大模型。
    status 0 表示成功，不应调用本函数。
    """
    try:
        code = int(status)
    except (TypeError, ValueError):
        code = -999
    detail = str(msg).strip() if msg is not None else ""
    base = _DATI_STATUS_MESSAGES.get(code)
    if base is None:
        base = f"接口返回异常状态码 {code}"
    if detail and detail not in (base, str(code)):
        return f"验证码识别异常：{code} {detail}"
    return f"验证码识别异常： [{code}] {base}"


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
) -> Tuple[Optional[str], Optional[str]]:
    """
    轮询查询直到 status==0 或超时。
    返回 (answer, None) 成功；(None, error_text) 失败或超时，error_text 含状态码说明，便于返回大模型。
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
        tail = f" 最后一次响应: status={last_out.get('status')!r}, msg={last_out.get('msg')!r}."
    return None, (
        f"查询答案超时（{timeout_seconds:.0f}s 内未完成）。{tail}".strip()
    )
