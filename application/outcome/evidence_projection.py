from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from contracts.business_outcome import BusinessOutcomeV1
from contracts.event_store import canonical_business_event_contract
from storage.evidence_store import EvidenceRecord, EvidenceStore

CANON_BUSINESS_OUTCOME_EVIDENCE_PROJECTION = True
CANON_BUSINESS_OUTCOME_EVENT_SPINE_PROJECTION = True
OUTCOME_OBSERVED_EVENT_TYPE = "outcome.observed"
_EVENT_SOURCE = "closed_loop.evidence_projection"


class BusinessOutcomeBodyUnavailable(LookupError):
    """A canonical outcome lineage exists, but its full body is unavailable."""


class BusinessOutcomeProjectionConflict(ValueError):
    """Persisted outcome body conflicts with canonical evidence identity."""


BusinessOutcomeEventProjectionConflict = BusinessOutcomeProjectionConflict


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _project_record(record: EvidenceRecord) -> BusinessOutcomeV1:
    body = _mapping(record.payload.get("business_outcome"))
    if not body:
        raise BusinessOutcomeBodyUnavailable(f"business outcome body unavailable for {record.lineage.get('outcome', '')}")
    required = ("tenant_id", "business_id", "run_id", "intent_id", "decision_id", "action_id", "action_type", "goal", "status", "outcome_id")
    if any(not str(body.get(name) or "").strip() for name in required):
        raise BusinessOutcomeProjectionConflict("business outcome body is incomplete")
    feedback = {
        "attempted": bool(body.get("attempted")), "executed": bool(body.get("executed")), "verified": bool(body.get("verified")),
        "verification_status": str(body.get("evidence_status") or "unknown"),
        "goal_evaluation": {"achieved": bool(body.get("goal_achieved")), "terminal": bool(body.get("goal_terminal")), "completion_ratio": body.get("completion_ratio"), "success_confidence": body.get("success_confidence")},
        "revenue_outcome": {"revenue_amount": body.get("revenue_amount"), "verified": bool(body.get("revenue_verified"))},
        "normalized_outcome": _mapping(body.get("metrics")), "execution_feedback": {"source_of_truth": str(body.get("source_of_truth") or "feedback_contract")},
        "external_refs": list(body.get("external_refs") or ()), "evidence_status": str(body.get("evidence_status") or "unknown"),
    }
    outcome = BusinessOutcomeV1.from_feedback(
        tenant_id=str(body["tenant_id"]), business_id=str(body["business_id"]), run_id=str(body["run_id"]), intent_id=str(body["intent_id"]),
        decision_id=str(body["decision_id"]), action_id=str(body["action_id"]), action_type=str(body["action_type"]), goal=str(body["goal"]),
        status=str(body["status"]), feedback=feedback, evidence_refs=tuple(str(item) for item in body.get("evidence_refs") or ()),
        derived_fact_ref=str(body.get("derived_fact_ref") or ""),
    )
    if int(body.get("schema_version") or 0) != outcome.schema_version or outcome.as_dict() != dict(body):
        raise BusinessOutcomeProjectionConflict("business outcome body conflicts with canonical contract")
    checks = (
        (record.tenant_id, outcome.tenant_id, "tenant"), (record.business_id, outcome.business_id, "business"), (record.run_id, outcome.run_id, "run"),
        (record.action_id or "", outcome.action_id, "action"), (record.lineage.get("outcome", ""), outcome.outcome_id, "outcome"),
        (record.lineage.get("decision", ""), outcome.decision_id, "decision"),
    )
    for actual, expected, label in checks:
        if str(actual or "") != str(expected or ""):
            raise BusinessOutcomeProjectionConflict(f"business outcome {label} identity conflicts with evidence")
    derived = str(record.lineage.get("derived_fact") or "")
    if derived and derived != outcome.derived_fact_ref:
        raise BusinessOutcomeProjectionConflict("business outcome derived fact conflicts with evidence")
    return outcome


