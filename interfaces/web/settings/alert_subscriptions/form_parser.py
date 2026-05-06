from __future__ import annotations

from runtime.messaging.channel_normalizer import normalize_channel
from runtime.messaging_policy_alert_subscriptions.subscription_level import normalize_min_level


def _parse_csv_list(value) -> tuple[str, ...]:
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        parts = value
    else:
        parts = []

    out: list[str] = []
    for item in parts:
        text = str(item or "").strip()
        if not text:
            continue
        out.append(text)
    return tuple(dict.fromkeys(out))


def _parse_subscription_item(value) -> dict | None:
    if not isinstance(value, dict):
        return None

    recipient_user_id = str(value.get("recipient_user_id") or "").strip()
    if not recipient_user_id:
        return None

    return {
        "recipient_user_id": recipient_user_id,
        "channel": normalize_channel(str(value.get("channel") or "telegram")),
        "min_level": normalize_min_level(str(value.get("min_level") or "warn")),
        "enabled": bool(value.get("enabled", True)),
        "code_filters": list(_parse_csv_list(value.get("code_filters") or ())),
        "user_scope": list(_parse_csv_list(value.get("user_scope") or ())),
    }


def parse_alert_subscriptions_form(payload) -> list[dict]:
    if isinstance(payload, dict):
        raw_items = payload.get("items") or ()
    elif isinstance(payload, (list, tuple)):
        raw_items = payload
    else:
        raw_items = ()

    out = []
    for item in raw_items:
        parsed = _parse_subscription_item(item)
        if parsed is not None:
            out.append(parsed)
    return out
