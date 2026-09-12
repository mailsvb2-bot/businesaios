from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .contracts import BuildRequest
from .owner_projection import blueprint_card, opportunity_card, roi_card
from .ports import (
    BlueprintLedger,
    ProcessDecisionBindingStore,
    ProcessEvidenceRecorder,
    TrustedMeasurementSource,
    TrustedProcessEvidenceSource,
)
from .service import DiscoverBuildMeasureService


class ProcessWorkspaceError(RuntimeError):
    def __init__(self, code: str, status_code: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _clean_sequence(value: Any, *, code: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ProcessWorkspaceError(code)
    return tuple(str(item).strip() for item in value if str(item).strip())


@dataclass(frozen=True)
class CanonicalProcessWorkspace:
    """Fail-closed owner facade over canonical evidence and ledgers."""

    service: DiscoverBuildMeasureService
    evidence_source: TrustedProcessEvidenceSource
    blueprint_ledger: BlueprintLedger
    measurement_source: TrustedMeasurementSource
    evidence_recorder: ProcessEvidenceRecorder | None = None
    decision_binding_store: ProcessDecisionBindingStore | None = None

    def record_observation(self, *, tenant_id: str, business_id: str, user_id: str | None, payload: Mapping[str, Any], request_id: str | None = None) -> dict[str, object]:
        if self.evidence_recorder is None:
            raise ProcessWorkspaceError("process_evidence_recorder_unavailable", 503)
        try:
            item = self.evidence_recorder.record_owner_observation(
                tenant_id=tenant_id, business_id=business_id, user_id=user_id, payload=dict(payload), request_id=request_id,
            )
        except (TypeError, ValueError) as exc:
            raise ProcessWorkspaceError(str(exc) or "invalid_process_observation", 422) from exc
        return {
            "status": "recorded", "evidence_id": item.evidence_id, "process_key": item.process_key,
            "occurred_at": item.occurred_at.isoformat(), "source": item.source, "trust_weight": item.trust_weight,
        }

    def discover(self, *, tenant_id: str, business_id: str) -> dict[str, object]:
        observations = self.evidence_source.load_process_observations(tenant_id=tenant_id, business_id=business_id)
        if not observations:
            return {"business_id": business_id, "opportunities": [], "rejected": [], "status": "insufficient_process_evidence"}
        try:
            report = self.service.discover(observations)
        except ValueError as exc:
            raise ProcessWorkspaceError("invalid_or_conflicting_process_evidence", 409) from exc
        return {
            "business_id": business_id,
            "generated_at": report.generated_at.isoformat(),
            "opportunities": [opportunity_card(item) for item in report.opportunities],
            "rejected": [opportunity_card(item) for item in report.rejected_processes],
            "status": "ok",
        }

    def build(self, *, tenant_id: str, business_id: str, opportunity_id: str, payload: Mapping[str, Any]) -> dict[str, object]:
        observations = self.evidence_source.load_process_observations(tenant_id=tenant_id, business_id=business_id)
        if not observations:
            raise ProcessWorkspaceError("process_evidence_not_found", 404)
        try:
            report = self.service.discover(observations)
        except ValueError as exc:
            raise ProcessWorkspaceError("invalid_or_conflicting_process_evidence", 409) from exc
        opportunity = next((item for item in report.opportunities if item.opportunity_id == opportunity_id), None)
        if opportunity is None:
            raise ProcessWorkspaceError("eligible_opportunity_not_found", 404)
        try:
            request = BuildRequest(
                owner_goal=str(payload.get("owner_goal") or "").strip(),
                requested_capabilities=_clean_sequence(
                    payload.get("requested_capabilities"), code="requested_capabilities_must_be_array"
                ),
                expected_coverage=float(payload.get("expected_coverage", 0.5)),
                setup_cost_minor=int(payload["setup_cost_minor"]) if payload.get("setup_cost_minor") is not None else None,
                currency=str(payload.get("currency") or "").strip() or None,
                success_metrics=_clean_sequence(payload.get("success_metrics"), code="success_metrics_must_be_array"),
            )
            blueprint = self.service.build(opportunity, request)
        except ProcessWorkspaceError:
            raise
        except (TypeError, ValueError) as exc:
            raise ProcessWorkspaceError("invalid_blueprint_request") from exc
        self.blueprint_ledger.save(blueprint=blueprint, baseline=opportunity.baseline)
        advisory = self.service.decisioncore_payload(blueprint)
        return {
            "blueprint": blueprint_card(blueprint),
            "decisioncore_advisory": advisory,
            "decisioncore_goal": str(advisory["objective"]),
            "execution_created": False,
            "approval_created": False,
            "measurement_ready": False,
        }


    def decision_request(self, *, tenant_id: str, business_id: str, blueprint_id: str) -> dict[str, object]:
        record = self.blueprint_ledger.get(tenant_id=tenant_id, business_id=business_id, blueprint_id=blueprint_id)
        if record is None:
            raise ProcessWorkspaceError("blueprint_not_found", 404)
        blueprint, baseline = record
        if blueprint.tenant_id != tenant_id or blueprint.business_id != business_id:
            raise ProcessWorkspaceError("blueprint_scope_mismatch", 403)
        if blueprint.executable:
            raise ProcessWorkspaceError("blueprint_integrity_failed", 409)
        if not baseline.evidence_fingerprint or baseline.evidence_fingerprint != blueprint.baseline_fingerprint:
            raise ProcessWorkspaceError("blueprint_baseline_fingerprint_mismatch", 409)
        advisory = self.service.decisioncore_payload(blueprint)
        return {
            "blueprint_id": blueprint.blueprint_id,
            "baseline_fingerprint": blueprint.baseline_fingerprint,
            "objective": str(advisory["objective"]),
            "metadata": dict(advisory["metadata"]),
        }

    def bind_decision_result(self, *, tenant_id: str, business_id: str, blueprint_id: str, result: Mapping[str, Any]) -> dict[str, object]:
        record = self.blueprint_ledger.get(tenant_id=tenant_id, business_id=business_id, blueprint_id=blueprint_id)
        if record is None:
            raise ProcessWorkspaceError("blueprint_not_found", 404)
        blueprint, _ = record
        if self.decision_binding_store is None:
            raise ProcessWorkspaceError("process_decision_binding_unavailable", 503)
        try:
            binding = self.decision_binding_store.record_decision_result(
                tenant_id=tenant_id, business_id=business_id, blueprint=blueprint, result=dict(result),
            )
        except (TypeError, ValueError) as exc:
            raise ProcessWorkspaceError(str(exc) or "process_decision_binding_failed", 409) from exc
        return dict(binding)

    def measure(self, *, tenant_id: str, business_id: str, blueprint_id: str) -> dict[str, object]:
        record = self.blueprint_ledger.get(tenant_id=tenant_id, business_id=business_id, blueprint_id=blueprint_id)
        if record is None:
            raise ProcessWorkspaceError("blueprint_not_found", 404)
        blueprint, baseline = record
        if blueprint.tenant_id != tenant_id or blueprint.business_id != business_id:
            raise ProcessWorkspaceError("blueprint_scope_mismatch", 403)
        intervention = self.measurement_source.load_intervention_proof(
            tenant_id=tenant_id, business_id=business_id, blueprint=blueprint
        )
        if intervention is None or not intervention.server_validated or not intervention.execution_verified:
            return {
                "blueprint_id": blueprint_id,
                "status": "intervention_not_verified",
                "measurement": None,
                "measurement_ready": False,
            }
        after = self.measurement_source.load_after_observations(
            tenant_id=tenant_id, business_id=business_id, blueprint=blueprint, intervention=intervention
        )
        if not after:
            return {
                "blueprint_id": blueprint_id,
                "status": "insufficient_after_evidence",
                "measurement": None,
                "measurement_ready": False,
            }
        spend = self.measurement_source.load_intervention_spend(
            tenant_id=tenant_id, business_id=business_id, blueprint=blueprint, intervention=intervention
        )
        comparison = self.measurement_source.load_comparison_evidence(
            tenant_id=tenant_id, business_id=business_id, blueprint=blueprint, intervention=intervention
        )
        try:
            report = self.service.measure(
                blueprint=blueprint,
                baseline=baseline,
                intervention=intervention,
                after_observations=after,
                spend=spend,
                comparison=comparison,
            )
        except ValueError as exc:
            raise ProcessWorkspaceError("measurement_evidence_integrity_failed", 409) from exc
        return {
            "blueprint_id": blueprint_id,
            "status": "ok",
            "measurement": roi_card(report),
            "measurement_ready": True,
        }
