from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from collections.abc import Mapping

from runtime._internal.effect_types import EffectActionType, require_effect_action_type


class EffectPayloadError(RuntimeError):
    """Raised when an effect payload fails contract normalization."""


def _fail(action_type: EffectActionType, reason: str) -> EffectPayloadError:
    return EffectPayloadError(f"effect_payload_invalid:{str(action_type)}:{reason}")


def _require_mapping(action_type: EffectActionType, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise _fail(action_type, "payload_must_be_mapping")
    return dict(payload)


def _require_text(action_type: EffectActionType, payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _fail(action_type, f"missing_{key}")
    return value.strip()


def _optional_text(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _optional_dict(payload: Mapping[str, Any], key: str) -> dict[str, Any] | None:
    value = payload.get(key)
    return dict(value) if isinstance(value, Mapping) else None


def _bool(payload: Mapping[str, Any], key: str, *, default: bool) -> bool:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _int(
    payload: Mapping[str, Any],
    key: str,
    *,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    raw = payload.get(key, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = int(default)
    if minimum is not None and value < minimum:
        value = minimum
    if maximum is not None and value > maximum:
        value = maximum
    return value


def _optional_int(payload: Mapping[str, Any], key: str) -> int | None:
    raw = payload.get(key)
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _decimal_amount(action_type: EffectActionType, payload: Mapping[str, Any], key: str) -> Decimal:
    raw = payload.get(key)
    if raw is None or raw == "":
        raise _fail(action_type, f"missing_{key}")
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        raise _fail(action_type, f"invalid_{key}") from None
    if value <= 0:
        raise _fail(action_type, f"invalid_{key}")
    return value


def _generic_endpoint_contract(action_type: EffectActionType, payload: Mapping[str, Any]) -> dict[str, Any]:
    endpoint = _optional_text(payload, "url") or _optional_text(payload, "endpoint")
    if endpoint is None:
        raise _fail(action_type, "missing_endpoint")
    headers = _optional_dict(payload, "headers") or {}
    body = payload.get("data") if isinstance(payload.get("data"), Mapping) else payload.get("payload")
    if body is None:
        body = {k: v for k, v in payload.items() if k not in {"url", "endpoint", "headers", "timeout_s"}}
    if not isinstance(body, Mapping):
        raise _fail(action_type, "payload_body_must_be_mapping")
    return {
        "endpoint": str(endpoint),
        "headers": {str(k): str(v) for k, v in dict(headers).items()},
        "data": dict(body),
        "timeout_s": _int(payload, "timeout_s", default=30, minimum=1, maximum=300),
    }


def payload_contract_fields() -> dict[EffectActionType, tuple[str, ...]]:
    return {
        EffectActionType.TELEGRAM_SEND_MESSAGE: ("chat_id", "text", "reply_markup", "priority", "critical", "timeout_s"),
        EffectActionType.TELEGRAM_SEND_AUDIO: ("chat_id", "audio_url", "caption", "priority", "critical", "timeout_s"),
        EffectActionType.TELEGRAM_ANSWER_CALLBACK: ("callback_query_id", "text", "show_alert"),
        EffectActionType.TELEGRAM_SEND_CHAT_ACTION: ("chat_id", "action"),
        EffectActionType.TELEGRAM_SELF_CHECK: ("token",),
        EffectActionType.TELEGRAM_POLL_UPDATES: ("offset", "timeout_s", "limit", "startup_checked", "webhook_cleared"),
        EffectActionType.PAYMENTS_YOOKASSA_CREATE: ("amount_rub", "description", "customer_id", "idempotence_key", "metadata", "timeout_s"),
        EffectActionType.PAYMENTS_YOOKASSA_GET_STATUS: ("external_payment_id", "timeout_s"),
        EffectActionType.CRM_WRITE_RECORD: ("endpoint", "headers", "data", "timeout_s"),
        EffectActionType.ADS_UPDATE_BUDGET: ("endpoint", "headers", "data", "timeout_s"),
        EffectActionType.WEBSITE_PUBLISH_PAGE: ("endpoint", "headers", "data", "timeout_s"),
        EffectActionType.WEATHER_OPEN_METEO_CURRENT: ("city",),
        EffectActionType.LLM_MARKETING_COMPLETE: ("provider", "system", "user", "model"),
    }


def normalize_effect_payload(action_type: str | EffectActionType, payload: Any) -> dict[str, Any]:
    key = require_effect_action_type(action_type)
    data = _require_mapping(key, payload)
    if key is EffectActionType.TELEGRAM_SEND_MESSAGE:
        return {
            "chat_id": _require_text(key, data, "chat_id"),
            "text": _require_text(key, data, "text"),
            "reply_markup": _optional_dict(data, "reply_markup"),
            "priority": data.get("priority", "normal"),
            "critical": _bool(data, "critical", default=True),
            "timeout_s": _int(data, "timeout_s", default=30, minimum=1, maximum=300),
        }
    if key is EffectActionType.TELEGRAM_SEND_AUDIO:
        return {
            "chat_id": _require_text(key, data, "chat_id"),
            "audio_url": _require_text(key, data, "audio_url"),
            "caption": _optional_text(data, "caption"),
            "priority": data.get("priority", "normal"),
            "critical": _bool(data, "critical", default=True),
            "timeout_s": _int(data, "timeout_s", default=30, minimum=1, maximum=300),
        }
    if key is EffectActionType.TELEGRAM_ANSWER_CALLBACK:
        return {
            "callback_query_id": _require_text(key, data, "callback_query_id"),
            "text": _optional_text(data, "text"),
            "show_alert": _bool(data, "show_alert", default=False),
        }
    if key is EffectActionType.TELEGRAM_SEND_CHAT_ACTION:
        return {
            "chat_id": _require_text(key, data, "chat_id"),
            "action": _require_text(key, data, "action"),
        }
    if key is EffectActionType.TELEGRAM_SELF_CHECK:
        return {"token": _require_text(key, data, "token")}
    if key is EffectActionType.TELEGRAM_POLL_UPDATES:
        return {
            "offset": _optional_int(data, "offset"),
            "timeout_s": _int(data, "timeout_s", default=30, minimum=0, maximum=300),
            "limit": _int(data, "limit", default=100, minimum=1, maximum=100),
            "startup_checked": _bool(data, "startup_checked", default=False),
            "webhook_cleared": _bool(data, "webhook_cleared", default=False),
        }
    if key is EffectActionType.PAYMENTS_YOOKASSA_CREATE:
        return {
            "amount_rub": str(_decimal_amount(key, data, "amount_rub")),
            "description": _require_text(key, data, "description"),
            "customer_id": _optional_text(data, "customer_id"),
            "idempotence_key": _optional_text(data, "idempotence_key"),
            "metadata": _optional_dict(data, "metadata") or {},
            "timeout_s": _int(data, "timeout_s", default=30, minimum=1, maximum=300),
        }
    if key is EffectActionType.PAYMENTS_YOOKASSA_GET_STATUS:
        return {
            "external_payment_id": _require_text(key, data, "external_payment_id"),
            "timeout_s": _int(data, "timeout_s", default=30, minimum=1, maximum=300),
        }
    if key in {
        EffectActionType.CRM_WRITE_RECORD,
        EffectActionType.ADS_UPDATE_BUDGET,
        EffectActionType.WEBSITE_PUBLISH_PAGE,
    }:
        return _generic_endpoint_contract(key, data)
    if key is EffectActionType.WEATHER_OPEN_METEO_CURRENT:
        city = _optional_text(data, "city") or "Amsterdam"
        return {"city": city}
    if key is EffectActionType.LLM_MARKETING_COMPLETE:
        return {
            "provider": _require_text(key, data, "provider"),
            "system": _require_text(key, data, "system"),
            "user": _require_text(key, data, "user"),
            "model": _require_text(key, data, "model"),
        }
    return data
