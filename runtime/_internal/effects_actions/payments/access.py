from __future__ import annotations

from typing import Any

from runtime.observability.error_handling import swallow


def grant_access_effect(
    effects: Any,
    *,
    decision_id: str,
    correlation_id: str,
    user_id: str,
    tenant_id: str | None = None,
    product_id: str | None = None,
    grant_key: str | None = None,
    full_access: bool = True,
    notify_text: str | None = None,
    notify_reply_markup: dict | None = None,
    track_event_type: str | None = None,
    track_payload: dict | None = None,
) -> bool:
    if str(track_event_type or "") == "gift_redeemed":
        try:
            token = str((track_payload or {}).get("token") or "").strip()
        except Exception:
            token = ""

        store = getattr(effects.event_log, "_store", None)
        created = None
        redeemed = False
        expires_ms = 0
        if token and store is not None and hasattr(store, "iter_events"):
            try:
                for ev in store.iter_events(tenant_id=str(getattr(effects.event_log, '_tenant_id', 'default')), start_ms=0, end_ms=None):
                    et = str(ev.get("event_type") or "")
                    payload = ev.get("payload") or {}
                    if et == "gift_token_created" and str(payload.get("token") or "") == token:
                        created = payload
                        try:
                            expires_ms = int(payload.get("expires_ms") or 0)
                        except Exception:
                            expires_ms = 0
                    if et == "gift_redeemed" and str(payload.get("token") or "") == token:
                        redeemed = True
            except Exception:
                swallow(__name__, 'runtime/_internal/_effects_impl.py')

        import time
        now_ms = int(time.time() * 1000)
        if (not token) or (created is None):
            try:
                effects.send_message(
                    decision_id=str(decision_id),
                    correlation_id=str(correlation_id),
                    user_id=str(user_id),
                    text="🎁 Подарок не найден или ссылка неверна.",
                    reply_markup=None,
                    priority="high",
                )
            except Exception:
                swallow(__name__, 'runtime/_internal/_effects_impl.py')
            try:
                effects.event_log.emit(
                    event_type="gift_redeem_failed",
                    source="gift",
                    user_id=str(user_id),
                    decision_id=str(decision_id),
                    correlation_id=str(correlation_id),
                    payload={"token": token, "reason": "not_found"},
                )
            except Exception:
                swallow(__name__, 'runtime/_internal/_effects_impl.py')
            return True
        if expires_ms and now_ms > int(expires_ms):
            try:
                effects.send_message(
                    decision_id=str(decision_id),
                    correlation_id=str(correlation_id),
                    user_id=str(user_id),
                    text="🎁 Срок действия подарка истёк.",
                    reply_markup=None,
                    priority="high",
                )
            except Exception:
                swallow(__name__, 'runtime/_internal/_effects_impl.py')
            try:
                effects.event_log.emit(
                    event_type="gift_redeem_failed",
                    source="gift",
                    user_id=str(user_id),
                    decision_id=str(decision_id),
                    correlation_id=str(correlation_id),
                    payload={"token": token, "reason": "expired"},
                )
            except Exception:
                swallow(__name__, 'runtime/_internal/_effects_impl.py')
            return True
        if redeemed:
            try:
                effects.send_message(
                    decision_id=str(decision_id),
                    correlation_id=str(correlation_id),
                    user_id=str(user_id),
                    text="🎁 Этот подарок уже активирован.",
                    reply_markup=None,
                    priority="high",
                )
            except Exception:
                swallow(__name__, 'runtime/_internal/_effects_impl.py')
            try:
                effects.event_log.emit(
                    event_type="gift_redeem_failed",
                    source="gift",
                    user_id=str(user_id),
                    decision_id=str(decision_id),
                    correlation_id=str(correlation_id),
                    payload={"token": token, "reason": "already_redeemed"},
                )
            except Exception:
                swallow(__name__, 'runtime/_internal/_effects_impl.py')
            return True

        try:
            effects.event_log.emit(
                event_type="gift_redeemed",
                source="gift",
                user_id=str(user_id),
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                payload={"token": token, "created_by": str((created or {}).get("created_by") or ""), "redeemed_by": str(user_id)},
            )
        except Exception:
            swallow(__name__, 'runtime/_internal/_effects_impl.py')

    if isinstance(track_event_type, str) and track_event_type.strip() and str(track_event_type) != "gift_redeemed":
        try:
            effects.event_log.emit(
                event_type=str(track_event_type),
                source="runtime",
                user_id=str(user_id),
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                payload=dict(track_payload or {}),
            )
        except Exception:
            swallow(__name__, 'runtime/_internal/_effects_impl.py')

    effects.event_log.emit(
        event_type="access_granted",
        source="entitlements",
        user_id=str(user_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload={"full_access": bool(full_access), "tenant_id": str(tenant_id or ""), "product_id": str(product_id or ""), "grant_key": str(grant_key or "")},
    )
    try:
        if bool(full_access):
            text = str(notify_text) if isinstance(notify_text, str) and notify_text.strip() else "Полный доступ активирован ✅"
            effects.send_message(
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                user_id=str(user_id),
                text=text,
                reply_markup=notify_reply_markup if isinstance(notify_reply_markup, dict) else None,
                priority="high",
            )
    except Exception:
        swallow(__name__, 'runtime/_internal/_effects_impl.py')
    return True
