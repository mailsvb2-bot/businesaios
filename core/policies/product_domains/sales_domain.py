from __future__ import annotations

from dataclasses import dataclass

from core.policies.product_domains.sales_domain_support import build_offer_action
from core.policies.sales.sales_keyboards import sales_main_kb
from core.policies.telegram.helpers import ProposedAction, propose_message
from core.tenancy.normalization import normalize_tenant_id_or_unknown


@dataclass
class SalesDomainPolicyV1:
    """Lightweight domain policy (delegated from UnifiedTelegramPolicyV3).

    IMPORTANT:
    - This is NOT a DecisionCore policy.
    - It is a pure router for a product domain inside the single active Telegram policy.
    - Side-effects are proposed as explicit actions (DecisionCore validates; Runtime executes).
    """

    def propose(self, state) -> ProposedAction:
        session = dict(getattr(state, "session", {}) or {})
        text = str(session.get("text") or "").strip()
        cb = str(session.get("callback_data") or "") if bool(session.get("is_callback")) else ""
        callback_query_id = str(session.get("callback_query_id")) if session.get("callback_query_id") else None
        user_id = str(getattr(state, "user_id", "anonymous") or "anonymous")
        tenant_id = normalize_tenant_id_or_unknown(getattr(state, "tenant_id", None))

        locale = "ru"
        try:
            locale = str((getattr(state, "user", {}) or {}).get("locale") or "ru")
        except Exception:
            locale = "ru"

        if text.lower().startswith("/start"):
            return propose_message(
                user_id=user_id,
                text="Привет. Это SalesBot.\nЯ предложу лучший вариант, когда будет подходящий момент.",
                reply_markup=sales_main_kb(),
                callback_query_id=callback_query_id,
            )

        if cb == "sales:one_click_value":
            return build_offer_action(
                state=state,
                user_id=user_id,
                tenant_id=tenant_id,
                locale=locale,
                last_user_text=text,
                callback_query_id=callback_query_id,
                step_key="sales:one_click_value",
                context={"domain": "sales", "one_click": True},
                action_name="one_click_value@v1",
                track_event_type="one_click_value_shown",
                fallback_text="Сделаю один быстрый шаг к результату. Открыть 30 дней за 600 ₽?",
            )

        if cb == "sales:offer":
            return build_offer_action(
                state=state,
                user_id=user_id,
                tenant_id=tenant_id,
                locale=locale,
                last_user_text=text,
                callback_query_id=callback_query_id,
                step_key="sales:offer_30",
                context={"domain": "sales"},
                action_name="send_marketing_offer@v1",
                track_event_type="offer_shown",
                fallback_text="Предложение: 30 дней за 600 ₽",
            )

        if cb == "sales:price_down":
            return propose_message(
                user_id=user_id,
                text=(
                    "Ок. Если сейчас не вовремя — можно начать мягче.\n"
                    "Нажми «Предложение», когда будет удобно."
                ),
                reply_markup=sales_main_kb(),
                callback_query_id=callback_query_id,
            )

        return propose_message(
            user_id=user_id,
            text="Меню SalesBot:",
            reply_markup=sales_main_kb(),
            callback_query_id=callback_query_id,
        )
