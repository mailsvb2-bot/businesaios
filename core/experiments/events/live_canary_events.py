from __future__ import annotations

EXPERIMENT_CREATED = "experiment_created@v1"
EXPERIMENT_ASSIGNMENT = "experiment_assignment@v1"
CONTROL_ACTION_EXECUTED = "control_action_executed@v1"
CANDIDATE_ACTION_EXECUTED = "candidate_action_executed@v1"
BUSINESS_OUTCOME_OBSERVED = "business_outcome_observed@v1"
CANARY_GUARDRAIL_BREACHED = "canary_guardrail_breached@v1"
CANARY_AUTO_ROLLED_BACK = "canary_auto_rolled_back@v1"
CANARY_PROMOTED = "canary_promoted@v1"

LIVE_CANARY_EVENT_TYPES = frozenset(
    {
        EXPERIMENT_CREATED,
        EXPERIMENT_ASSIGNMENT,
        CONTROL_ACTION_EXECUTED,
        CANDIDATE_ACTION_EXECUTED,
        BUSINESS_OUTCOME_OBSERVED,
        CANARY_GUARDRAIL_BREACHED,
        CANARY_AUTO_ROLLED_BACK,
        CANARY_PROMOTED,
    }
)


def _register_canonical_event_types() -> None:
    from core.events.event_types import KNOWN_EVENT_TYPES

    KNOWN_EVENT_TYPES.update(LIVE_CANARY_EVENT_TYPES)


def is_live_canary_event(event_type: str) -> bool:
    return str(event_type or "").strip() in LIVE_CANARY_EVENT_TYPES


_register_canonical_event_types()


__all__ = [
    "BUSINESS_OUTCOME_OBSERVED",
    "CANARY_AUTO_ROLLED_BACK",
    "CANARY_GUARDRAIL_BREACHED",
    "CANARY_PROMOTED",
    "CANDIDATE_ACTION_EXECUTED",
    "CONTROL_ACTION_EXECUTED",
    "EXPERIMENT_ASSIGNMENT",
    "EXPERIMENT_CREATED",
    "LIVE_CANARY_EVENT_TYPES",
    "is_live_canary_event",
]
