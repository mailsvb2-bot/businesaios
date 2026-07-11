from __future__ import annotations

from typing import Any

from runtime.observability.error_handling import swallow

RUNTIME_EFFECTS_IMPL_PATH = "runtime/_internal/_effects_impl.py"
TERMINAL_EVENTS = {"payment_captured", "payment_failed"}
SUCCESS_STATUSES = {"succeeded", "success", "paid"}
FAILED_STATUSES = {"canceled", "cancelled", "failed"}


def _terminal_event_for_external_id(*, effects: Any, external_id: str) -> dict[str, Any] | None:
    try:
        for event in effects.event_log.iter_events():
            event_type = str(event.get("event_type") or event.get("type") or "")
            if event_type not in TERMINAL_EVENTS:
                continue
            payload = event.get("payload") or {}
            if str(payload.get("external_id") or "") == str(external_id):
                return dict(event)
    except Exception:
        return None
    return None


def _backfill_terminal_marker(*, effects: Any, external_id: str, event: dict[str, Any]) -> None:
    if effects.payment_outbox is None or not hasattr(effects.payment_outbox, "try_mark_terminal_emitted"):
        return
    event_type = str(event.get("event_type") or event.get("type") or "")
    terminal_status = "succeeded" if event_type == "payment_captured" else "failed"
    try:
        effects.payment_outbox.try_mark_terminal_emitted(
            external_id=str(external_id),
            terminal_status=terminal_status,
            event=event_type,
        )
    except Exception:
        swallow(__name__, RUNTIME_EFFECTS_IMPL_PATH)


def event_already_processed(*, effects: Any, external_id: str) -> bool:
    """Return True only when a canonical terminal proof event exists.

    A payment_terminal marker alone is not proof: older code committed that marker
    before emitting the event, so a crash could leave a permanent false terminal.
    When proof exists but the marker is missing, repair the marker idempotently.
    """

    event = _terminal_event_for_external_id(effects=effects, external_id=str(external_id))
    if event is None:
        return False
    _backfill_terminal_marker(effects=effects, external_id=str(external_id), event=event)
    return True


def resolve_created_payment_context(*, effects: Any, external_id: str) -> dict[str, str]:
    context = {
        "envelope_id": "",
        "user_id": "system",
        "correlation_id": "",
    }
    try:
        for event in effects.event_log.iter_events():
            if (event.get("event_type") or event.get("type")) != "payment_created":
                continue
            payload = event.get("payload") or {}
            if str(payload.get("external_id") or "") != str(external_id):
                continue
            context["envelope_id"] = str(event.get("decision_id") or event.get("envelope_id") or "")
            context["user_id"] = str(event.get("user_id") or context["user_id"])
            context["correlation_id"] = str(event.get("correlation_id") or "")
            break
    except Exception:
        return context
    return context


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
