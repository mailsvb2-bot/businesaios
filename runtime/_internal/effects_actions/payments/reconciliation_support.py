from __future__ import annotations

from typing import Any, Tuple

from runtime.observability.error_handling import swallow

RUNTIME_EFFECTS_IMPL_PATH = 'runtime/_internal/_effects_impl.py'
TERMINAL_EVENTS = {"payment_checked", "payment_succeeded", "payment_failed"}
SUCCESS_STATUSES = {"succeeded", "success", "paid"}
FAILED_STATUSES = {"canceled", "cancelled", "failed"}


def event_already_processed(*, effects: Any, external_id: str) -> bool:
    if effects.payment_outbox is not None and hasattr(effects.payment_outbox, "terminal_status"):
        try:
            if effects.payment_outbox.terminal_status(str(external_id)):
                return True
        except Exception:
            swallow(__name__, RUNTIME_EFFECTS_IMPL_PATH)
    try:
        for event in effects.event_log.iter_events():
            event_type = event.get("event_type") or event.get("type")
            if event_type not in TERMINAL_EVENTS:
                continue
            payload = event.get("payload") or {}
            if str(payload.get("external_id") or "") == str(external_id):
                return True
    except Exception:
        return False
    return False


def resolve_created_payment_context(*, effects: Any, external_id: str) -> Tuple[str, str]:
    envelope_id = ""
    user_id = "system"
    try:
        for event in effects.event_log.iter_events():
            if (event.get("event_type") or event.get("type")) != "payment_created":
                continue
            payload = event.get("payload") or {}
            if str(payload.get("external_id") or "") != str(external_id):
                continue
            envelope_id = str(event.get("decision_id") or event.get("envelope_id") or "")
            user_id = str(event.get("user_id") or user_id)
            break
    except Exception:
        return "", user_id
    return envelope_id, user_id


def try_mark_terminal_outbox(*, effects: Any, external_id: str, terminal_status: str, notification_id: str | None = None, event: str | None = None) -> bool:
    if effects.payment_outbox is None or not hasattr(effects.payment_outbox, "try_mark_terminal_emitted"):
        return True
    try:
        return bool(
            effects.payment_outbox.try_mark_terminal_emitted(
                external_id=str(external_id),
                terminal_status=str(terminal_status),
                notification_id=notification_id,
                event=event,
            )
        )
    except Exception:
        swallow(__name__, RUNTIME_EFFECTS_IMPL_PATH)
        return True


def mark_ledger_terminal(*, effects: Any, envelope_id: str, terminal_status: str) -> None:
    if effects.ledger is None or not envelope_id:
        return
    try:
        if terminal_status == "succeeded":
            effects.ledger.mark_effect_completed(envelope_id)
        elif terminal_status == "failed":
            effects.ledger.mark_effect_failed(envelope_id)
    except Exception:
        swallow(__name__, RUNTIME_EFFECTS_IMPL_PATH)
