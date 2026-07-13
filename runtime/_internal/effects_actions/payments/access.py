from __future__ import annotations

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

    if isinstance(track_event_type, str) and track_event_type.strip():
        effects.event_log.emit(
            event_type=str(track_event_type),
            source="runtime",
            user_id=user,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload=dict(track_payload or {}),
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
                reply_markup=notify_reply_markup if isinstance(notify_reply_markup, dict) else None,
                priority="high",
            )
        except Exception as exc:
            notification = {"ok": False, "error": exc.__class__.__name__}

    return {
        "ok": True,
        "status": "verified",
        "entitlement": payload,
        "notification": notification,
        "router_evidence": evidence,
    }
