from __future__ import annotations

from core.observability.structured_logging import log_exception_throttled
from core.policies.telegram.handlers.autopilot_parts.flow_diag import handle_diag_text
from core.policies.telegram.handlers.autopilot_parts.flow_launch import build_launch_action
from core.policies.telegram.handlers.autopilot_parts.shared import kb_pick_channel, set_session
from core.policies.telegram.helpers import ProposedAction, propose
from core.tenancy.normalization import normalize_tenant_id_or_unknown
from core.ux.callbacks import (
    CB_AUTOPILOT_MENU,
    CB_AUTOPILOT_START_7D,
    CB_PROFIT_SPRINT_LEAD_ADS,
    CB_PROFIT_SPRINT_LEAD_CALLS,
    CB_PROFIT_SPRINT_LEAD_INBOX,
    CB_PROFIT_SPRINT_LEAD_SITE,
    CB_PROFIT_SPRINT_LEAD_SOCIAL,
    CB_PROFIT_SPRINT_START,
)
from core.ux.telegram_keyboards import kb_back_main

_LEAD_SOURCE_MAP = {
    CB_PROFIT_SPRINT_LEAD_INBOX: "inbox",
    CB_PROFIT_SPRINT_LEAD_CALLS: "calls",
    CB_PROFIT_SPRINT_LEAD_SITE: "site",
    CB_PROFIT_SPRINT_LEAD_SOCIAL: "social",
    CB_PROFIT_SPRINT_LEAD_ADS: "ads",
}


def handle_flow(ctx, *, user_id: str, default_price_rub: int, sess: dict, sl, logger) -> ProposedAction | None:
    cb = str(ctx.callback_data or "")

    if cb == CB_PROFIT_SPRINT_START:
        return propose(
            "execute_plan@v1",
            {
                "user_id": str(user_id),
                "steps": [
                    {"action": "set_user_setting@v1", "payload": {"user_id": str(user_id), "key": "profit_sprint:onboarding", "value": {"active": True}}},
                    {"action": "profit_sprint_onboarding_start@v1", "payload": {"user_id": str(user_id)}},
                ],
            },
        )

    if cb == CB_AUTOPILOT_START_7D:
        return set_session(
            user_id=user_id,
            sess={"stage": "diag:what", "goal": "profit_7d", "diag": {}},
            notify_text="Шаг 0/4 — Диагностика\n\n1) Что вы продаёте? (одно предложение)\n\nНапиши ответ сообщением.",
            reply_markup=kb_back_main(),
            callback_query_id=ctx.callback_query_id,
        )

    if cb in _LEAD_SOURCE_MAP:
        return propose(
            "execute_plan@v1",
            {
                "user_id": str(user_id),
                "steps": [
                    {
                        "action": "profit_sprint_onboarding_lead_source@v1",
                        "payload": {
                            "user_id": str(user_id),
                            "lead_source": _LEAD_SOURCE_MAP.get(cb, ""),
                            "tenant_id": normalize_tenant_id_or_unknown(getattr(ctx.state, "tenant_id", None)),
                            "gate_settings": (ctx.settings if isinstance(ctx.settings, dict) else {}),
                        },
                    },
                    {"action": "set_user_setting@v1", "payload": {"user_id": str(user_id), "key": "profit_sprint:onboarding", "value": {"active": False}}},
                ],
            },
        )

    if isinstance(ctx.text, str) and ctx.text.strip():
        try:
            ps = (ctx.settings.get("profit_sprint:onboarding") if isinstance(ctx.settings, dict) else None) or {}
            if isinstance(ps, dict) and ps.get("active"):
                return propose("profit_sprint_onboarding_text@v1", {"user_id": str(user_id), "text": ctx.text.strip()})
        except Exception as exc:
            log_exception_throttled(__name__, "autopilot_profit_sprint_settings_read_failed", exc)

    if isinstance(ctx.text, str) and ctx.text.strip() and str(sess.get("stage") or "").startswith("diag:"):
        return _handle_diag_text(ctx, user_id=user_id, default_price_rub=default_price_rub, sess=sess)

    if cb.startswith("autopilot:pick_offer:"):
        oid = cb.split(":", 2)[2].strip() if ":" in cb else ""
        diag = dict(sess.get("diag") or {}) if isinstance(sess.get("diag"), dict) else {}
        diag["offer"] = str(oid)
        sess["diag"] = diag
        sess["stage"] = "pick:channel"
        return set_session(
            user_id=user_id,
            sess=sess,
            notify_text="Шаг 2/4 — Выбери канал запуска:",
            reply_markup=kb_pick_channel(),
            callback_query_id=ctx.callback_query_id,
        )

    if cb.startswith("autopilot:pick_channel:"):
        ch = cb.split(":", 2)[2].strip() if ":" in cb else "internal"
        diag = dict(sess.get("diag") or {}) if isinstance(sess.get("diag"), dict) else {}
        diag["channel"] = "external" if ch == "external" else "internal"
        sess["diag"] = diag
        sess["stage"] = "ready:launch"
        return set_session(
            user_id=user_id,
            sess=sess,
            notify_text="Шаг 3/4 — Запуск\n\nНажми ‘Запустить’, и я начну измерять и предлагать улучшения.",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "✅ Запустить", "callback_data": "autopilot:launch"}],
                    [{"text": "⬅️ Назад", "callback_data": CB_AUTOPILOT_MENU}],
                ]
            },
            callback_query_id=ctx.callback_query_id,
        )

    if cb == "autopilot:launch":
        return build_launch_action(ctx, user_id=user_id, default_price_rub=default_price_rub, sess=sess, sl=sl, logger=logger)

    return None


def _handle_diag_text(ctx, *, user_id: str, default_price_rub: int, sess: dict):
    return handle_diag_text(ctx, user_id=user_id, default_price_rub=default_price_rub, sess=sess)
