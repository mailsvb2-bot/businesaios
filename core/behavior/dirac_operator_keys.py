"""Canonical Dirac operator-key surface.

Event-backed operators are derived from the sole event vocabulary owner instead
of being copied into another hand-maintained list. A small, explicit set of
behavioral policy operators remains here because those keys describe proposed
influence tactics rather than emitted events.
"""

from __future__ import annotations

from core.events.event_types import KNOWN_EVENT_TYPES

BEHAVIORAL_POLICY_OPERATOR_KEYS: tuple[str, ...] = (
    "content_nudge",
    "deadline_pressure",
    "price_hard_push",
    "scarcity_urgency",
)


def required_operator_keys() -> tuple[str, ...]:
    """Return every event-backed and policy-only Dirac operator key.

    ``KNOWN_EVENT_TYPES`` remains the single owner of event names. This
    function only composes that vocabulary with the genuinely non-event policy
    operators used by product governance catalogs.
    """

    return tuple(
        sorted(set(KNOWN_EVENT_TYPES) | set(BEHAVIORAL_POLICY_OPERATOR_KEYS))
    )


__all__ = ["BEHAVIORAL_POLICY_OPERATOR_KEYS", "required_operator_keys"]
