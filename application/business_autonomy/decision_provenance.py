from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.events.event_types import DECISION_PROPOSED

CANON_EXTERNAL_DECISION_PROVENANCE = True
_DECISION_EVENT_SOURCE = "application.decision_runtime"


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class DecisionEventSpineProvenanceVerifier:
    """Bind managed external execution to the canonical signed-decision lineage.

    This verifier intentionally performs no cryptography. Decision signatures stay
    owned by DecisionCore/RuntimeGuard. Here we only require the durable
    decision.proposed projection that the canonical decision runtime emitted from
    the signed DecisionEnvelope and bind it exactly to ActionIntentV2.
    """

    event_store: object

    def assert_intent_provenance(self, intent: object) -> str:
        iter_events = getattr(self.event_store, "iter_events", None)
        if not callable(iter_events):
            raise RuntimeError("canonical decision event store is unavailable")

        tenant_id = _text(getattr(intent, "tenant_id", ""))
        decision_id = _text(getattr(intent, "decision_id", ""))
        matches = [
            dict(raw)
            for raw in iter_events(
                tenant_id=tenant_id,
                start_ms=0,
                event_type=DECISION_PROPOSED,
            )
            if _text(_mapping(raw).get("decision_id")) == decision_id
        ]
        if not matches:
            raise LookupError("canonical decision provenance not found")
        if len(matches) != 1:
            raise ValueError("canonical decision provenance is ambiguous")

        event = matches[0]
        if _text(event.get("source")) != _DECISION_EVENT_SOURCE:
            raise ValueError("canonical decision provenance source mismatch")
        payload = _mapping(event.get("payload"))
        decision = _mapping(payload.get("decision"))

        expected = {
            "tenant_id": tenant_id,
            "business_id": _text(getattr(intent, "business_id", "")),
            "decision_id": decision_id,
            "correlation_id": _text(getattr(intent, "correlation_id", "")),
            "goal_id": _text(getattr(intent, "goal_id", "")),
            "agent_id": _text(getattr(intent, "agent_id", "")),
            "action_type": _text(getattr(intent, "capability_target", "")),
            "action_intent_id": _text(getattr(intent, "intent_id", "")),
            "decision_payload_hash": _text(getattr(intent, "payload_hash", "")),
        }
        actual = {
            "tenant_id": _text(event.get("tenant_id")),
            "business_id": _text(payload.get("business_id")),
            "decision_id": _text(event.get("decision_id")),
            "correlation_id": _text(event.get("correlation_id")),
            "goal_id": _text(decision.get("goal_id")),
            "agent_id": _text(payload.get("agent_id")),
            "action_type": _text(decision.get("action_type")),
            "action_intent_id": _text(decision.get("action_intent_id")),
            "decision_payload_hash": _text(decision.get("decision_payload_hash")),
        }
        mismatches = sorted(key for key, value in expected.items() if actual.get(key) != value)
        if mismatches:
            raise ValueError(
                "canonical decision provenance mismatch: " + ",".join(mismatches)
            )
        event_id = _text(event.get("event_id"))
        if not event_id:
            raise ValueError("canonical decision provenance event_id is required")
        return event_id


__all__ = [
    "CANON_EXTERNAL_DECISION_PROVENANCE",
    "DecisionEventSpineProvenanceVerifier",
]
