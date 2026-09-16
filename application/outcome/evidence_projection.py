from __future__ import annotations

from collections.abc import Mapping

from contracts.business_outcome import BusinessOutcomeV1
from storage.evidence_store import EvidenceRecord, EvidenceStore

CANON_BUSINESS_OUTCOME_EVIDENCE_PROJECTION = True


class BusinessOutcomeBodyUnavailable(LookupError):
    """A canonical outcome lineage exists, but its full body is unavailable."""


class BusinessOutcomeProjectionConflict(ValueError):
    """Persisted outcome body conflicts with canonical evidence identity."""


def _mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _feedback_from_body(body: Mapping[str, object]) -> dict[str, object]:
    return {
        "attempted": bool(body.get("attempted")),
        "executed": bool(body.get("executed")),
        "verified": bool(body.get("verified")),
        "verification_status": str(body.get("evidence_status") or "unknown"),
        "goal_evaluation": {
            "achieved": bool(body.get("goal_achieved")),
            "terminal": bool(body.get("goal_terminal")),
            "completion_ratio": body.get("completion_ratio"),
            "success_confidence": body.get("success_confidence"),
        },
        "revenue_outcome": {
            "revenue_amount": body.get("revenue_amount"),
            "verified": bool(body.get("revenue_verified")),
        },
        "normalized_outcome": _mapping(body.get("metrics")),
        "execution_feedback": {
            "source_of_truth": str(body.get("source_of_truth") or "feedback_contract"),
        },
        "external_refs": list(body.get("external_refs") or ()),
        "evidence_status": str(body.get("evidence_status") or "unknown"),
    }


def _project_body(body: Mapping[str, object]) -> BusinessOutcomeV1:
    required = (
        "tenant_id", "business_id", "run_id", "intent_id", "decision_id",
        "action_id", "action_type", "goal", "status", "outcome_id",
    )
    if any(not str(body.get(name) or "").strip() for name in required):
        raise BusinessOutcomeProjectionConflict("business outcome body is incomplete")
    outcome = BusinessOutcomeV1.from_feedback(
        tenant_id=str(body["tenant_id"]),
        business_id=str(body["business_id"]),
        run_id=str(body["run_id"]),
        intent_id=str(body["intent_id"]),
        decision_id=str(body["decision_id"]),
        action_id=str(body["action_id"]),
        action_type=str(body["action_type"]),
        goal=str(body["goal"]),
        status=str(body["status"]),
        feedback=_feedback_from_body(body),
        evidence_refs=tuple(str(item) for item in body.get("evidence_refs") or ()),
        derived_fact_ref=str(body.get("derived_fact_ref") or ""),
    )
    if int(body.get("schema_version") or 0) != outcome.schema_version:
        raise BusinessOutcomeProjectionConflict("business outcome schema version conflicts")
    if outcome.as_dict() != dict(body):
        raise BusinessOutcomeProjectionConflict("business outcome body conflicts with canonical contract")
    return outcome


def _validate_record(record: EvidenceRecord, outcome: BusinessOutcomeV1) -> None:
    lineage = dict(record.lineage)
    checks = (
        (record.tenant_id, outcome.tenant_id, "tenant"),
        (record.business_id, outcome.business_id, "business"),
        (record.run_id, outcome.run_id, "run"),
        (record.action_id or "", outcome.action_id, "action"),
        (lineage.get("outcome", ""), outcome.outcome_id, "outcome"),
        (lineage.get("decision", ""), outcome.decision_id, "decision"),
    )
    for actual, expected, label in checks:
        if str(actual or "") != str(expected or ""):
            raise BusinessOutcomeProjectionConflict(f"business outcome {label} identity conflicts with evidence")
    derived = str(lineage.get("derived_fact") or "")
    if derived and derived != outcome.derived_fact_ref:
        raise BusinessOutcomeProjectionConflict("business outcome derived fact conflicts with evidence")


class BusinessOutcomeEvidenceProjector:
    """Read-only BusinessOutcomeV1 projection over the canonical EvidenceStore."""

    def __init__(self, evidence_store: EvidenceStore) -> None:
        self._evidence = evidence_store

    @staticmethod
    def _is_outcome_record(record: EvidenceRecord, *, business_id: str) -> bool:
        return (
            record.scope == "closed_loop"
            and record.source_type == "closed_loop_verification"
            and record.business_id == str(business_id)
            and bool(str(record.lineage.get("outcome") or ""))
        )
    def _project_record(self, record: EvidenceRecord) -> BusinessOutcomeV1:
        body = _mapping(record.payload.get("business_outcome"))
        if not body:
            raise BusinessOutcomeBodyUnavailable(
                f"business outcome body unavailable for {record.lineage.get('outcome', '')}"
            )
        outcome = _project_body(body)
        _validate_record(record, outcome)
        return outcome

    def get(
        self, *, tenant_id: str, business_id: str, outcome_id: str, limit: int = 1000
    ) -> BusinessOutcomeV1:
        target = str(outcome_id or "").strip()
        if not target:
            raise ValueError("outcome_id is required")
        matches = [
            row for row in self._evidence.list_for_tenant(tenant_id=tenant_id, limit=limit)
            if self._is_outcome_record(row, business_id=business_id)
            and str(row.lineage.get("outcome") or "") == target
            and bool(_mapping(row.payload.get("business_outcome")))
        ]
        if not matches:
            raise LookupError(f"business outcome not found: {target}")
        projected = tuple(self._project_record(row) for row in matches)
        first = projected[0]
        if any(item != first for item in projected[1:]):
            raise BusinessOutcomeProjectionConflict("multiple canonical evidence rows disagree on outcome body")
        return first

    def list_for_business(
        self, *, tenant_id: str, business_id: str, limit: int = 1000
    ) -> tuple[BusinessOutcomeV1, ...]:
        rows = (
            row for row in self._evidence.list_for_tenant(tenant_id=tenant_id, limit=limit)
            if self._is_outcome_record(row, business_id=business_id)
        )
        projected: dict[str, BusinessOutcomeV1] = {}
        for row in rows:
            if not _mapping(row.payload.get("business_outcome")):
                continue
            outcome = self._project_record(row)
            prior = projected.get(outcome.outcome_id)
            if prior is not None and prior != outcome:
                raise BusinessOutcomeProjectionConflict("multiple canonical evidence rows disagree on outcome body")
            projected[outcome.outcome_id] = outcome
        return tuple(projected[key] for key in sorted(projected))

    def legacy_incomplete_count(
        self, *, tenant_id: str, business_id: str, limit: int = 1000
    ) -> int:
        """Count retained lineage-only rows that predate full BusinessOutcome bodies."""
        return sum(
            1
            for row in self._evidence.list_for_tenant(tenant_id=tenant_id, limit=limit)
            if self._is_outcome_record(row, business_id=business_id)
            and not _mapping(row.payload.get("business_outcome"))
        )


__all__ = [
    "BusinessOutcomeBodyUnavailable",
    "BusinessOutcomeEvidenceProjector",
    "BusinessOutcomeProjectionConflict",
    "CANON_BUSINESS_OUTCOME_EVIDENCE_PROJECTION",
]