class BusinessOutcomeEvidenceProjector:
    """Read-only BusinessOutcomeV1 projection over the canonical EvidenceStore."""

    def __init__(self, evidence_store: EvidenceStore) -> None:
        self._evidence = evidence_store

    @staticmethod
    def _is_outcome_record(record: EvidenceRecord, *, business_id: str) -> bool:
        return record.scope == "closed_loop" and record.source_type == "closed_loop_verification" and record.business_id == str(business_id) and bool(str(record.lineage.get("outcome") or ""))

    def _project_record(self, record: EvidenceRecord) -> BusinessOutcomeV1:
        return _project_record(record)

    def get(self, *, tenant_id: str, business_id: str, outcome_id: str, limit: int = 1000) -> BusinessOutcomeV1:
        target = str(outcome_id or "").strip()
        if not target:
            raise ValueError("outcome_id is required")
        rows = [row for row in self._evidence.list_for_tenant(tenant_id=tenant_id, limit=limit) if self._is_outcome_record(row, business_id=business_id) and str(row.lineage.get("outcome") or "") == target and _mapping(row.payload.get("business_outcome"))]
        if not rows:
            raise LookupError(f"business outcome not found: {target}")
        items = tuple(_project_record(row) for row in rows)
        if any(item != items[0] for item in items[1:]):
            raise BusinessOutcomeProjectionConflict("multiple canonical evidence rows disagree on outcome body")
        return items[0]

    def list_for_business(self, *, tenant_id: str, business_id: str, limit: int = 1000) -> tuple[BusinessOutcomeV1, ...]:
        projected: dict[str, BusinessOutcomeV1] = {}
        for row in self._evidence.list_for_tenant(tenant_id=tenant_id, limit=limit):
            if not self._is_outcome_record(row, business_id=business_id) or not _mapping(row.payload.get("business_outcome")):
                continue
            outcome = _project_record(row)
            if (prior := projected.get(outcome.outcome_id)) is not None and prior != outcome:
                raise BusinessOutcomeProjectionConflict("multiple canonical evidence rows disagree on outcome body")
            projected[outcome.outcome_id] = outcome
        return tuple(projected[key] for key in sorted(projected))

    def legacy_incomplete_count(self, *, tenant_id: str, business_id: str, limit: int = 1000) -> int:
        return sum(1 for row in self._evidence.list_for_tenant(tenant_id=tenant_id, limit=limit) if self._is_outcome_record(row, business_id=business_id) and not _mapping(row.payload.get("business_outcome")))


class BusinessOutcomeEventSpineProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _matches(self, record: EvidenceRecord, event_id: str) -> list[dict[str, Any]]:
        return [dict(raw) for raw in self._events.iter_events(tenant_id=record.tenant_id, start_ms=0, event_type=OUTCOME_OBSERVED_EVENT_TYPE) if str(raw.get("event_id") or "") == event_id]

    def project(self, record: EvidenceRecord) -> str | None:
        normalized = record.normalized()
        body = _mapping(normalized.payload.get("business_outcome"))
        if not body or body.get("schema_version") is None:
            return None
        outcome = _project_record(normalized)
        intent, correlation_id = _mapping(normalized.payload.get("action_intent")), None
        if intent:
            checks = ((intent.get("tenant_id"), outcome.tenant_id), (intent.get("business_id"), outcome.business_id), (intent.get("decision_id"), outcome.decision_id), (intent.get("intent_id"), outcome.intent_id))
            if int(intent.get("schema_version") or 0) != 1 or any(str(a or "") != str(b or "") for a, b in checks):
                raise BusinessOutcomeEventProjectionConflict("action intent identity conflicts with canonical outcome")
            correlation_id = str(intent.get("correlation_id") or "").strip() or None
        timestamp_ms, event_id = int(normalized.created_at.timestamp() * 1000), f"closed-loop-outcome:{normalized.evidence_id}"
        event_payload = {"schema_version": 1, "business_id": normalized.business_id, "occurred_at_ms": timestamp_ms, "recorded_at_ms": timestamp_ms, "causation_id": outcome.intent_id, "evidence_ids": [normalized.evidence_id], "outcome": outcome.as_dict()}
        goal_id = str(dict(normalized.labels).get("goal_id") or "").strip()
        if goal_id:
            event_payload["goal_id"] = goal_id
        event = {
            "event_id": event_id, "tenant_id": normalized.tenant_id, "source": _EVENT_SOURCE, "event_type": OUTCOME_OBSERVED_EVENT_TYPE,
            "timestamp_ms": timestamp_ms, "decision_id": outcome.decision_id, "correlation_id": correlation_id,
            "payload": event_payload,
        }
        matches = self._matches(normalized, event_id)
        if len(matches) > 1:
            raise BusinessOutcomeEventProjectionConflict("multiple Event Spine rows share one outcome projection id")
        if matches:
            if canonical_business_event_contract(matches[0]) != canonical_business_event_contract(event):
                raise BusinessOutcomeEventProjectionConflict("outcome Event Spine projection conflicts with canonical evidence")
            return event_id
        try:
            self._events.append_event(event)
        except Exception:
            matches = self._matches(normalized, event_id)
            if not matches or canonical_business_event_contract(matches[0]) != canonical_business_event_contract(event):
                raise
            return event_id
        matches = self._matches(normalized, event_id)
        if len(matches) != 1:
            raise RuntimeError("outcome Event Spine append did not become durable")
        if canonical_business_event_contract(matches[0]) != canonical_business_event_contract(event):
            raise BusinessOutcomeEventProjectionConflict("outcome Event Spine projection conflicts with canonical evidence")
        return event_id


__all__ = ["BusinessOutcomeBodyUnavailable", "BusinessOutcomeEvidenceProjector", "BusinessOutcomeEventProjectionConflict", "BusinessOutcomeEventSpineProjector", "BusinessOutcomeProjectionConflict", "CANON_BUSINESS_OUTCOME_EVIDENCE_PROJECTION", "CANON_BUSINESS_OUTCOME_EVENT_SPINE_PROJECTION", "OUTCOME_OBSERVED_EVENT_TYPE"]
