from __future__ import annotations

"""Final owner: entrypoints.api.governance_route_handlers."""

CANON_API_GOVERNANCE_ROUTE_HANDLERS_FINAL_OWNER = True
CANON_API_GOVERNANCE_ROUTE_HANDLERS_NO_FASTAPI_COUPLING = True

from application.governance.governance_service import GovernanceService
from entrypoints.api.baseline_models import (
    PromoteBaselineRequest,
    PromoteBaselineResponse,
    SelectBaselineRequest,
    SelectBaselineResponse,
)
from entrypoints.api.drift_models import (
    DriftAuditRequest,
    DriftAuditResponse,
    RollbackBaselineRequest,
    RollbackBaselineResponse,
)


class GovernanceRouteHandlers:
    def __init__(self) -> None:
        self._governance = GovernanceService.build_default()

    def promote_baseline(self, request: PromoteBaselineRequest) -> PromoteBaselineResponse:
        payload = self._governance.promote_baseline(
            baseline_name=request.baseline_name,
            run_id=request.run_id,
            label=request.label,
            metadata={"via": "api"},
        )
        return PromoteBaselineResponse(
            baseline_name=payload["baseline_name"],
            source_run_id=payload["source_run_id"],
            goal=payload["goal"],
            business_id=payload["business_id"],
            tenant_id=payload["tenant_id"],
            promoted_at_label=payload["promoted_at_label"],
            metadata=dict(payload.get("metadata") or {}),
        )

    def select_baseline(self, request: SelectBaselineRequest) -> SelectBaselineResponse:
        selected = self._governance.select_baseline(run_ids=request.run_ids)
        if not selected:
            return SelectBaselineResponse()
        feedback = dict(selected.get("final_feedback") or {})
        return SelectBaselineResponse(
            selected_run_id=str(selected.get("run_id") or ""),
            completed=bool(selected.get("completed")),
            stop_reason=str(selected.get("stop_reason") or ""),
            goal_score=float(feedback.get("goal_score") or 0.0),
        )

    def audit_drift(self, request: DriftAuditRequest) -> DriftAuditResponse:
        payload = self._governance.audit_drift(
            baseline_name=request.baseline_name,
            candidate_run_id=request.candidate_run_id,
        )
        return DriftAuditResponse(
            severity=payload["severity"],
            goal_score_delta=float(payload["goal_score_delta"]),
            report_text=payload["report_text"],
        )

    def rollback_baseline(self, request: RollbackBaselineRequest) -> RollbackBaselineResponse:
        payload = self._governance.rollback_baseline(
            baseline_name=request.baseline_name,
            fallback_run_id=request.fallback_run_id,
            reason=request.reason,
            metadata={"via": "api"},
        )
        return RollbackBaselineResponse(
            baseline_name=payload["baseline_name"],
            source_run_id=payload["source_run_id"],
            rollback_reason=str((payload.get("metadata") or {}).get("rollback_reason") or request.reason),
        )
