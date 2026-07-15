from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from runtime._internal.effects_actions.payments.reconciliation_ownership import (
    assert_payment_metadata_tenant,
    resolve_payment_user,
)
from runtime._internal.effects_actions.payments.reconciliation_support import (
    FAILED_STATUSES,
    SUCCESS_STATUSES,
    event_already_processed,
    mark_ledger_terminal,
    resolve_created_payment_context,
    try_mark_terminal_outbox,
)
from runtime._internal.effects_tenant import assert_event_log_tenant
from runtime.security.runtime_asserts import assert_called_from_executor

_PAYMENT_EVENT_NAMESPACE = uuid.UUID("cb6838ad-0545-4d2e-8c8e-253a6fab1b48")


def _terminal_event_id(*, event_type: str, external_id: str, original_decision_id: str) -> str:
    key = f"businesaios:payments:{event_type}:{original_decision_id}:{external_id}"
    return str(uuid.uuid5(_PAYMENT_EVENT_NAMESPACE, key))


def _event_id_exists(*, effects: Any, event_id: str) -> bool:
    try:
        return any(
            str(event.get("event_id") or "") == str(event_id)
            for event in effects.event_log.iter_events()
        )
    except Exception:
        return False


def _emit_terminal_event_once(
    effects: Any,
    *,
    event_type: str,
    source: str,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    original_decision_id: str,
    external_id: str,
    payload: dict[str, Any],
) -> str:
    event_id = _terminal_event_id(
        event_type=event_type,
        external_id=str(external_id),
        original_decision_id=str(original_decision_id),
    )
    if _event_id_exists(effects=effects, event_id=event_id):
        return event_id
    try:
        effects.event_log.emit(
            event_type=str(event_type),
            source=str(source),
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload=dict(payload),
            event_id=event_id,
        )
    except Exception:
        if not _event_id_exists(effects=effects, event_id=event_id):
            raise
    return event_id


def _metadata(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: value[key]
        for key in ("tenant_id", "product_id", "order_id")
        if str(value.get(key) or "").strip()
    }


def _emit_payment_captured(
    effects: Any,
    *,
    original_decision_id: str,
    original_correlation_id: str,
    reconciliation_decision_id: str,
    reconciliation_correlation_id: str,
    user_id: str,
    external_id: str,
    status: str,
    business_metadata: dict[str, Any] | None = None,
) -> str:
    metadata = _metadata(business_metadata)
    return _emit_terminal_event_once(
        effects,
        event_type="payment_captured",
        source="payments",
        user_id=str(user_id),
        decision_id=str(original_decision_id or reconciliation_decision_id),
        correlation_id=str(original_correlation_id or reconciliation_correlation_id),
        original_decision_id=str(original_decision_id),
        external_id=str(external_id),
        payload={
            "external_id": str(external_id),
            "status": str(status),
            "reconciled_by_decision_id": str(reconciliation_decision_id),
            "reconciliation_correlation_id": str(reconciliation_correlation_id),
            "metadata": metadata,
        },
    )


def _emit_payment_status_event(
    effects: Any,
    *,
    event_type: str,
    original_decision_id: str,
    reconciliation_decision_id: str,
    reconciliation_correlation_id: str,
    user_id: str,
    external_id: str,
    status: str,
    business_metadata: dict[str, Any] | None = None,
) -> str:
    return _emit_terminal_event_once(
        effects,
        event_type=str(event_type),
        source="payments",
        user_id=str(user_id),
        decision_id=str(reconciliation_decision_id),
        correlation_id=str(reconciliation_correlation_id),
        original_decision_id=str(original_decision_id),
        external_id=str(external_id),
        payload={
            "external_id": str(external_id),
            "status": str(status),
            "metadata": _metadata(business_metadata),
        },
    )


