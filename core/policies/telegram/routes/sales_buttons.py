"""«Продажи» as buttons: the same sales_pipeline@v1 ops as /leads, /lead_add, ...

Pure policy. A button either proposes the op directly (lists, claim, card) or,
for ops that need text, stores a short one-shot input session (user setting
``sales:input``, 10 min). The next plain message becomes the op argument; the
executor clears the session in the same signed decision (``input_session``).
Leads are addressed by stable lead_id, not by list position.
"""

from __future__ import annotations

import re

from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose
from core.users.roles import has_permission

SALES_INPUT_KEY = "sales:input"
SESSION_TTL_MS = 10 * 60 * 1000
_LEAD_ID = re.compile(r"^lead_[0-9a-f]{16}$")
LIST_BUTTONS = {  # callback -> sales_pipeline op (same as the command)
    "sales:menu": "list", "sales:leads": "list", "sales:due": "due", "sales:followups": "followup",
    "sales:handoffs": "handoffs", "sales:closed": "closed",
}
LEAD_BUTTONS = {"claim": "claim", "card": "card", "take": "assign"}  # sales:do:<op>:<lead_id>
INPUT_PROMPTS = {  # sales:in:<op>[:<lead_id>] -> prompt
    "add": "➕ Новый лид. Отправьте одним сообщением: Имя | источник\nНапример: Анна | Instagram",
    "note": "📝 Напишите текст заметки к лиду.",
    "next": "⏰ Следующий шаг. Отправьте: ГГГГ-ММ-ДД ЧЧ:ММ | что сделать\nНапример: 2027-01-20 10:00 | позвонить",
    "assign": "👤 Отправьте ID участника команды (см. /team) или «-», чтобы снять ответственного.",
}


def _allowed(ctx: TelegramCtx) -> bool:  # same RBAC as the owner-only /lead* commands
    return has_permission(ctx, "sales") and has_permission(ctx, "business_manage")


def _op(ctx: TelegramCtx, user_id: str, op: str, arg: str = "", **extra) -> ProposedAction:
    return propose("sales_pipeline@v1", {"user_id": user_id, "op": op, "arg": arg[:200], **extra})


def _setting(ctx: TelegramCtx, user_id: str, value: dict, text: str, markup: dict | None = None) -> ProposedAction:
    payload = {"user_id": user_id, "key": SALES_INPUT_KEY, "value": value, "notify_text": text}
    if markup:
        payload["notify_reply_markup"] = markup
    if ctx.callback_query_id:
        payload["callback_query_id"] = str(ctx.callback_query_id)
    return propose("set_user_setting@v1", payload)


def _session(ctx: TelegramCtx) -> dict:
    raw = ctx.settings.get(SALES_INPUT_KEY) if isinstance(ctx.settings, dict) else None
    if not isinstance(raw, dict) or str(raw.get("op") or "") not in INPUT_PROMPTS:
        return {}
    expires = raw.get("expires_ms")
    now = int(getattr(ctx.state, "timestamp_ms", 0) or 0)
    if not isinstance(expires, int) or now <= 0 or now > expires:
        return {}
    lead = str(raw.get("lead_id") or "")
    if lead and not _LEAD_ID.fullmatch(lead):
        return {}
    return {"op": str(raw["op"]), "lead_id": lead}


def _input_arg(op: str, lead: str, text: str) -> str:
    if op == "add":
        return text
    if op == "assign":
        return f"{lead} {text.split()[0] if text.split() else ''}".strip()
    return f"{lead} | {text}"  # note, next


def handle_sales_buttons(ctx: TelegramCtx, *, user_id: str) -> ProposedAction | None:
    data = str(ctx.callback_data or "")
    if data.startswith("sales:"):
        if not _allowed(ctx):
            return None  # router RBAC already answered; never leak sales data
        if data in LIST_BUTTONS:
            return _op(ctx, user_id, LIST_BUTTONS[data])
        parts = data.split(":")
        if len(parts) == 4 and parts[1] == "do" and parts[2] in LEAD_BUTTONS and _LEAD_ID.fullmatch(parts[3]):
            # «Взять в работу» = /lead_assign <lead> <me>; the executor checks team membership.
            arg = f"{parts[3]} {user_id}" if parts[2] == "take" else parts[3]
            return _op(ctx, user_id, LEAD_BUTTONS[parts[2]], arg)
        if parts[1:2] == ["in"] and len(parts) in (3, 4) and parts[2] in INPUT_PROMPTS:
            lead = parts[3] if len(parts) == 4 else ""
            if (parts[2] == "add") == bool(lead) or (lead and not _LEAD_ID.fullmatch(lead)):
                return None
            now = int(getattr(ctx.state, "timestamp_ms", 0) or 0)
            return _setting(ctx, user_id, {"op": parts[2], "lead_id": lead, "expires_ms": now + SESSION_TTL_MS},
                            INPUT_PROMPTS[parts[2]] + "\n\nОтмена — кнопкой ниже или словом «отмена».",
                            {"inline_keyboard": [[{"text": "✖️ Отмена", "callback_data": "sales:cancel"}]]})
        if data == "sales:cancel":
            return _setting(ctx, user_id, {}, "Ок, отменено.",
                            {"inline_keyboard": [[{"text": "💰 Продажи", "callback_data": "sales:menu"}]]})
        return None
    text = str(ctx.text or "").strip()
    if data or ctx.cmd or not text:
        return None
    session = _session(ctx)
    if not session or not _allowed(ctx):
        return None
    if text.casefold() in {"отмена", "cancel"}:
        return _setting(ctx, user_id, {}, "Ок, отменено.")
    return _op(ctx, user_id, session["op"], _input_arg(session["op"], session["lead_id"], text), input_session=True)


__all__ = ["SALES_INPUT_KEY", "handle_sales_buttons"]
