from __future__ import annotations

from core.behavior.observability.metric_names import (
    BEHAVIOR_METRIC_GUARDRAILS_VIOLATIONS,
    BEHAVIOR_METRIC_MARKET_COHERENCE,
    BEHAVIOR_METRIC_ORG_ALIGNMENT,
    BEHAVIOR_METRIC_PERSON_ANTI,
    BEHAVIOR_METRIC_PERSON_COHERENCE,
    BEHAVIOR_METRIC_POLICY_DENIALS,
)


def behavior_metrics_from_payload(payload: dict[str, object]) -> dict[str, float]:
    behavior = dict(payload.get("behavior", {}))
    org_observables = dict(behavior.get("org_observables", {}))
    return {
        BEHAVIOR_METRIC_POLICY_DENIALS: float(sum(dict(behavior.get("policy_denials", {})).values())),
        BEHAVIOR_METRIC_GUARDRAILS_VIOLATIONS: 1.0 if behavior.get("guardrails_violation") else 0.0,
        BEHAVIOR_METRIC_PERSON_COHERENCE: float(behavior.get("coherence_score", 0.0)),
        BEHAVIOR_METRIC_PERSON_ANTI: float(behavior.get("anti_field_level", 0.0)),
        BEHAVIOR_METRIC_ORG_ALIGNMENT: float(org_observables.get("org_alignment_score", 0.0)),
        BEHAVIOR_METRIC_MARKET_COHERENCE: float(behavior.get("market_alignment_score", 0.0)),
    }
