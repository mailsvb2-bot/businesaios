from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .state_machine import OnboardingSession, OnboardingStep, OnboardingTransition


def build_has_clients_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [{"text": "✅ Да, есть", "callback_data": "autopilot:has_clients:yes"}],
            [{"text": "🤏 Немного", "callback_data": "autopilot:has_clients:some"}],
            [{"text": "🆕 Нет, стартую с нуля", "callback_data": "autopilot:has_clients:no"}],
        ]
    }


def build_budget_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [{"text": "€300 / 7 дней", "callback_data": "autopilot:budget:eur_300"}],
            [{"text": "€500 / 7 дней", "callback_data": "autopilot:budget:eur_500"}],
            [{"text": "€1000 / 7 дней", "callback_data": "autopilot:budget:eur_1000"}],
        ]
    }


def build_ads_connect_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [{"text": "Meta", "callback_data": "autopilot:ads_connect:meta"}],
            [{"text": "Яндекс Директ", "callback_data": "autopilot:ads_connect:yandex_direct"}],
            [{"text": "ВК", "callback_data": "autopilot:ads_connect:vk"}],
            [{"text": "Telegram Ads", "callback_data": "autopilot:ads_connect:telegram_ads"}],
        ]
    }


def next_session(
    *,
    session_cls,
    sess,
    stage,
    diag=None,
    offer_id: Optional[str] = None,
    channel: Optional[str] = None,
    ads_platform: Optional[str] = None,
    tasks: Any = None,
):
    return session_cls(
        stage=stage,
        goal=sess.goal,
        diag=sess.diag if diag is None else diag,
        offer_id=sess.offer_id if offer_id is None else str(offer_id),
        channel=sess.channel if channel is None else str(channel),
        ads_platform=sess.ads_platform if ads_platform is None else str(ads_platform),
        tasks=sess.tasks if tasks is None else tasks,
    )


def transition(
    *,
    session_cls,
    transition_cls,
    sess,
    stage,
    notify_text: str,
    reply_markup: Optional[dict],
    diag=None,
    offer_id: Optional[str] = None,
    channel: Optional[str] = None,
    ads_platform: Optional[str] = None,
    tasks: Any = None,
    use_callback_query_id: bool = False,
):
    return transition_cls(
        session=next_session(
            session_cls=session_cls,
            sess=sess,
            stage=stage,
            diag=diag,
            offer_id=offer_id,
            channel=channel,
            ads_platform=ads_platform,
            tasks=tasks,
        ),
        notify_text=str(notify_text),
        reply_markup=reply_markup,
        use_callback_query_id=bool(use_callback_query_id),
    )
