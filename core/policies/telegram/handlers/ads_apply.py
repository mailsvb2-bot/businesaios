from __future__ import annotations

from typing import Any, Dict

from core.ads.apply_flow_codec import PENDING_KEY, compute_plan_idempotency_key, plan_summary_text
from core.ads.apply_gate import AdsApplyState, build_disable_ads_apply_plan, build_enable_ads_apply_plan
from core.policies.telegram.context import TelegramCtx
from core.policies.telegram.helpers import ProposedAction, propose, propose_message
from core.ux.callbacks import (
    CB_ADS_APPLY_CANCEL,
    CB_ADS_APPLY_CONFIRM,
    CB_ADS_APPLY_DISABLE,
    CB_ADS_APPLY_ENABLE,
    CB_ADS_APPLY_MENU,
    CB_ADS_APPLY_PREVIEW,
)
from core.ux.telegram_keyboards import kb_ads_apply_pending


def _get_pending(settings: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(settings, dict):
        return None
    p = settings.get(PENDING_KEY)
    return dict(p) if isinstance(p, dict) else None


def handle_ads_apply(ctx: TelegramCtx, *, user_id: str) -> ProposedAction:
    cb = str(ctx.callback_data or "")
    st = AdsApplyState.from_settings(ctx.settings if isinstance(ctx.settings, dict) else {})

    pending = _get_pending(ctx.settings if isinstance(ctx.settings, dict) else None)

    # --- Flow actions ---
    if cb == CB_ADS_APPLY_CANCEL:
        # Clear pending plan
        return propose(
            "execute_plan@v1",
            {
                "user_id": str(user_id),
                "steps": [
                    {"action": "set_user_setting@v1", "payload": {"user_id": str(user_id), "key": PENDING_KEY, "value": None}},
                    {
                        "action": "send_message@v1",
                        "payload": {
                            "user_id": str(user_id),
                            "text": "🗑 План отменён. Ничего не применено.",
                            "reply_markup": {"inline_keyboard": [[{"text": "⬅️ Назад", "callback_data": CB_ADS_APPLY_MENU}]]},
                            "callback_query_id": ctx.callback_query_id,
                        },
                    },
                ],
            },
        )

    if cb == CB_ADS_APPLY_PREVIEW:
        txt = plan_summary_text(pending)
        return propose_message(
            user_id=str(user_id),
            text=txt,
            reply_markup=kb_ads_apply_pending(),
            callback_query_id=ctx.callback_query_id,
            track_event_type="ads_apply_preview_opened" + "@v1",
            track_payload={"has_pending": bool(pending)},
        )

    if cb == CB_ADS_APPLY_CONFIRM:
        if not pending:
            return propose_message(
                user_id=str(user_id),
                text="Нет активного плана. Сначала собери план (Profit Sprint / Autopilot).",
                reply_markup={"inline_keyboard": [[{"text": "⬅️ Назад", "callback_data": CB_ADS_APPLY_MENU}]]},
                callback_query_id=ctx.callback_query_id,
            )
        idem = compute_plan_idempotency_key(pending)
        # Strict single-path: execution happens only via ads_apply_flow (pending confirm).
        return propose_message(
            user_id=str(user_id),
            text="ℹ️ План готов. Открой предпросмотр/подтверждение в Ads Apply Pending.",
            reply_markup=kb_ads_apply_pending(can_apply=AdsApplyState.from_settings(ctx.settings).enabled),
            callback_query_id=ctx.callback_query_id,
        )

    # --- Gate toggles ---
    if cb == CB_ADS_APPLY_ENABLE:
        return propose("execute_plan@v1", build_enable_ads_apply_plan(user_id=str(user_id), callback_query_id=ctx.callback_query_id))

    if cb == CB_ADS_APPLY_DISABLE:
        return propose("execute_plan@v1", build_disable_ads_apply_plan(user_id=str(user_id), callback_query_id=ctx.callback_query_id))

    # --- Menu (default) ---
    rm = {"inline_keyboard": []}
    if pending:
        rm["inline_keyboard"].append([{ "text": "🧾 План готов (открыть)", "callback_data": CB_ADS_APPLY_PREVIEW }])
    if st.enabled:
        rm["inline_keyboard"].append([{ "text": "🛑 Отключить применение", "callback_data": CB_ADS_APPLY_DISABLE }])
    else:
        rm["inline_keyboard"].append([{ "text": "✅ Разрешить применение", "callback_data": CB_ADS_APPLY_ENABLE }])
    rm["inline_keyboard"].append([{ "text": "⬅️ Назад", "callback_data": "autopilot:menu" }])

    txt = (
        "🧩 Ads Apply (prod gate)\n\n"
        "По умолчанию система делает *dry-run*: строит план и показывает изменения, но не применяет их.\n\n"
        f"Статус: {'✅ разрешено' if st.enabled else '🛑 запрещено'}\n"
        + ("\n🧾 Есть pending-план (можно просмотреть/подтвердить).\n" if pending else "")
        + "\nРазрешение нужно только для необратимых действий (создание/изменение кампаний).\n"
        "В любой момент можно отключить обратно."
    )

    return propose_message(
        user_id=str(user_id),
        text=txt,
        reply_markup=rm,
        callback_query_id=ctx.callback_query_id,
        track_event_type="ads_apply_menu_opened" + "@v1",
        track_payload={"enabled": bool(st.enabled), "has_pending": bool(pending)},
    )
