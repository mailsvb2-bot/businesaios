from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from runtime._internal.effects_actions.payments.reconciliation_support import (
    FAILED_STATUSES,
    SUCCESS_STATUSES,
    event_already_processed,
    mark_ledger_terminal,
    resolve_created_payment_context,
    try_mark_terminal_outbox,
)
from runtime.security.runtime_asserts import assert_called_from_executor

_PAYMENT_EVENT_NAMESPACE = uuid.UUID("cb6838ad-0545-4d2e-8c8e-253a6fab1b48")


def _terminal_event_id(*, event_type: str, external_id: str, original_decision_id: str) -> str:
    key = f"businesaios:payments:{event_type}:{original_decision_id}:{external_id}"
    return str(uuid.uuid5(_PAYMENT_EVENT_NAMESPACE, key))


def _event_id_exists(*, effects: Any, event_id: str) -> bool:
    try:
        return any(str(event.get("event_id") or "") == str(event_id) for event in effects.event_log.iter_events())
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
) -> str:
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
        payload={"external_id": str(external_id), "status": str(status)},
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
    )
    try_mark_terminal_outbox(
        effects=effects,
        external_id=str(external_id),
        terminal_status="failed",
        notification_id=notification_id,
        event=event or "payment_failed",
    )


def reconcile_payments_effect(
    effects: Any, *, decision_id: str, correlation_id: str, window_min: int = 30
) -> dict | bool:
    assert_called_from_executor()
    if effects.ledger is None:
        return True
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
            ext_id = payload.get("external_id")
            uid = ev.get("user_id")
            if not ext_id or not uid:
                continue
            if event_already_processed(effects=effects, external_id=str(ext_id)):
                skipped_already += 1
                continue
            status = str(effects._yookassa_get_payment_status(external_payment_id=str(ext_id))).lower()
            envelope_id = str(ev.get("decision_id") or ev.get("envelope_id") or "")
            original_correlation_id = str(ev.get("correlation_id") or "")
            if status in SUCCESS_STATUSES:
                _record_success(
                    effects,
                    original_decision_id=envelope_id,
                    original_correlation_id=original_correlation_id,
                    reconciliation_decision_id=str(decision_id),
                    reconciliation_correlation_id=str(correlation_id),
                    user_id=str(uid),
                    external_id=str(ext_id),
                    status=status,
                )
                processed_any += 1
            elif status in FAILED_STATUSES:
                _record_failure(
                    effects,
                    original_decision_id=envelope_id,
                    reconciliation_decision_id=str(decision_id),
                    reconciliation_correlation_id=str(correlation_id),
                    user_id=str(uid),
                    external_id=str(ext_id),
                    status=status,
                )
                processed_any += 1

        effects.event_log.emit(
            event_type="payments_reconciled",
            source="payments",
            user_id="system",
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={"window_min": int(window_min), "processed": int(processed_any), "skipped_already": int(skipped_already)},
        )
        if processed_any == 0 and skipped_already > 0:
            return {"ok": True, "status": "already_checked"}
        return {"ok": True, "status": "checked", "processed": int(processed_any)}
    except Exception as e:
        effects.event_log.emit(
            event_type="payments_reconcile_failed",
            source="payments",
            user_id="system",
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={"error": str(e)},
        )
        return False


def reconcile_payment_effect(
    effects: Any,
    *,
    decision_id: str,
    correlation_id: str,
    external_payment_id: str,
    notification_id: str | None = None,
    event: str | None = None,
    user_id_hint: str | None = None,
) -> bool:
    assert_called_from_executor()
    ext_id = str(external_payment_id or "").strip()
    if not ext_id:
        return True

    if event_already_processed(effects=effects, external_id=ext_id):
        return True

    try:
        status = str(effects._yookassa_get_payment_status(external_payment_id=ext_id)).lower()
    except Exception as e:
        effects.event_log.emit(
            event_type="payment_checked",
            source="payments",
            user_id="system",
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={"external_id": ext_id, "status": "error", "error": repr(e), "notification_id": notification_id, "event": event, "user_id_hint": (str(user_id_hint) if user_id_hint else None)},
        )
        raise

    effects.event_log.emit(
        event_type="payment_checked",
        source="payments",
        user_id="system",
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload={"external_id": ext_id, "status": status, "notification_id": notification_id, "event": event, "user_id_hint": (str(user_id_hint) if user_id_hint else None)},
    )

    ctx = resolve_created_payment_context(effects=effects, external_id=ext_id)
    uid = str(user_id_hint or ctx.get("user_id") or "system")
    terminal = "succeeded" if status in SUCCESS_STATUSES else ("failed" if status in FAILED_STATUSES else "pending")
    if terminal == "pending":
        return True
    if terminal == "succeeded":
        _record_success(
            effects,
            original_decision_id=str(ctx.get("envelope_id") or ""),
            original_correlation_id=str(ctx.get("correlation_id") or ""),
            reconciliation_decision_id=str(decision_id),
            reconciliation_correlation_id=str(correlation_id),
            user_id=uid,
            external_id=ext_id,
            status=status,
            notification_id=notification_id,
            event=event,
        )
    else:
        _record_failure(
            effects,
            original_decision_id=str(ctx.get("envelope_id") or ""),
            reconciliation_decision_id=str(decision_id),
            reconciliation_correlation_id=str(correlation_id),
            user_id=uid,
            external_id=ext_id,
            status=status,
            notification_id=notification_id,
            event=event,
        )
    return True


__all__ = [
    "_emit_payment_captured",
    "_record_failure",
    "_record_success",
    "_terminal_event_id",
    "reconcile_payment_effect",
    "reconcile_payments_effect",
]