def _record_success(
    effects: Any,
    *,
    original_decision_id: str,
    original_correlation_id: str,
    reconciliation_decision_id: str,
    reconciliation_correlation_id: str,
    user_id: str,
    external_id: str,
    status: str,
    business_metadata: dict[str, Any] | None = None,
    notification_id: str | None = None,
    event: str | None = None,
) -> None:
    _emit_payment_status_event(
        effects,
        event_type="payment_succeeded",
        original_decision_id=str(original_decision_id),
        reconciliation_decision_id=str(reconciliation_decision_id),
        reconciliation_correlation_id=str(reconciliation_correlation_id),
        user_id=str(user_id),
        external_id=str(external_id),
        status=str(status),
        business_metadata=business_metadata,
    )
    mark_ledger_terminal(
        effects=effects,
        envelope_id=str(original_decision_id),
        terminal_status="succeeded",
    )
    _emit_payment_captured(
        effects,
        original_decision_id=str(original_decision_id),
        original_correlation_id=str(original_correlation_id),
        reconciliation_decision_id=str(reconciliation_decision_id),
        reconciliation_correlation_id=str(reconciliation_correlation_id),
        user_id=str(user_id),
        external_id=str(external_id),
        status=str(status),
        business_metadata=business_metadata,
    )
    try_mark_terminal_outbox(
        effects=effects,
        external_id=str(external_id),
        terminal_status="succeeded",
        notification_id=notification_id,
        event=event or "payment_captured",
    )


def _record_failure(
    effects: Any,
    *,
    original_decision_id: str,
    reconciliation_decision_id: str,
    reconciliation_correlation_id: str,
    user_id: str,
    external_id: str,
    status: str,
    business_metadata: dict[str, Any] | None = None,
    notification_id: str | None = None,
    event: str | None = None,
) -> None:
    mark_ledger_terminal(
        effects=effects,
        envelope_id=str(original_decision_id),
        terminal_status="failed",
    )
    _emit_payment_status_event(
        effects,
        event_type="payment_failed",
        original_decision_id=str(original_decision_id),
        reconciliation_decision_id=str(reconciliation_decision_id),
        reconciliation_correlation_id=str(reconciliation_correlation_id),
        user_id=str(user_id),
        external_id=str(external_id),
        status=str(status),
        business_metadata=business_metadata,
    )
    try_mark_terminal_outbox(
        effects=effects,
        external_id=str(external_id),
        terminal_status="failed",
        notification_id=notification_id,
        event=event or "payment_failed",
    )


