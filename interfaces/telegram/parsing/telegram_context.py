"""Telegram update parsing (PURE).

This module is intentionally side-effect free.
It extracts a normalized TelegramContext from a raw update dict.

WorldState building is handled elsewhere (runtime reducers).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

def extract_telegram_user_id(update: dict) -> int | None:
    """Extract Telegram sender user id from update (best-effort).

    Prefer a stable sender id over chat id.
    Returns None if unavailable.
    """
    try:
        if isinstance(update, dict):
            if "message" in update and isinstance(update.get("message"), dict):
                frm = update["message"].get("from")
                if isinstance(frm, dict) and frm.get("id") is not None:
                    return int(frm["id"])
            if "callback_query" in update and isinstance(update.get("callback_query"), dict):
                frm = update["callback_query"].get("from")
                if isinstance(frm, dict) and frm.get("id") is not None:
                    return int(frm["id"])
            if "inline_query" in update and isinstance(update.get("inline_query"), dict):
                frm = update["inline_query"].get("from")
                if isinstance(frm, dict) and frm.get("id") is not None:
                    return int(frm["id"])
    except Exception:
        return None
    return None


@dataclass(frozen=True)
class TelegramContext:
    update_id: int
    chat_id: str
    message_id: int | None
    text: str
    command: str | None
    args: str
    is_callback: bool
    callback_data: str | None
    callback_query_id: str | None
    raw: dict[str, Any]


def _extract_message(update: dict[str, Any]) -> tuple[dict[str, Any] | None, str, bool, str | None]:
    for k in (
        "message",
        "edited_message",
        "channel_post",
        "edited_channel_post",
        "callback_query",
    ):
        if k in update and isinstance(update[k], dict):
            if k == "callback_query":
                msg = update[k].get("message") if isinstance(update[k].get("message"), dict) else None
                data = update[k].get("data")
                txt = str(data) if data is not None else ""
                return msg, txt, True, (str(data) if data is not None else None)
            return update[k], str(update[k].get("text") or ""), False, None
    return None, "", False, None


def _parse_command(text: str) -> tuple[str | None, str]:
    t = (text or "").strip()
    if not t.startswith("/"):
        return None, ""
    first, *rest = t.split(maxsplit=1)
    cmd = first.split("@", 1)[0].lower()
    args = rest[0] if rest else ""
    return cmd, args


def build_context(update: dict[str, Any]) -> TelegramContext | None:
    if not isinstance(update, dict):
        return None
    upd_id = update.get("update_id")
    if upd_id is None:
        return None

    msg, txt, is_cb, cb_data = _extract_message(update)
    cbq_id = None
    if is_cb:
        cbq = update.get("callback_query") if isinstance(update.get("callback_query"), dict) else None
        if isinstance(cbq, dict) and cbq.get("id") is not None:
            cbq_id = str(cbq.get("id"))

    chat_id = None
    msg_id = None
    if isinstance(msg, dict):
        msg_id = msg.get("message_id")
        chat = msg.get("chat") if isinstance(msg.get("chat"), dict) else None
        if isinstance(chat, dict) and chat.get("id") is not None:
            chat_id = str(chat.get("id"))

    if chat_id is None:
        return None

    cmd, args = _parse_command(txt)
    return TelegramContext(
        update_id=int(upd_id),
        chat_id=str(chat_id),
        message_id=int(msg_id) if msg_id is not None else None,
        text=str(txt or ""),
        command=cmd,
        args=str(args or ""),
        is_callback=bool(is_cb),
        callback_data=str(cb_data) if cb_data is not None else None,
        callback_query_id=str(cbq_id) if cbq_id is not None else None,
        raw=update,
    )


def now_ms() -> int:
    return int(time.time() * 1000)
