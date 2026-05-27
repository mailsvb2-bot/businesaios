from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


def reconcile_payments_effect(
    effects: Any, *, decision_id: str, correlation_id: str, window_min: int = 30
) -> dict | bool:
    assert_called_from_executor()
    if effects.ledger is None:
        return True
    try:
        now = datetime.now(timezone.utc)
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
            if status in SUCCESS_STATUSES:
                if not try_mark_terminal_outbox(effects=effects, external_id=str(ext_id), terminal_status="succeeded"):
                    skipped_already += 1
                    continue
                processed_any += 1
                envelope_id = str(ev.get("decision_id") or ev.get("envelope_id") or "")
                mark_ledger_terminal(effects=effects, envelope_id=envelope_id, terminal_status="succeeded")
                effects.event_log.emit(
                    event_type="payment_succeeded",
                    source="payments",
                    user_id=str(uid),
                    decision_id=str(decision_id),
                    correlation_id=str(correlation_id),
                    payload={"external_id": str(ext_id), "status": status},
                )
            elif status in FAILED_STATUSES:
                if not try_mark_terminal_outbox(effects=effects, external_id=str(ext_id), terminal_status="failed"):
                    skipped_already += 1
                    continue
                processed_any += 1
                envelope_id = str(ev.get("decision_id") or ev.get("envelope_id") or "")
                mark_ledger_terminal(effects=effects, envelope_id=envelope_id, terminal_status="failed")
                effects.event_log.emit(
                    event_type="payment_failed",
                    source="payments",
                    user_id=str(uid),
                    decision_id=str(decision_id),
                    correlation_id=str(correlation_id),
                    payload={"external_id": str(ext_id), "status": status},
                )

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
    if not try_mark_terminal_outbox(effects=effects, external_id=ext_id, terminal_status=terminal):
        return True
    mark_ledger_terminal(effects=effects, envelope_id=str(ctx.get("envelope_id") or ""), terminal_status=terminal)
    effects.event_log.emit(
        event_type=("payment_succeeded" if terminal == "succeeded" else "payment_failed"),
        source="payments",
        user_id=uid,
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload={"external_id": ext_id, "status": status},
    )
    return True
