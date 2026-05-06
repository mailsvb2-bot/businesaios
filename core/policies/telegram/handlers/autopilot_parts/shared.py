from __future__ import annotations

from typing import Any, Dict

from core.observability.throttled_logger import exception_throttled
from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose, propose_message
from core.ux.callbacks import CB_AUTOPILOT_MENU


def get_session(ctx: TelegramCtx, logger) -> Dict[str, Any]:
    try:
        if isinstance(ctx.settings, dict):
            return dict(ctx.settings.get("autopilot:session") or {})
    except Exception:
        exception_throttled(logger, key=f"autopilot.get_session|{getattr(ctx,'user_id', 'unknown')}", msg="telegram_autopilot: failed to read session from settings")
        return {}
    return {}


def set_session(*, user_id: str, sess: Dict[str, Any], notify_text: str, reply_markup: dict, callback_query_id: str | None) -> ProposedAction:
    return propose(
        "set_user_setting@v1",
        {
            "user_id": str(user_id),
            "key": "autopilot:session",
            "value": dict(sess),
            "notify_text": str(notify_text),
            "notify_reply_markup": reply_markup,
            "callback_query_id": callback_query_id,
        },
    )


def pm(*, user_id: str, text: str, reply_markup: dict | None, callback_query_id: str | None, track_event_type: str | None = None, track_payload: Dict | None = None) -> ProposedAction:
    return propose_message(
        user_id=str(user_id),
        text=text,
        reply_markup=reply_markup,
        callback_query_id=callback_query_id,
        track_event_type=track_event_type,
        track_payload=track_payload,
    )


def kb_pick_offer(offers: list[tuple[str, str, int]]) -> dict:
    rows = []
    for oid, title, price_rub in offers[:8]:
        rows.append([
            {
                "text": f"{title} — {price_rub} ₽",
                "callback_data": f"autopilot:pick_offer:{oid}",
            }
        ])
    rows.append([{"text": "⬅️ Назад", "callback_data": CB_AUTOPILOT_MENU}])
    return {"inline_keyboard": rows}


def kb_pick_channel() -> dict:
    return {
        "inline_keyboard": [
            [{"text": "📩 Внутренний (сообщения/скрипты)", "callback_data": "autopilot:pick_channel:internal"}],
            [{"text": "📣 Внешний (Ads позже)", "callback_data": "autopilot:pick_channel:external"}],
            [{"text": "⬅️ Назад", "callback_data": CB_AUTOPILOT_MENU}],
        ]
    }
