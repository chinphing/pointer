"""
Development-only: dump each chat LLM request to a readable file for copy-paste / UI verification.

- Only when runtime.is_development() and A0_DEV_PROMPT_DUMP is not disabled (default: enabled in dev).
- Writes under tmp/prompt_dumps/ as Markdown. Base64 image URLs are replaced with short placeholders.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage


def enabled() -> bool:
    try:
        from python.helpers import runtime

        if not runtime.is_development():
            return False
    except Exception:
        return False
    v = (os.environ.get("A0_DEV_PROMPT_DUMP") or "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    return True


def _safe_filename_part(s: str, max_len: int = 40) -> str:
    s = re.sub(r"[^\w\-.]", "_", s).strip("_")
    return (s[:max_len] if s else "unknown")


def _placeholder_for_data_url(url: str) -> str:
    if not url.startswith("data:") or "base64," not in url:
        t = url[:120] + ("…" if len(url) > 120 else "")
        return f"[image_url: {t}]"
    try:
        _, _, b64 = url.partition("base64,")
        n = len(b64)
        approx_bytes = n * 3 // 4
        mime = url.split(";", 1)[0].replace("data:", "")
        return (
            f"[IMAGE omitted — {mime or 'image'}, ~{approx_bytes} bytes base64; "
            f"not inlined so you can copy this file as text. Full image is only in the live API call.]"
        )
    except Exception:
        return "[IMAGE omitted — base64 data URL]"


def _format_message_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for i, block in enumerate(content):
            if isinstance(block, dict):
                btype = block.get("type", "")
                if btype == "text":
                    parts.append(block.get("text") or "")
                elif btype == "image_url":
                    url_obj = block.get("image_url")
                    if isinstance(url_obj, dict):
                        u = url_obj.get("url") or ""
                    else:
                        u = str(url_obj or "")
                    parts.append(_placeholder_for_data_url(u))
                else:
                    parts.append(f"[block {i+1} type={btype!r}]\n{block!r}")
            else:
                parts.append(str(block))
        return "\n\n".join(parts)
    return str(content)


def _message_role_label(msg: BaseMessage) -> str:
    name = type(msg).__name__
    if name == "SystemMessage":
        return "system"
    if name == "HumanMessage":
        return "human"
    if name == "AIMessage":
        return "assistant"
    return name.replace("Message", "").lower() or "message"


def format_messages_markdown(messages: List[BaseMessage]) -> str:
    """Single document: human-readable, safe to copy without multi-MB base64."""
    chunks: List[str] = []
    chunks.append(
        "<!-- Agent Zero — development prompt dump. Images shown as [IMAGE omitted]. -->\n"
    )
    for i, msg in enumerate(messages):
        role = _message_role_label(msg)
        chunks.append(f"## Message {i + 1} — {role}\n\n")
        chunks.append(_format_message_content(msg.content))
        chunks.append("\n\n---\n\n")
    return "".join(chunks).rstrip() + "\n"


def maybe_dump_chat_prompt(agent: Any, messages: List[BaseMessage]) -> None:
    """Call from Agent.call_chat_model. No-op if not development or disabled."""
    if not enabled() or not messages:
        return
    try:
        from python.helpers import files

        out_dir = files.get_abs_path("tmp", "prompt_dumps")
        os.makedirs(out_dir, exist_ok=True)
        ctx = getattr(agent, "context", None)
        ctx_id = getattr(ctx, "id", None) or "no_context"
        loop_data = getattr(agent, "loop_data", None)
        iteration = getattr(loop_data, "iteration", 0) if loop_data is not None else 0
        profile = getattr(getattr(agent, "config", None), "profile", None) or "agent"
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        fname = (
            f"prompt_{ts}_{_safe_filename_part(ctx_id)}_"
            f"iter{iteration}_{_safe_filename_part(profile, 24)}.md"
        )
        path = os.path.join(out_dir, fname)
        header = (
            f"# LLM prompt dump (development)\n\n"
            f"- **UTC time:** {datetime.now(timezone.utc).isoformat()}\n"
            f"- **context_id:** `{ctx_id}`\n"
            f"- **loop iteration:** {iteration}\n"
            f"- **profile:** `{profile}`\n\n"
            f"You can copy everything below into a text editor or a chat input for inspection. "
            f"Image parts are replaced with placeholders to keep the file small.\n\n"
            f"---\n\n"
        )
        body = format_messages_markdown(messages)
        with open(path, "w", encoding="utf-8") as f:
            f.write(header)
            f.write(body)
        try:
            from python.helpers.print_style import PrintStyle

            PrintStyle(font_color="#7a9", padding=False).print(f"[dev] LLM prompt dump → {path}")
        except Exception:
            pass
    except Exception:
        pass
