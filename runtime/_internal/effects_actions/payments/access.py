from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from runtime._internal.effects_tenant import assert_event_log_tenant
from runtime.security.runtime_asserts import assert_called_from_executor


def _required_scope(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError(f"{field.upper()}_REQUIRED")
    return text


def _entitlement_evidence(
    *,
    decision_id: str,
    tenant_id: str,
    product_id: str,
    user_id: str,
    grant_key: str,
    full_access: bool,
) -> dict[str, Any]:
    suffix = grant_key or str(decision_id)
    external_ref = f"entitlement:{tenant_id}:{product_id}:{user_id}:{suffix}"
    return {
        "source": "ledger",
        "verified": True,
        "status": "verified",
        "code": "entitlement_grant_recorded",
        "external_refs": [external_ref],
        "confidence": 1.0,
        "payload": {
            "tenant_id": str(tenant_id),
            "product_id": str(product_id),
            "user_id": str(user_id),
            "grant_key": str(grant_key),
            "full_access": bool(full_access),
        },
    }


def _gift_events(
    effects: Any,
    *,
    tenant_id: str,
    token: str,
) -> tuple[dict[str, Any] | None, bool]:
    store = getattr(effects.event_log, "_store", None)
    if store is None or not hasattr(store, "iter_events"):
        return None, False

    created: dict[str, Any] | None = None
    redeemed = False
    events = store.iter_events(
        tenant_id=str(tenant_id),
        start_ms=0,
        end_ms=None,
    )
    for event in events:
        event_type = str(event.get("event_type") or "")
        payload = event.get("payload") or {}
        if not isinstance(payload, Mapping):
            continue
        if (
            event_type == "gift_token_created"
            and str(payload.get("token") or "") == token
        ):
            created = dict(payload)
        elif (
            event_type == "gift_redeemed"
            and str(payload.get("token") or "") == token
        ):
            redeemed = True
    return created, redeemed


def _gift_failure(
    effects: Any,
    *,
    decision_id: str,
    correlation_id: str,
    tenant_id: str,
    user_id: str,
    token: str,
    reason: str,
    text: str,
) -> dict[str, Any]:
    event = effects.event_log.emit(
        event_type="gift_redeem_failed",
        source="gift",
        user_id=str(user_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload={
            "tenant_id": str(tenant_id),
            "token": str(token),
            "reason": str(reason),
        },
    )
    try:
        notification = effects.send_message(
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            text=str(text),
            reply_markup=None,
            priority="high",
        )
    except Exception as exc:
        notification = {"ok": False, "error": exc.__class__.__name__}
    return {
        "ok": False,
        "status": "blocked",
        "reason": str(reason),
        "gift_failure_event": event,
        "notification": notification,
        "router_evidence": None,
    }


def _validate_and_record_gift(
    effects: Any,
    *,
    decision_id: str,
    correlation_id: str,
    tenant_id: str,
    user_id: str,
    track_payload: dict | None,
) -> dict[str, Any]:
    token = str((track_payload or {}).get("token") or "").strip()
    created, redeemed = _gift_events(
        effects,
        tenant_id=tenant_id,
        token=token,
    )
    if not token or created is None:
        return _gift_failure(
            effects,
            decision_id=decision_id,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            token=token,
            reason="not_found",
            text="🎁 Подарок не найден или ссылка неверна.",
        )

    try:
        expires_ms = int(created.get("expires_ms") or 0)
    except (TypeError, ValueError):
        expires_ms = 0
    if expires_ms and int(time.time() * 1000) > expires_ms:
        return _gift_failure(
            effects,
            decision_id=decision_id,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            token=token,
            reason="expired",
            text="🎁 Срок действия подарка истёк.",
        )
    if redeemed:
        return _gift_failure(
            effects,
            decision_id=decision_id,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            token=token,
            reason="already_redeemed",
            text="🎁 Этот подарок уже активирован.",
        )

    event = effects.event_log.emit(
        event_type="gift_redeemed",
        source="gift",
        user_id=str(user_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload={
            "tenant_id": str(tenant_id),
            "token": token,
            "created_by": str(created.get("created_by") or ""),
            "redeemed_by": str(user_id),
        },
    )
    return {
        "ok": True,
        "token": token,
        "event": event,
    }


def grant_access_effect(
    effects: Any,
    *,
    decision_id: str,
    correlation_id: str,
    user_id: str,
    tenant_id: str,
    product_id: str,
    grant_key: str | None = None,
    full_access: bool = True,
    notify_text: str | None = None,
    notify_reply_markup: dict | None = None,
    track_event_type: str | None = None,
    track_payload: dict | None = None,
) -> dict[str, Any]:
    """Grant one tenant-scoped product entitlement and return durable proof."""

    assert_called_from_executor()
    tenant = _required_scope(tenant_id, field="tenant_id")
    product = _required_scope(product_id, field="product_id")
    user = _required_scope(user_id, field="user_id")
    key = str(grant_key or "").strip()
    assert_event_log_tenant(
        effects.event_log,
        tenant_id=tenant,
        operation="grant_access",
    )

    gift_result: dict[str, Any] | None = None
    if str(track_event_type or "").strip() == "gift_redeemed":
        gift_result = _validate_and_record_gift(
            effects,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            tenant_id=tenant,
            user_id=user,
            track_payload=track_payload,
        )
        if not gift_result.get("ok"):
            return gift_result
        key = key or str(gift_result.get("token") or "")
    elif isinstance(track_event_type, str) and track_event_type.strip():
        effects.event_log.emit(
            event_type=str(track_event_type),
            source="runtime",
            user_id=user,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={
                **dict(track_payload or {}),
                "tenant_id": tenant,
            },
        )

    payload = {
        "full_access": bool(full_access),
        "tenant_id": tenant,
        "product_id": product,
        "grant_key": key,
    }
    effects.event_log.emit(
        event_type="entitlement_granted",
        source="entitlements",
        user_id=user,
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload=payload,
    )
    evidence = _entitlement_evidence(
        decision_id=str(decision_id),
        tenant_id=tenant,
        product_id=product,
        user_id=user,
        grant_key=key,
        full_access=bool(full_access),
    )

    notification: Any = None
    if bool(full_access):
        text = (
            str(notify_text)
            if isinstance(notify_text, str) and notify_text.strip()
            else "Доступ активирован ✅"
        )
        try:
            notification = effects.send_message(
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                tenant_id=tenant,
                user_id=user,
                text=text,
                reply_markup=(
                    notify_reply_markup
                    if isinstance(notify_reply_markup, dict)
                    else None
                ),
                priority="high",
            )
        except Exception as exc:
            notification = {"ok": False, "error": exc.__class__.__name__}

    return {
        "ok": True,
        "status": "verified",
        "entitlement": payload,
        "gift": gift_result,
        "notification": notification,
        "router_evidence": evidence,
    }
