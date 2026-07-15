from __future__ import annotations

import time
import uuid
from collections.abc import Mapping
from typing import Any

from runtime._internal.effects_tenant import assert_event_log_tenant
from runtime.security.runtime_asserts import assert_called_from_executor

_GIFT_REDEMPTION_NAMESPACE = uuid.UUID("f945d879-640a-497a-a4d0-655548159a91")
_ENTITLEMENT_NAMESPACE = uuid.UUID("42f21c2b-6fa7-46ad-87fb-c818170eb744")


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
    event_id: str = "",
) -> dict[str, Any]:
    suffix = grant_key or str(decision_id)
    external_ref = str(event_id or "").strip() or (
        f"entitlement:{tenant_id}:{product_id}:{user_id}:{suffix}"
    )
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
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    store = getattr(effects.event_log, "_store", None)
    if store is None or not hasattr(store, "iter_events"):
        return None, None

    created: dict[str, Any] | None = None
    redeemed: dict[str, Any] | None = None
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
            redeemed = {
                **dict(event),
                "payload": dict(payload),
            }
    return created, redeemed


def _gift_redemption_event_id(*, tenant_id: str, token: str) -> str:
    return str(
        uuid.uuid5(
            _GIFT_REDEMPTION_NAMESPACE,
            f"gift-redemption:{tenant_id}:{token}",
        )
    )


def _entitlement_event_id(
    *,
    tenant_id: str,
    product_id: str,
    user_id: str,
    grant_key: str,
    decision_id: str,
) -> str:
    suffix = str(grant_key or decision_id).strip()
    return str(
        uuid.uuid5(
            _ENTITLEMENT_NAMESPACE,
            f"entitlement:{tenant_id}:{product_id}:{user_id}:{suffix}",
        )
    )


def _event_by_id(
    effects: Any,
    *,
    tenant_id: str,
    event_id: str,
) -> dict[str, Any] | None:
    store = getattr(effects.event_log, "_store", None)
    if store is None or not hasattr(store, "iter_events"):
        return None
    for event in store.iter_events(
        tenant_id=str(tenant_id),
        start_ms=0,
        end_ms=None,
    ):
        if (
            isinstance(event, dict)
            and str(event.get("event_id") or "") == str(event_id)
        ):
            return dict(event)
    return None


def _same_gift_claim(
    event: Mapping[str, Any] | None,
    *,
    user_id: str,
    product_id: str,
) -> bool:
    if not isinstance(event, Mapping):
        return False
    payload = event.get("payload") or {}
    if not isinstance(payload, Mapping):
        return False
    return (
        str(payload.get("redeemed_by") or "") == str(user_id)
        and str(payload.get("product_id") or "") == str(product_id)
    )


