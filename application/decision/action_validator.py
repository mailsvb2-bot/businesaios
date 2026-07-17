from __future__ import annotations

CANON_APPLICATION_ACTION_VALIDATOR_ENVELOPE_ONLY = True


class ActionValidator:
    """Validate only already-issued canonical decision envelopes."""

    def valid(self, envelope: object) -> bool:
        decision = getattr(envelope, "decision", None)
        if decision is None:
            return False
        return bool(
            str(getattr(decision, "decision_id", "") or "").strip()
            and str(getattr(decision, "correlation_id", "") or "").strip()
            and str(getattr(decision, "action", "") or "").strip()
        )


__all__ = [
    "ActionValidator",
    "CANON_APPLICATION_ACTION_VALIDATOR_ENVELOPE_ONLY",
]
