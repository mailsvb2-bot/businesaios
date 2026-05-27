from __future__ import annotations

from enum import StrEnum
from typing import Any


class EffectActionType(StrEnum):
    TELEGRAM_SEND_MESSAGE = "telegram.send_message"
    TELEGRAM_SEND_AUDIO = "telegram.send_audio"
    TELEGRAM_ANSWER_CALLBACK = "telegram.answer_callback"
    TELEGRAM_SEND_CHAT_ACTION = "telegram.send_chat_action"
    TELEGRAM_SELF_CHECK = "telegram.self_check"
    TELEGRAM_POLL_UPDATES = "telegram.poll_updates"
    PAYMENTS_YOOKASSA_CREATE = "payments.yookassa.create"
    PAYMENTS_YOOKASSA_GET_STATUS = "payments.yookassa.get_status"
    CRM_WRITE_RECORD = "crm.write_record"
    ADS_UPDATE_BUDGET = "ads.update_budget"
    WEBSITE_PUBLISH_PAGE = "website.publish_page"
    WEATHER_OPEN_METEO_CURRENT = "weather.open_meteo.current"
    LLM_MARKETING_COMPLETE = "llm.marketing_complete"
EFFECT_ACTION_ALIASES: dict[str, EffectActionType] = {
    "telegram_send_message": EffectActionType.TELEGRAM_SEND_MESSAGE,
    "telegram_send_audio": EffectActionType.TELEGRAM_SEND_AUDIO,
    "telegram_answer_callback": EffectActionType.TELEGRAM_ANSWER_CALLBACK,
    "telegram_send_chat_action": EffectActionType.TELEGRAM_SEND_CHAT_ACTION,
    "yookassa_create_payment": EffectActionType.PAYMENTS_YOOKASSA_CREATE,
    "yookassa_get_payment_status": EffectActionType.PAYMENTS_YOOKASSA_GET_STATUS,
    "payment_create": EffectActionType.PAYMENTS_YOOKASSA_CREATE,
    "telegram_send": EffectActionType.TELEGRAM_SEND_MESSAGE,
    "crm_write": EffectActionType.CRM_WRITE_RECORD,
    "ads_update_budget": EffectActionType.ADS_UPDATE_BUDGET,
    "website_publish_page": EffectActionType.WEBSITE_PUBLISH_PAGE,
    "weather.current": EffectActionType.WEATHER_OPEN_METEO_CURRENT,
    "weather_open_meteo_current": EffectActionType.WEATHER_OPEN_METEO_CURRENT,
    "marketing_llm_complete": EffectActionType.LLM_MARKETING_COMPLETE,
    "telegram_self_check": EffectActionType.TELEGRAM_SELF_CHECK,
    "telegram_poll_updates": EffectActionType.TELEGRAM_POLL_UPDATES,
}
_EFFECT_ACTION_BY_VALUE: dict[str, EffectActionType] = {str(item): item for item in EffectActionType}
def normalize_effect_action_type(action_type: Any) -> str:
    resolved = resolve_effect_action_type(action_type)
    return str(resolved) if resolved is not None else ""
def resolve_effect_action_type(action_type: Any) -> EffectActionType | None:
    if isinstance(action_type, EffectActionType):
        return action_type
    key = str(action_type or "").strip().lower().replace("@", ".")
    if not key:
        return None
    direct = _EFFECT_ACTION_BY_VALUE.get(key)
    if direct is not None:
        return direct
    return EFFECT_ACTION_ALIASES.get(key)
def require_effect_action_type(action_type: Any) -> EffectActionType:
    resolved = resolve_effect_action_type(action_type)
    if resolved is None:
        key = str(action_type or "").strip()
        raise RuntimeError(f"unsupported_effect_action:{key.lower().replace('@', '.')}")
    return resolved
def canonical_effect_action_types() -> tuple[str, ...]:
    return tuple(sorted(str(item) for item in EffectActionType))