def _created_payment_context(
    effects: Any,
    *,
    tenant_id: str,
    external_id: str,
    user_id_hint: str | None = None,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    context = resolve_created_payment_context(
        effects=effects,
        external_id=str(external_id),
    )
    if not str(context.get("envelope_id") or "").strip():
        raise RuntimeError(f"PAYMENT_CONTEXT_NOT_FOUND:{external_id}")
    metadata = assert_payment_metadata_tenant(
        _metadata(context.get("metadata")),
        tenant_id=str(tenant_id),
        external_id=str(external_id),
    )
    user_id = resolve_payment_user(
        context,
        user_id_hint=user_id_hint,
        external_id=str(external_id),
    )
    return context, user_id, metadata


def reconcile_payments_effect(
    effects: Any,
    *,
    decision_id: str,
    correlation_id: str,
    tenant_id: str,
    window_min: int = 30,
) -> dict | bool:
    assert_called_from_executor()
    tenant = assert_event_log_tenant(
        effects.event_log,
        tenant_id=str(tenant_id),
        operation="reconcile_payments",
    )
    if effects.ledger is None:
        raise RuntimeError("PAYMENT_LEDGER_REQUIRED")

    try:
        now = datetime.now(UTC)
        window_start = now - timedelta(minutes=int(window_min))
        start_ms = int(window_start.timestamp() * 1000)
        end_ms = int(now.timestamp() * 1000)
        processed_any = 0
        skipped_already = 0
        for ev in effects.event_log.iter_events():
            try:
                ts = int(ev.get("timestamp_ms") or 0)
            except Exception:
                ts = 0
            if (ev.get("event_type") or ev.get("type")) != "payment_created":
                continue
            if ts < start_ms or ts >= end_ms:
                continue
            payload = ev.get("payload") or {}
            ext_id = str(payload.get("external_id") or "").strip()
            if not ext_id:
                continue
            context, uid, business_metadata = _created_payment_context(
                effects,
                tenant_id=tenant,
                external_id=ext_id,
            )
            if event_already_processed(effects=effects, external_id=ext_id):
                skipped_already += 1
                continue
            status = str(
                effects._yookassa_get_payment_status(external_payment_id=ext_id)
            ).lower()
            envelope_id = str(context.get("envelope_id") or "")
            original_correlation_id = str(context.get("correlation_id") or "")
            if status in SUCCESS_STATUSES:
                _record_success(
                    effects,
                    original_decision_id=envelope_id,
                    original_correlation_id=original_correlation_id,
                    reconciliation_decision_id=str(decision_id),
                    reconciliation_correlation_id=str(correlation_id),
                    user_id=uid,
                    external_id=ext_id,
                    status=status,
                    business_metadata=business_metadata,
                )
                processed_any += 1
            elif status in FAILED_STATUSES:
                _record_failure(
                    effects,
                    original_decision_id=envelope_id,
                    reconciliation_decision_id=str(decision_id),
                    reconciliation_correlation_id=str(correlation_id),
                    user_id=uid,
                    external_id=ext_id,
                    status=status,
                    business_metadata=business_metadata,
                )
                processed_any += 1

        effects.event_log.emit(
            event_type="payments_reconciled",
            source="payments",
            user_id="system",
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={
                "tenant_id": tenant,
                "window_min": int(window_min),
                "processed": int(processed_any),
                "skipped_already": int(skipped_already),
            },
        )
        if processed_any == 0 and skipped_already > 0:
            return {
                "ok": True,
                "status": "already_checked",
                "tenant_id": tenant,
            }
        return {
            "ok": True,
            "status": "checked",
            "tenant_id": tenant,
            "processed": int(processed_any),
        }
    except RuntimeError:
        raise
    except Exception as exc:
        effects.event_log.emit(
            event_type="payments_reconcile_failed",
            source="payments",
            user_id="system",
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={"tenant_id": tenant, "error": str(exc)},
        )
        return False


def reconcile_payment_effect(
    effects: Any,
    *,
    decision_id: str,
    correlation_id: str,
    tenant_id: str,
    external_payment_id: str,
    notification_id: str | None = None,
    event: str | None = None,
    user_id_hint: str | None = None,
) -> dict[str, Any] | bool:
    assert_called_from_executor()
    tenant = assert_event_log_tenant(
        effects.event_log,
        tenant_id=str(tenant_id),
        operation="reconcile_payment",
    )
    ext_id = str(external_payment_id or "").strip()
    if not ext_id:
        raise RuntimeError("EXTERNAL_PAYMENT_ID_REQUIRED")

    context, uid, business_metadata = _created_payment_context(
        effects,
        tenant_id=tenant,
        external_id=ext_id,
        user_id_hint=user_id_hint,
    )
    if event_already_processed(effects=effects, external_id=ext_id):
        return True

    try:
        status = str(
            effects._yookassa_get_payment_status(external_payment_id=ext_id)
        ).lower()
    except Exception as exc:
        effects.event_log.emit(
            event_type="payment_checked",
            source="payments",
            user_id=uid,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={
                "tenant_id": tenant,
                "external_id": ext_id,
                "status": "error",
                "error": repr(exc),
                "notification_id": notification_id,
                "event": event,
                "user_id_hint": str(user_id_hint) if user_id_hint else None,
                "metadata": business_metadata,
            },
        )
        raise

    effects.event_log.emit(
        event_type="payment_checked",
        source="payments",
        user_id=uid,
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload={
            "tenant_id": tenant,
            "external_id": ext_id,
            "status": status,
            "notification_id": notification_id,
            "event": event,
            "user_id_hint": str(user_id_hint) if user_id_hint else None,
            "metadata": business_metadata,
        },
    )

    terminal = (
        "succeeded"
        if status in SUCCESS_STATUSES
        else ("failed" if status in FAILED_STATUSES else "pending")
    )
    if terminal == "pending":
        return True
    if terminal == "succeeded":
        _record_success(
            effects,
            original_decision_id=str(context.get("envelope_id") or ""),
            original_correlation_id=str(context.get("correlation_id") or ""),
            reconciliation_decision_id=str(decision_id),
            reconciliation_correlation_id=str(correlation_id),
            user_id=uid,
            external_id=ext_id,
            status=status,
            business_metadata=business_metadata,
            notification_id=notification_id,
            event=event,
        )
    else:
        _record_failure(
            effects,
            original_decision_id=str(context.get("envelope_id") or ""),
            reconciliation_decision_id=str(decision_id),
            reconciliation_correlation_id=str(correlation_id),
            user_id=uid,
            external_id=ext_id,
            status=status,
            business_metadata=business_metadata,
            notification_id=notification_id,
            event=event,
        )
    return {
        "ok": True,
        "status": status,
        "tenant_id": tenant,
        "metadata": business_metadata,
    }


__all__ = [
    "_emit_payment_captured",
    "_record_failure",
    "_record_success",
    "_terminal_event_id",
    "reconcile_payment_effect",
    "reconcile_payments_effect",
]
