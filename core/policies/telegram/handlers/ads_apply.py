from __future__ import annotations

from typing import Any

from core.ads.apply_flow_codec import PENDING_KEY, plan_summary_text
from core.ads.apply_gate import AdsApplyState, build_ads_apply_toggle_action
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
        # One signed canonical settings action. Nested execute_plan effects
        # cannot be issued by one DecisionCore envelope.
        return propose(
            "set_user_setting@v1",
            {
                "user_id": str(user_id),
                "key": PENDING_KEY,
                "value": None,
                "notify_text": "🗑 План отменён. Ничего не применено.",
                "notify_reply_markup": {"inline_keyboard": [[
                    {"text": "⬅️ Назад", "callback_data": CB_ADS_APPLY_MENU},
                ]]},
                "callback_query_id": ctx.callback_query_id,
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
        if not st.enabled:
            return propose_message(
                user_id=str(user_id),
                text="🛑 Применение выключено. Сначала разрешите его в Ads Apply.",
                reply_markup=kb_ads_apply_pending(can_apply=False),
                callback_query_id=ctx.callback_query_id,
            )
        from core.policies.telegram.handlers.ads_apply_flow import propose_confirmed_apply

        result = propose_confirmed_apply(ctx, user_id=str(user_id), pending=pending)
        if result is not None:
            return result
        return propose_message(
            user_id=str(user_id),
            text="План неполный. Повторите подготовку и предпросмотр.",
            reply_markup=kb_ads_apply_pending(can_apply=False),
            callback_query_id=ctx.callback_query_id,
        )

    # --- Gate toggles ---
    if cb == CB_ADS_APPLY_ENABLE:
        return propose("set_user_setting@v1", build_ads_apply_toggle_action(
            user_id=str(user_id), enabled=True, callback_query_id=ctx.callback_query_id,
        ))

    if cb == CB_ADS_APPLY_DISABLE:
        return propose("set_user_setting@v1", build_ads_apply_toggle_action(
            user_id=str(user_id), enabled=False, callback_query_id=ctx.callback_query_id,
        ))

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
