from __future__ import annotations

from collections.abc import Mapping

from runtime.proofs import ACTION_PROOF_EVENT

_SUCCESS_STATUSES = frozenset(
    {"captured", "completed", "confirmed", "delivered", "sent", "succeeded", "success"}
)
_FAILURE_STATUSES = frozenset(
    {"canceled", "cancelled", "declined", "failed", "failure", "rejected"}
)
_REGISTERED_SUCCESS_PROOF_TYPES = frozenset(
    str(event_type) for event_type in ACTION_PROOF_EVENT.values() if str(event_type)
)


def resolve_action_proof_success(
    event_type: str,
    payload: Mapping[str, object],
) -> bool | None:
    """Resolve canonical execution proof semantics without inventing success."""

    explicit = [
        value
        for key in ("success", "ok")
        if isinstance((value := payload.get(key)), bool)
    ]
    if explicit:
        if any(value is not explicit[0] for value in explicit[1:]):
            return None
        return explicit[0]

    status = str(payload.get("status") or "").strip().lower()
    if status in _SUCCESS_STATUSES:
        return True
    if status in _FAILURE_STATUSES:
        return False
    if str(event_type) in _REGISTERED_SUCCESS_PROOF_TYPES:
        return True
    return None


__all__ = ["resolve_action_proof_success"]
