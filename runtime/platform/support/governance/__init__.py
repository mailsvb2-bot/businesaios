from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol


class ApprovalWorkflow:
    def approved(self, approvals: list[bool]) -> bool:
        return all(approvals) if approvals else False

@dataclass(frozen=True)
class AuditRecord:
    event_type: str
    payload: Mapping[str, Any]

class AuditWriterContract(Protocol):
    def write(self, payload: dict) -> None:
        ...

class AuditWriter:
    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def write(self, payload: dict) -> None:
        self._records.append(
            AuditRecord(
                event_type=str(payload.get("event_type", "unknown")),
                payload=dict(payload),
            )
        )

    def records(self) -> list[AuditRecord]:
        return list(self._records)

class AuditReader:
    def __init__(self, writer: AuditWriter) -> None:
        self._writer = writer

    def read_all(self):
        return self._writer.records()

class AuditLog:
    def __init__(self) -> None:
        self._writer = AuditWriter()
        self._reader = AuditReader(self._writer)

    def append(self, event_type: str, payload: dict) -> None:
        updated = dict(payload)
        updated["event_type"] = event_type
        self._writer.write(updated)

    def records(self):
        return self._reader.read_all()

@dataclass(frozen=True)
class ChangeRequest:
    request_id: str
    description: str

class ChangeReview:
    def approve(self, payload: dict) -> bool:
        return bool(payload.get("approved", False))

@dataclass(frozen=True)
class ComplianceRecord:
    control_name: str
    passed: bool

@dataclass(frozen=True)
class EvaluationReport:
    candidate_id: str
    metrics: Mapping[str, float]

@dataclass(frozen=True)
class GovernancePolicy:
    require_approval: bool = True
    require_reproducibility: bool = True
    require_audit_trail: bool = True

class GovernanceRegistry:
    def __init__(self) -> None:
        self._items: dict[str, dict] = {}

    def register(self, key: str, payload: dict) -> None:
        self._items[key] = dict(payload)

    def get(self, key: str) -> dict:
        return dict(self._items[key])

class IncidentReview:
    def classify(self, severity: str) -> dict[str, str]:
        return {"severity": severity}

@dataclass(frozen=True)
class LineageManifest:
    candidate_id: str
    parent_id: str | None

@dataclass(frozen=True)
class ModelCard:
    model_name: str
    intended_use: str

class Postmortem:
    def build(self, incident_id: str, summary: str) -> dict[str, str]:
        return {"incident_id": incident_id, "summary": summary}

@dataclass(frozen=True)
class PromotionReport:
    candidate_id: str
    approved: bool

class ReleasePolicy:
    def releasable(self, payload: dict) -> bool:
        required = (
            payload.get("evaluation_passed", False),
            payload.get("safety_passed", False),
            payload.get("approved", False),
            payload.get("reproducible", False),
        )
        return all(required)

class ReleaseReadiness:
    def ready(self, checks: dict[str, bool]) -> bool:
        return all(checks.values())

@dataclass(frozen=True)
class ReproducibilityManifest:
    code_version: str
    config: Mapping[str, Any]
    dataset_ids: tuple[str, ...]

@dataclass(frozen=True)
class RollbackReport:
    candidate_id: str
    rollback: bool

_GOVERNANCE_COMPAT_EXPORTS = {
    "approval_workflow": {"ApprovalWorkflow": f"{__name__}:ApprovalWorkflow"},
    "audit_log": {"AuditLog": f"{__name__}:AuditLog"},
    "audit_reader": {"AuditReader": f"{__name__}:AuditReader"},
    "audit_record": {"AuditRecord": f"{__name__}:AuditRecord"},
    "audit_writer": {"AuditWriter": f"{__name__}:AuditWriter"},
    "change_request": {"ChangeRequest": f"{__name__}:ChangeRequest"},
    "change_review": {"ChangeReview": f"{__name__}:ChangeReview"},
    "compliance_record": {"ComplianceRecord": f"{__name__}:ComplianceRecord"},
    "contracts": {"AuditWriterContract": f"{__name__}:AuditWriterContract"},
    "evaluation_report": {"EvaluationReport": f"{__name__}:EvaluationReport"},
    "governance_policy": {"GovernancePolicy": f"{__name__}:GovernancePolicy"},
    "governance_registry": {"GovernanceRegistry": f"{__name__}:GovernanceRegistry"},
    "incident_review": {"IncidentReview": f"{__name__}:IncidentReview"},
    "lineage_manifest": {"LineageManifest": f"{__name__}:LineageManifest"},
    "model_card": {"ModelCard": f"{__name__}:ModelCard"},
    "postmortem": {"Postmortem": f"{__name__}:Postmortem"},
    "promotion_report": {"PromotionReport": f"{__name__}:PromotionReport"},
    "release_policy": {"ReleasePolicy": f"{__name__}:ReleasePolicy"},
    "release_readiness": {"ReleaseReadiness": f"{__name__}:ReleaseReadiness"},
    "reproducibility_manifest": {"ReproducibilityManifest": f"{__name__}:ReproducibilityManifest"},
    "rollback_report": {"RollbackReport": f"{__name__}:RollbackReport"},
}

__all__ = [
    "ApprovalWorkflow",
    "AuditLog",
    "AuditReader",
    "AuditRecord",
    "AuditWriter",
    "AuditWriterContract",
    "ChangeRequest",
    "ChangeReview",
    "ComplianceRecord",
    "EvaluationReport",
    "GovernancePolicy",
    "GovernanceRegistry",
    "IncidentReview",
    "LineageManifest",
    "ModelCard",
    "Postmortem",
    "PromotionReport",
    "ReleasePolicy",
    "ReleaseReadiness",
    "ReproducibilityManifest",
    "RollbackReport",
]
