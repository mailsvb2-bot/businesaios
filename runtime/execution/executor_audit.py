"""Audit/proof helpers for RuntimeExecutor.

These helpers keep runtime.executor focused on sovereign orchestration while
centralizing proof-event emission in one place.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid5

from contracts.event_store import (
    append_event_strict,
    canonical_business_event_contract,
    supports_event_store,
)
from runtime.events import ACTION_AMBIGUOUS, ACTION_AUTHORIZED, ACTION_EXECUTED, ACTION_FAILED


def _user_id(payload: Any) -> str:
    if isinstance(payload, dict):
        return str(payload.get("user_id", "unknown"))
    return "unknown"


def emit_effect_window(event_log: Any, *, opened: bool, decision: Any) -> None:
    if event_log is None:
        return
    event_log.emit(
        event_type="effect_window_opened" if opened else "effect_window_closed",
        source="runtime_executor",
        user_id=_user_id(getattr(decision, "payload", None)),
        decision_id=decision.decision_id,
        correlation_id=decision.correlation_id,
        payload={"action": decision.action},
    )


def emit_decision_executed(event_log: Any, *, decision: Any) -> None:
    if event_log is None:
        return
    event_log.emit(
        event_type="decision_executed",
        source="runtime_executor",
        user_id=_user_id(getattr(decision, "payload", None)),
        decision_id=decision.decision_id,
        correlation_id=decision.correlation_id,
        payload={"action": decision.action},
    )


def emit_reward_observed(event_log: Any, *, decision: Any, reward_engine: Any, reward: float) -> None:
    if event_log is None:
        return
    details = reward_engine.last_details() if hasattr(reward_engine, "last_details") else {}
    event_log.emit(
        event_type="reward_observed",
        source="reward_engine",
        user_id=_user_id(getattr(decision, "payload", None)),
        decision_id=decision.decision_id,
        correlation_id=decision.correlation_id,
        payload={"policy_id": decision.policy_id, "reward": float(reward), **(details or {})},
    )


def emit_deployment_proposed(event_log: Any, *, decision: Any, proposal: Any) -> None:
    if event_log is None:
        return
    event_log.emit(
        event_type="deployment_proposed",
        source="learning_system",
        user_id=_user_id(getattr(decision, "payload", None)),
        decision_id=decision.decision_id,
        correlation_id=decision.correlation_id,
        payload={"proposal": proposal},
    )


CANON_ACTION_AUTHORIZATION_EVENT_SPINE_PROJECTION = True
CANON_ACTION_LIFECYCLE_EVENT_SPINE_PROJECTION = True

_EVENT_SOURCE = "runtime.execution.lifecycle"
_EVENT_NAMESPACE = UUID("517d8c6c-12e0-4e5d-9c61-e16ee9162d83")


class ActionEventProjectionConflict(ValueError):
    """The durable Action lifecycle event conflicts with signed canonical lineage."""


ActionAuthorizationEventProjectionConflict = ActionEventProjectionConflict


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _required(value: object, *, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ActionEventProjectionConflict(f"{field} is required")
    return normalized


def _event_id(
    *,
    tenant_id: str,
    business_id: str,
    intent_id: str,
    action_id: str,
    decision_id: str,
    event_type: str,
) -> str:
    semantic = "|".join((tenant_id, business_id, intent_id, action_id, decision_id, event_type))
    return str(uuid5(_EVENT_NAMESPACE, semantic))


def _matches(event_store: Any, *, tenant_id: str, event_type: str, event_id: str) -> list[dict[str, Any]]:
    return [
        dict(raw)
        for raw in event_store.iter_events(
            tenant_id=tenant_id,
            start_ms=0,
            event_type=event_type,
        )
        if str(raw.get("event_id") or "") == event_id
    ]


def _lineage(*, decision: Any) -> dict[str, Any] | None:
    payload = _mapping(getattr(decision, "payload", {}) or {})
    intent_id = str(payload.get("intent_id") or "").strip()
    if not intent_id:
        # Legacy/non-ActionIntent runtime decisions keep their existing path.
        return None

    tenant_id = _required(payload.get("tenant_id") or payload.get("tenant"), field="tenant_id")
    business_id = _required(payload.get("business_id"), field="business_id")
    decision_id = _required(getattr(decision, "decision_id", ""), field="decision_id")
    action_id = _required(payload.get("action_id"), field="action_id")
    action_type = _required(getattr(decision, "action", ""), field="action_type")
    channel = _required(payload.get("action_channel"), field="action_channel")

    policy = _mapping(payload.get("policy_decision"))
    if int(policy.get("schema_version") or 0) != 1:
        raise ActionEventProjectionConflict("canonical policy decision schema is required")
    identity_checks = (
        (policy.get("intent_id"), intent_id, "policy intent"),
        (policy.get("decision_id"), decision_id, "policy decision"),
        (policy.get("tenant_id"), tenant_id, "policy tenant"),
        (policy.get("business_id"), business_id, "policy business"),
    )
    for actual, expected, label in identity_checks:
        if str(actual or "").strip() != expected:
            raise ActionEventProjectionConflict(f"{label} identity mismatch")
    if str(policy.get("verdict") or "") != "allowed" or not bool(policy.get("allowed")):
        raise ActionEventProjectionConflict("action lifecycle requires an allowed PolicyDecisionV1")
    if bool(policy.get("approval_required")) or bool(policy.get("blocked_by_policy")):
        raise ActionEventProjectionConflict("restricted policy verdict cannot enter Action execution lifecycle")

    safety = _mapping(payload.get("autonomy_safety"))
    if not safety or not bool(safety.get("allowed")):
        raise ActionEventProjectionConflict("action lifecycle requires successful runtime safety preflight")
    if bool(safety.get("operator_required")):
        raise ActionEventProjectionConflict("operator-required action cannot enter side-effect lifecycle")

    capability = _mapping(payload.get("capability_planning"))
    if capability and not bool(capability.get("allowed")):
        raise ActionEventProjectionConflict("disabled capability cannot enter side-effect lifecycle")

    evidence_ids = tuple(
        dict.fromkeys(
            str(item).strip()
            for item in (payload.get("evidence_refs") or ())
            if str(item).strip()
        )
    )
    issued_at_ms = int(getattr(decision, "issued_at_ms", 0) or 0)
    actor_id = str(payload.get("actor_id") or "").strip() or None
    agent_id = str(getattr(decision, "issuer_id", "") or "").strip() or None
    return {
        "payload": payload,
        "tenant_id": tenant_id,
        "business_id": business_id,
        "goal_id": str(payload.get("goal_id") or "").strip() or None,
        "decision_id": decision_id,
        "intent_id": intent_id,
        "action_id": action_id,
        "action_type": action_type,
        "channel": channel,
        "policy": policy,
        "safety": safety,
        "evidence_ids": evidence_ids,
        "issued_at_ms": issued_at_ms,
        "actor_id": actor_id,
        "agent_id": agent_id,
        "correlation_id": str(getattr(decision, "correlation_id", "") or "").strip() or None,
    }


def _build_event(
    *,
    decision: Any,
    event_type: str,
    causation_id: str,
    lifecycle: Mapping[str, Any],
) -> dict[str, Any] | None:
    lineage = _lineage(decision=decision)
    if lineage is None:
        return None
    payload = dict(lineage["payload"])
    event_id = _event_id(
        tenant_id=lineage["tenant_id"],
        business_id=lineage["business_id"],
        intent_id=lineage["intent_id"],
        action_id=lineage["action_id"],
        decision_id=lineage["decision_id"],
        event_type=event_type,
    )
    event_payload = {
        "schema_version": 1,
        "business_id": lineage["business_id"],
        "actor_id": lineage["actor_id"],
        "agent_id": lineage["agent_id"],
        "occurred_at_ms": lineage["issued_at_ms"],
        "recorded_at_ms": lineage["issued_at_ms"],
        "causation_id": causation_id,
        "evidence_ids": list(lineage["evidence_ids"]),
        "action": {
            "intent_id": lineage["intent_id"],
            "action_id": lineage["action_id"],
            "action_type": lineage["action_type"],
            "channel": lineage["channel"],
            "derived_fact_ref": str(payload.get("derived_fact_ref") or "").strip() or None,
        },
        "policy_decision": dict(lineage["policy"]),
        "lifecycle": dict(lifecycle),
    }
    if lineage["goal_id"] is not None:
        event_payload["goal_id"] = lineage["goal_id"]
    return {
        "event_id": event_id,
        "tenant_id": lineage["tenant_id"],
        "source": _EVENT_SOURCE,
        "event_type": event_type,
        "timestamp_ms": lineage["issued_at_ms"],
        "decision_id": lineage["decision_id"],
        "correlation_id": lineage["correlation_id"],
        "payload": event_payload,
    }


def _persist_event(*, event_store: Any, event: dict[str, Any], missing_store_code: str) -> str:
    if not supports_event_store(event_store):
        raise RuntimeError(missing_store_code)

    tenant_id = str(event["tenant_id"])
    event_type = str(event["event_type"])
    event_id = str(event["event_id"])
    matches = _matches(
        event_store,
        tenant_id=tenant_id,
        event_type=event_type,
        event_id=event_id,
    )
    if len(matches) > 1:
        raise ActionEventProjectionConflict(f"multiple Event Spine rows share one {event_type} id")
    if matches:
        if canonical_business_event_contract(matches[0]) != canonical_business_event_contract(event):
            raise ActionEventProjectionConflict(f"persisted {event_type} conflicts with signed lineage")
        return event_id

    try:
        append_event_strict(event_store, tenant_id=tenant_id, event=event)
    except Exception:
        matches = _matches(
            event_store,
            tenant_id=tenant_id,
            event_type=event_type,
            event_id=event_id,
        )
        if not matches or canonical_business_event_contract(matches[0]) != canonical_business_event_contract(event):
            raise
        return event_id

    matches = _matches(
        event_store,
        tenant_id=tenant_id,
        event_type=event_type,
        event_id=event_id,
    )
    if len(matches) != 1:
        raise RuntimeError(f"{event_type} Event Spine append did not become durable")
    if canonical_business_event_contract(matches[0]) != canonical_business_event_contract(event):
        raise ActionEventProjectionConflict(f"persisted {event_type} conflicts with signed lineage")
    return event_id


def _authorized_event(*, decision: Any) -> dict[str, Any] | None:
    lineage = _lineage(decision=decision)
    if lineage is None:
        return None
    return _build_event(
        decision=decision,
        event_type=ACTION_AUTHORIZED,
        causation_id=lineage["intent_id"],
        lifecycle={
            "status": "authorized",
            "safety_verdict": {
                "allowed": True,
                "operator_required": False,
                "reason": str(lineage["safety"].get("reason") or "").strip() or None,
            },
        },
    )


def _authorization_event_id(*, decision: Any) -> str | None:
    lineage = _lineage(decision=decision)
    if lineage is None:
        return None
    return _event_id(
        tenant_id=lineage["tenant_id"],
        business_id=lineage["business_id"],
        intent_id=lineage["intent_id"],
        action_id=lineage["action_id"],
        decision_id=lineage["decision_id"],
        event_type=ACTION_AUTHORIZED,
    )


def _require_authorized(*, event_store: Any, decision: Any) -> str | None:
    lineage = _lineage(decision=decision)
    if lineage is None:
        return None
    if not supports_event_store(event_store):
        raise RuntimeError("ACTION_LIFECYCLE_EVENT_STORE_REQUIRED")
    authorization_id = _authorization_event_id(decision=decision)
    matches = _matches(
        event_store,
        tenant_id=lineage["tenant_id"],
        event_type=ACTION_AUTHORIZED,
        event_id=str(authorization_id),
    )
    expected = _authorized_event(decision=decision)
    if len(matches) != 1 or expected is None:
        raise ActionEventProjectionConflict("terminal Action event requires one durable action.authorized predecessor")
    if canonical_business_event_contract(matches[0]) != canonical_business_event_contract(expected):
        raise ActionEventProjectionConflict("durable action.authorized predecessor conflicts with signed lineage")
    return str(authorization_id)


def project_action_authorized_event(*, event_store: Any, decision: Any) -> str | None:
    """Persist one canonical pre-side-effect authorization event."""

    event = _authorized_event(decision=decision)
    if event is None:
        return None
    return _persist_event(
        event_store=event_store,
        event=event,
        missing_store_code="ACTION_AUTHORIZATION_EVENT_STORE_REQUIRED",
    )


def project_action_executed_event(
    *,
    event_store: Any,
    decision: Any,
    verification: Mapping[str, Any] | None = None,
    output: Mapping[str, Any] | None = None,
) -> str | None:
    """Persist verified Action execution without copying provider payloads into Event Spine."""

    authorization_id = _require_authorized(event_store=event_store, decision=decision)
    if authorization_id is None:
        return None
    verification_payload = _mapping(verification)
    if verification_payload.get("verified") is not True:
        raise ActionEventProjectionConflict("action.executed requires explicit successful verification")
    normalized_output = _mapping(output)
    external_refs = verification_payload.get("external_refs")
    if not isinstance(external_refs, (list, tuple)):
        external_refs = []
    event = _build_event(
        decision=decision,
        event_type=ACTION_EXECUTED,
        causation_id=authorization_id,
        lifecycle={
            "status": "executed",
            "handler_status": str(normalized_output.get("status") or "executed"),
            "verification_status": str(
                verification_payload.get("status")
                or ("verified" if verification_payload else "verified")
            ),
            "external_ref_count": len(external_refs),
        },
    )
    if event is None:
        return None
    return _persist_event(
        event_store=event_store,
        event=event,
        missing_store_code="ACTION_LIFECYCLE_EVENT_STORE_REQUIRED",
    )


def project_action_ambiguous_event(
    *,
    event_store: Any,
    decision: Any,
    reason: str,
    error_type: str | None = None,
) -> str | None:
    """Persist an uncertain post-authorization side effect without claiming success or failure."""

    authorization_id = _require_authorized(event_store=event_store, decision=decision)
    if authorization_id is None:
        return None
    normalized_reason = _required(reason, field="ambiguous reason")
    event = _build_event(
        decision=decision,
        event_type=ACTION_AMBIGUOUS,
        causation_id=authorization_id,
        lifecycle={
            "status": "ambiguous",
            "reason": normalized_reason,
            "error_type": str(error_type or "").strip() or None,
            "recovery": "reconcile_before_retry",
        },
    )
    if event is None:
        return None
    return _persist_event(
        event_store=event_store,
        event=event,
        missing_store_code="ACTION_LIFECYCLE_EVENT_STORE_REQUIRED",
    )


def project_action_failed_event(
    *,
    event_store: Any,
    decision: Any,
    reason: str,
    error_type: str | None = None,
) -> str | None:
    """Persist one canonical failure after authorization and before verified execution."""

    authorization_id = _require_authorized(event_store=event_store, decision=decision)
    if authorization_id is None:
        return None
    normalized_reason = _required(reason, field="failure reason")
    event = _build_event(
        decision=decision,
        event_type=ACTION_FAILED,
        causation_id=authorization_id,
        lifecycle={
            "status": "failed",
            "reason": normalized_reason,
            "error_type": str(error_type or "").strip() or None,
        },
    )
    if event is None:
        return None
    return _persist_event(
        event_store=event_store,
        event=event,
        missing_store_code="ACTION_LIFECYCLE_EVENT_STORE_REQUIRED",
    )
