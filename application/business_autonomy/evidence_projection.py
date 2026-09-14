from __future__ import annotations

from datetime import UTC, datetime

from application.business_autonomy.contracts import BusinessExecutionResult
from storage.evidence_store import EvidenceRecord, EvidenceStore

CANON_BUSINESS_AUTONOMY_EVIDENCE_PROJECTION = True


def _text(value: object) -> str:
    return str(value or "").strip()


def _payload(result: BusinessExecutionResult) -> dict:
    return {
        "message": result.message,
        "metrics": dict(result.metrics),
        "metadata": dict(result.metadata),
        "evidence": [
            {
                "event_type": item.event_type,
                "payload": dict(item.payload),
                "timestamp_utc": item.timestamp_utc,
                "source": item.source,
            }
            for item in result.evidence
        ],
    }


def _tenant_id(result: BusinessExecutionResult) -> str:
    return _text(result.metadata.get("tenant_id") or result.business_id or "global")


def project_business_autonomy_evidence(
    result: BusinessExecutionResult, *, created_at: datetime | None = None
) -> EvidenceRecord:
    timestamp = (created_at or datetime.now(UTC)).astimezone(UTC)
    source = _text(result.adapter_name) or "business_autonomy"
    decision_ref = _text(
        result.metadata.get("decision_id") or result.metadata.get("sovereign_decision_id")
    )
    action_ref = _text(result.metadata.get("action_id")) or _text(result.goal_id)
    derived_fact_ref = _text(
        result.metadata.get("derived_fact_ref") or result.metadata.get("semantic_state_id")
    )
    execution_ref = _text(result.execution_id)
    lineage = {
        "source": source,
        "normalization": f"business-autonomy-result:{execution_ref}",
        "action": action_ref,
        "outcome": execution_ref,
    }
    if derived_fact_ref:
        lineage["derived_fact"] = derived_fact_ref
    if decision_ref:
        lineage["decision"] = decision_ref
    refs = tuple(
        dict.fromkeys(
            value
            for value in (
                source,
                _text(result.business_id),
                _text(result.goal_id),
                derived_fact_ref,
                decision_ref,
                action_ref,
            )
            if value
        )
    )
    return EvidenceRecord(
        evidence_id=f"business-autonomy:{execution_ref}",
        tenant_id=_tenant_id(result),
        scope="business_autonomy",
        run_id=execution_ref,
        action_id=action_ref,
        action_type="business_autonomy_execution",
        verification_status=result.verdict.value,
        created_at=timestamp,
        source=source,
        source_type="business_autonomy_execution",
        business_id=_text(result.business_id),
        observed_at=timestamp,
        privacy_class="internal",
        retention_policy="business_execution_evidence",
        lineage=lineage,
        refs=refs,
        payload=_payload(result),
        labels={
            "business_id": _text(result.business_id),
            "goal_id": _text(result.goal_id),
            "verdict": result.verdict.value,
        },
    ).normalized_for_write()


def append_business_autonomy_evidence(
    *, backend: EvidenceStore, result: BusinessExecutionResult
) -> EvidenceRecord:
    tenant_id = _tenant_id(result)
    evidence_id = f"business-autonomy:{_text(result.execution_id)}"
    existing = backend.get(tenant_id=tenant_id, evidence_id=evidence_id)
    record = project_business_autonomy_evidence(
        result, created_at=None if existing is None else existing.created_at
    )
    if existing is not None:
        if existing != record:
            raise ValueError("business autonomy evidence replay conflicts with canonical evidence")
        return existing
    try:
        return backend.append(record)
    except ValueError as exc:
        current = backend.get(tenant_id=tenant_id, evidence_id=evidence_id)
        if current is not None:
            replay = project_business_autonomy_evidence(result, created_at=current.created_at)
            if current == replay:
                return current
        raise ValueError("business autonomy evidence replay conflicts with canonical evidence") from exc


__all__ = [
    "CANON_BUSINESS_AUTONOMY_EVIDENCE_PROJECTION",
    "append_business_autonomy_evidence",
    "project_business_autonomy_evidence",
]