def _same_entitlement(
    event: Mapping[str, Any] | None,
    *,
    tenant_id: str,
    product_id: str,
    user_id: str,
    grant_key: str,
    full_access: bool,
) -> bool:
    if not isinstance(event, Mapping):
        return False
    payload = event.get("payload") or {}
    if not isinstance(payload, Mapping):
        return False
    return (
        str(event.get("event_type") or "") == "entitlement_granted"
        and str(event.get("user_id") or "") == str(user_id)
        and str(payload.get("tenant_id") or "") == str(tenant_id)
        and str(payload.get("product_id") or "") == str(product_id)
        and str(payload.get("grant_key") or "") == str(grant_key)
        and bool(payload.get("full_access")) == bool(full_access)
    )


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
    channel: str,
    channel_policy: dict[str, Any] | None,
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
            channel=str(channel),
            channel_policy=(
                dict(channel_policy)
                if isinstance(channel_policy, dict)
                else None
            ),
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
    product_id: str,
    user_id: str,
    track_payload: dict | None,
    channel: str,
    channel_policy: dict[str, Any] | None,
) -> dict[str, Any]:
    token = str((track_payload or {}).get("token") or "").strip()
    created, redeemed_event = _gift_events(
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
            channel=channel,
            channel_policy=channel_policy,
        )

    created_product = str(created.get("product_id") or "").strip()
    if created_product and created_product != str(product_id):
        return _gift_failure(
            effects,
            decision_id=decision_id,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            token=token,
            reason="product_mismatch",
            text="🎁 Этот подарок предназначен для другого продукта.",
            channel=channel,
            channel_policy=channel_policy,
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
            channel=channel,
            channel_policy=channel_policy,
        )
    if redeemed_event is not None:
        if _same_gift_claim(
            redeemed_event,
            user_id=user_id,
            product_id=product_id,
        ):
            return {
                "ok": True,
                "token": token,
                "event": dict(redeemed_event),
                "replayed": True,
            }
        return _gift_failure(
            effects,
            decision_id=decision_id,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            token=token,
            reason="already_redeemed",
            text="🎁 Этот подарок уже активирован.",
            channel=channel,
            channel_policy=channel_policy,
        )

    event_id = _gift_redemption_event_id(
        tenant_id=tenant_id,
        token=token,
    )
    try:
        event = effects.event_log.emit(
            event_id=event_id,
            event_type="gift_redeemed",
            source="gift",
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={
                "tenant_id": str(tenant_id),
                "product_id": str(product_id),
                "token": token,
                "created_by": str(created.get("created_by") or ""),
                "redeemed_by": str(user_id),
            },
        )
    except Exception:
        _created, raced = _gift_events(
            effects,
            tenant_id=tenant_id,
            token=token,
        )
        if _same_gift_claim(
            raced,
            user_id=user_id,
            product_id=product_id,
        ):
            return {
                "ok": True,
                "token": token,
                "event": dict(raced or {}),
                "replayed": True,
            }
        if raced is not None:
            return _gift_failure(
                effects,
                decision_id=decision_id,
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                user_id=user_id,
                token=token,
                reason="already_redeemed",
                text="🎁 Этот подарок уже активирован.",
                channel=channel,
                channel_policy=channel_policy,
            )
        raise
    return {
        "ok": True,
        "token": token,
        "event": event,
        "event_id": event_id,
        "replayed": False,
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
    channel: str = "telegram",
    channel_policy: dict[str, Any] | None = None,
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
            product_id=product,
            user_id=user,
            track_payload=track_payload,
            channel=str(channel),
            channel_policy=channel_policy,
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
    entitlement_event_id = _entitlement_event_id(
        tenant_id=tenant,
        product_id=product,
        user_id=user,
        grant_key=key,
        decision_id=str(decision_id),
    )
    existing_entitlement = _event_by_id(
        effects,
        tenant_id=tenant,
        event_id=entitlement_event_id,
    )
    entitlement_replayed = existing_entitlement is not None
    if existing_entitlement is not None:
        if not _same_entitlement(
            existing_entitlement,
            tenant_id=tenant,
            product_id=product,
            user_id=user,
            grant_key=key,
            full_access=bool(full_access),
        ):
            raise RuntimeError("ENTITLEMENT_EVENT_ID_CONFLICT")
    else:
        try:
            effects.event_log.emit(
                event_id=entitlement_event_id,
                event_type="entitlement_granted",
                source="entitlements",
                user_id=user,
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                payload=payload,
            )
        except Exception:
            existing_entitlement = _event_by_id(
                effects,
                tenant_id=tenant,
                event_id=entitlement_event_id,
            )
            if not _same_entitlement(
                existing_entitlement,
                tenant_id=tenant,
                product_id=product,
                user_id=user,
                grant_key=key,
                full_access=bool(full_access),
            ):
                raise
            entitlement_replayed = True
    evidence = _entitlement_evidence(
        decision_id=str(decision_id),
        tenant_id=tenant,
        product_id=product,
        user_id=user,
        grant_key=key,
        full_access=bool(full_access),
        event_id=entitlement_event_id,
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
                channel=str(channel),
                channel_policy=(
                    dict(channel_policy)
                    if isinstance(channel_policy, dict)
                    else None
                ),
            )
        except Exception as exc:
            notification = {"ok": False, "error": exc.__class__.__name__}

    return {
        "ok": True,
        "status": "verified",
        "entitlement": payload,
        "entitlement_event_id": entitlement_event_id,
        "entitlement_replayed": entitlement_replayed,
        "gift": gift_result,
        "notification": notification,
        "router_evidence": evidence,
    }
