from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid5

from contracts.event_store import (
    append_event_strict,
    canonical_business_event_contract,
    supports_event_store,
)
from core.events.event_types import DECISION_PROPOSED
from core.observability.throttled_logger import exception_throttled
from runtime.events.world_model_events import build_world_model_pinned_event

logger = logging.getLogger(__name__)


def archive_envelope(*, archive: Any, events: Any, env: Any, decision_id: str, user_id: str, correlation_id: str) -> None:
    if archive is None:
        return
    try:
        archive.put(env)
    except Exception as exc:  # noqa: BLE001
        exception_throttled(
            logger,
            key=f"archive_put|{decision_id}",
            msg=f"decision_core: archive.put failed decision={decision_id}",
        )
        try:
            if events is not None and hasattr(events, "emit"):
                events.emit(
                    event_type="decision_archive_failed",
                    source="decision_core",
                    user_id=user_id,
                    decision_id=decision_id,
                    correlation_id=correlation_id,
                    payload={"error": exc.__class__.__name__},
                )
        except Exception:  # noqa: BLE001
            exception_throttled(
                logger,
                key=f"archive_emit|{decision_id}",
                msg="decision_core: archive failure emit failed",
            )


def emit_decision_issued(*, events: Any, user_id: str, built: Any, tagged: Any, correlation_key: str | None) -> None:
    if events is None or not hasattr(events, "emit"):
        return
    events.emit(
        event_type="decision_issued",
        source="decision_core",
        user_id=user_id,
        decision_id=built.decision.decision_id,
        correlation_id=built.decision.correlation_id,
        payload={
            "policy_id": built.decision.policy_id,
            "action": built.decision.action,
            "payload_hash": built.payload_hash,
            "snapshot_id": built.decision.snapshot_id,
            "state_hash": built.decision.state_hash,
            "issued_at_ms": built.decision.issued_at_ms,
            "expires_at_ms": built.decision.expires_at_ms,
            "kid": built.envelope.kid,
            "envelope_version": built.decision.envelope_version,
            "state_schema_version": built.decision.state_schema_version,
            "action_schema_version": built.decision.action_schema_version,
            "correlation_key": correlation_key,
            "product_id": tagged.product_id,
            "domain": tagged.domain,
            "product_version": tagged.product_version,
        },
    )


def emit_world_model_pinned(*, events: Any, user_id: str, decision_id: str, correlation_id: str, world_model_meta: dict, issuer_id: str) -> None:
    try:
        event = build_world_model_pinned_event(
            decision_id=str(decision_id),
            user_id=str(user_id),
            world_model_meta=world_model_meta,
            issuer_id=issuer_id,
            timestamp_ms=int(time.time() * 1000),
        )
        if hasattr(events, "append"):
            events.append(event)
        elif hasattr(events, "emit"):
            events.emit(
                event_type=event.get("type", "decision.world_model_pinned"),
                source="decision_core",
                user_id=str(user_id),
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                payload={"world_model_meta": dict(world_model_meta)},
            )
    except Exception:  # noqa: BLE001
        exception_throttled(
            logger,
            key=f"{user_id}|world_model_pinned_event",
            msg="decision_core: failed to append world model pinned event",
        )


def emit_trace(*, events: Any, trace: Any, user_id: str, decision_id: str, correlation_id: str) -> None:
    try:
        tr = trace.build(decision_id=decision_id)
        events.emit(
            event_type="ai_decision_trace",
            source="decision_core",
            user_id=user_id,
            decision_id=decision_id,
            correlation_id=correlation_id,
            payload=tr.to_dict(),
        )
    except Exception:  # noqa: BLE001
        exception_throttled(
            logger,
            key=f"trace_emit|{decision_id}",
            msg="decision_core: trace emit failed",
        )


CANON_DECISION_EVENT_SPINE_PROJECTION = True

_EVENT_SOURCE = "application.decision_runtime"
_EVENT_NAMESPACE = UUID("ed04e8a7-daa1-46a1-a6ce-cf9d3af31c7e")


