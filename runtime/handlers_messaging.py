from __future__ import annotations

"""Canonical messaging handlers.

Handlers are execution-only.
No channel choice policy.
No fallback ranking.
No hidden second brain.
"""

import logging

from runtime.messaging.channel_normalizer import normalize_channel
from runtime.observability.error_handling import warning_throttled
from runtime.tenancy import UNKNOWN_TENANT_ID, normalize_tenant_id

log = logging.getLogger(__name__)


def _message_priority_fields(payload: dict) -> tuple[str, bool]:
    kind = payload.get("kind")
    best_effort = bool(payload.get("best_effort", False))
    priority = payload.get("priority")
    critical = payload.get("critical")
    if kind == "marketing":
        if "best_effort" not in payload:
            best_effort = True
        if priority is None:
            priority = "low"
        if critical is None:
            critical = False
    if priority is None:
        priority = "normal"
    if critical is None:
        critical = not best_effort
    return str(priority), bool(critical)


def _resolve_tenant_id(payload: dict, env) -> str:
    track_payload = payload.get("track_payload") if isinstance(payload.get("track_payload"), dict) else {}
    decision = getattr(env, "decision", None)
    for candidate in (
        payload.get("tenant_id"),
        track_payload.get("tenant_id"),
        getattr(decision, "tenant_id", None) if decision is not None else None,
        getattr(env, "tenant_id", None),
        getattr(env, "default_tenant_id", None),
    ):
        tenant_id = normalize_tenant_id(candidate)
        if tenant_id:
            return tenant_id
    return UNKNOWN_TENANT_ID


def _build_send_kwargs(payload: dict, env) -> dict:
    priority, critical = _message_priority_fields(payload)
    return {
        "decision_id": env.decision.decision_id,
        "correlation_id": env.decision.correlation_id,
        "tenant_id": _resolve_tenant_id(payload, env),
        "user_id": str(payload["user_id"]),
        "text": str(payload["text"]),
        "channel": normalize_channel(str(payload.get("channel") or "telegram")),
        "priority": priority,
        "critical": critical,
        "reply_markup": payload.get("reply_markup"),
        "callback_query_id": payload.get("callback_query_id"),
        "track_event_type": payload.get("track_event_type"),
        "track_payload": payload.get("track_payload"),
        "channel_policy": payload.get("channel_policy"),
    }


def handle_send_message(payload, effects, env):
    p = dict(payload or {})
    return effects.send_message(**_build_send_kwargs(p, env))


def handle_send_marketing_offer(payload, effects, env, *, composer):
    p = dict(payload or {})
    offer = p.get("offer") if isinstance(p.get("offer"), dict) else {}
    locale = str(p.get("locale") or "ru")
    tenant_id = _resolve_tenant_id(p, env)
    user_id = str(p.get("user_id") or "")
    features = p.get("features") if isinstance(p.get("features"), dict) else {}
    last_user_text = str(p.get("last_user_text") or "")
    channel = normalize_channel(str(p.get("channel") or "telegram"))

    text = None
    if composer is not None:
        try:
            from runtime.marketing import (
                MarketingLLMInputs,
                compose_marketing_fallback,
                compose_marketing_text_sync,
            )

            tp = p.get("track_payload") if isinstance(p.get("track_payload"), dict) else {}
            inp = MarketingLLMInputs(
                tenant_id=tenant_id,
                user_id=user_id,
                locale=locale,
                channel=channel,
                features=features,
                offer=offer,
                last_user_text=last_user_text,
                correlation_id=str(tp.get("correlation_id") or getattr(env, "correlation_id", "") or ""),
                message_id=str(tp.get("message_id") or ""),
                experiment=str(tp.get("experiment") or ""),
                variant=str(tp.get("variant") or tp.get("marketing_variant") or tp.get("offer_variant") or ""),
            )
            text = compose_marketing_text_sync(composer, inp)
            if not text:
                text = compose_marketing_fallback(offer=offer, locale=locale)
        except ImportError as exc:
            warning_throttled(log, 'runtime.marketing_offer.import_error', exc, throttle_ms=30_000)
            text = str(p.get("fallback_text") or "")
        except Exception as exc:
            warning_throttled(log, 'runtime.marketing_offer.compose_error', exc, throttle_ms=30_000)
            text = str(p.get("fallback_text") or "")

    return handle_send_message(
        {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "text": text,
            "channel": channel,
            "kind": "marketing",
            "priority": p.get("priority", "low"),
            "best_effort": bool(p.get("best_effort", True)),
            "critical": bool(p.get("critical", False)),
            "reply_markup": p.get("reply_markup"),
            "callback_query_id": p.get("callback_query_id"),
            "track_event_type": p.get("track_event_type"),
            "track_payload": p.get("track_payload"),
            "channel_policy": p.get("channel_policy"),
        },
        effects,
        env,
    )


def handle_one_click_value(payload, effects, env, *, composer):
    p = dict(payload or {})
    p.setdefault("track_event_type", "one_click_value_shown")
    return handle_send_marketing_offer(p, effects, env, composer=composer)


def handle_noop(payload, effects, env):
    return None


def handle_poll_telegram_updates(payload, effects, env):
    p = dict(payload or {})
    return effects.poll_telegram_updates(
        offset=p.get("offset"),
        timeout_s=int(p.get("timeout_s", 30)),
        limit=int(p.get("limit", 50)),
    )


def handle_telegram_self_check(payload, effects, env):
    return effects.telegram_self_check(token=(payload or {}).get("token"))