class DecisionEventProjectionConflict(ValueError):
    """A durable Decision Event Spine row conflicts with canonical Decision lineage."""


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _required(value: object, *, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise DecisionEventProjectionConflict(f"{field} is required")
    return normalized


def _event_id(*, tenant_id: str, business_id: str, decision_id: str) -> str:
    return str(uuid5(_EVENT_NAMESPACE, "|".join((tenant_id, business_id, decision_id, DECISION_PROPOSED))))


def _matches(event_store: Any, *, tenant_id: str, event_id: str) -> list[dict[str, Any]]:
    return [
        dict(raw)
        for raw in event_store.iter_events(
            tenant_id=tenant_id,
            start_ms=0,
            event_type=DECISION_PROPOSED,
        )
        if str(raw.get("event_id") or "") == event_id
    ]


def _build_event(*, envelope: Any, action_intent: Any) -> dict[str, Any]:
    decision = getattr(envelope, "decision", None)
    if decision is None:
        raise DecisionEventProjectionConflict("decision envelope is required")

    decision_id = _required(getattr(decision, "decision_id", ""), field="decision_id")
    correlation_id = _required(getattr(decision, "correlation_id", ""), field="correlation_id")
    action_type = _required(getattr(decision, "action", ""), field="action_type")
    tenant_id = _required(getattr(action_intent, "tenant_id", ""), field="tenant_id")
    business_id = _required(getattr(action_intent, "business_id", ""), field="business_id")
    intent_id = _required(getattr(action_intent, "intent_id", ""), field="intent_id")

    identity_checks = (
        (getattr(action_intent, "decision_id", ""), decision_id, "decision"),
        (getattr(action_intent, "correlation_id", ""), correlation_id, "correlation"),
        (getattr(action_intent, "action_type", ""), action_type, "action"),
    )
    for actual, expected, label in identity_checks:
        if str(actual or "").strip() != expected:
            raise DecisionEventProjectionConflict(f"ActionIntent {label} identity mismatch")

    issued_at_ms = int(getattr(decision, "issued_at_ms", 0) or 0)
    if issued_at_ms <= 0:
        raise DecisionEventProjectionConflict("decision issued_at_ms is required")

    intent_payload = (
        action_intent.payload_copy()
        if callable(getattr(action_intent, "payload_copy", None))
        else _mapping(getattr(action_intent, "payload", {}))
    )
    actor_id = str(intent_payload.get("actor_id") or "").strip() or None
    agent_id = str(getattr(decision, "issuer_id", "") or "").strip() or None
    evidence_ids = tuple(
        dict.fromkeys(
            str(item).strip()
            for item in (getattr(action_intent, "evidence_refs", ()) or ())
            if str(item).strip()
        )
    )
    derived_fact_ref = str(getattr(action_intent, "derived_fact_ref", "") or "").strip() or None
    event_id = _event_id(
        tenant_id=tenant_id,
        business_id=business_id,
        decision_id=decision_id,
    )
    return {
        "event_id": event_id,
        "tenant_id": tenant_id,
        "source": _EVENT_SOURCE,
        "event_type": DECISION_PROPOSED,
        "timestamp_ms": issued_at_ms,
        "decision_id": decision_id,
        "correlation_id": correlation_id,
        "payload": {
            "schema_version": 1,
            "business_id": business_id,
            "actor_id": actor_id,
            "agent_id": agent_id,
            "occurred_at_ms": issued_at_ms,
            "recorded_at_ms": issued_at_ms,
            "causation_id": derived_fact_ref,
            "evidence_ids": list(evidence_ids),
            "decision": {
                "decision_id": decision_id,
                "action_type": action_type,
                "policy_id": str(getattr(decision, "policy_id", "") or "").strip() or None,
                "snapshot_id": str(getattr(decision, "snapshot_id", "") or "").strip() or None,
                "state_hash": str(getattr(decision, "state_hash", "") or "").strip() or None,
                "decision_payload_hash": str(getattr(envelope, "payload_hash", "") or "").strip() or None,
                "action_intent_id": intent_id,
                "objective_name": str(getattr(action_intent, "objective_name", "") or "").strip() or None,
            },
        },
    }


def project_decision_proposed_event(*, event_store: Any, envelope: Any, action_intent: Any) -> str:
    """Project a business-scoped sovereign Decision into the canonical Event Spine."""

    if not supports_event_store(event_store):
        raise RuntimeError("DECISION_EVENT_STORE_REQUIRED")
    event = _build_event(envelope=envelope, action_intent=action_intent)
    tenant_id = str(event["tenant_id"])
    event_id = str(event["event_id"])
    matches = _matches(event_store, tenant_id=tenant_id, event_id=event_id)
    if len(matches) > 1:
        raise DecisionEventProjectionConflict("multiple Event Spine rows share one decision.proposed id")
    if matches:
        if canonical_business_event_contract(matches[0]) != canonical_business_event_contract(event):
            raise DecisionEventProjectionConflict("persisted decision.proposed conflicts with canonical Decision lineage")
        return event_id

    try:
        append_event_strict(event_store, tenant_id=tenant_id, event=event)
    except Exception:
        matches = _matches(event_store, tenant_id=tenant_id, event_id=event_id)
        if not matches or canonical_business_event_contract(matches[0]) != canonical_business_event_contract(event):
            raise
        return event_id

    matches = _matches(event_store, tenant_id=tenant_id, event_id=event_id)
    if len(matches) != 1:
        raise RuntimeError("decision.proposed Event Spine append did not become durable")
    if canonical_business_event_contract(matches[0]) != canonical_business_event_contract(event):
        raise DecisionEventProjectionConflict("persisted decision.proposed conflicts with canonical Decision lineage")
    return event_id
