from __future__ import annotations

"""Final owner: entrypoints.api.governance_advanced_route_handlers."""

from application.governance.governance_service import GovernanceService
from entrypoints.api.governance_advanced_models import (
    BusinessMemoryGovernanceSummaryRequest,
    BusinessMemoryGovernanceSummaryResponse,
    DriftTrendRequest,
    DriftTrendResponse,
    JoinedHistoryRequest,
    JoinedHistoryResponse,
    PromoteScenarioBaselineRequest,
    PromoteScenarioBaselineResponse,
    PromotionEvidenceVerifyRequest,
    PromotionEvidenceVerifyResponse,
    RollbackRecommendationRequest,
    RollbackRecommendationResponse,
    RollbackTimelineRequest,
    RollbackTimelineResponse,
)

CANON_API_GOVERNANCE_ADVANCED_ROUTE_HANDLERS_FINAL_OWNER = True
CANON_API_GOVERNANCE_ADVANCED_ROUTE_HANDLERS = True


class GovernanceAdvancedRouteHandlers:
    def __init__(self) -> None:
        self._governance = GovernanceService.build_default()

    def rollback_recommendation(self, request: RollbackRecommendationRequest) -> RollbackRecommendationResponse:
        payload = self._governance.rollback_recommendation(
            baseline_name=request.baseline_name,
            candidate_run_id=request.candidate_run_id,
            fallback_run_ids=list(request.fallback_run_ids),
        )
        return RollbackRecommendationResponse(
            baseline_name=str(payload.get("baseline_name") or request.baseline_name),
            candidate_run_id=str(payload.get("candidate_run_id") or request.candidate_run_id),
            should_rollback=bool(payload.get("should_rollback")),
            confidence=float(payload.get("confidence") or 0.0),
            reason=str(payload.get("reason") or ""),
            recommended_run_id=payload.get("recommended_run_id"),
        )

    def joined_history(self, request: JoinedHistoryRequest) -> JoinedHistoryResponse:
        return JoinedHistoryResponse(payload=self._governance.joined_history(
            baseline_name=request.baseline_name,
            candidate_run_ids=list(request.candidate_run_ids),
        ))

    def verify_promotion_evidence(self, request: PromotionEvidenceVerifyRequest) -> PromotionEvidenceVerifyResponse:
        payload = self._governance.verify_promotion_evidence(baseline_name=request.baseline_name)
        return PromotionEvidenceVerifyResponse(
            ok=bool(payload.get("ok")),
            expected=dict(payload.get("expected") or {}),
            observed=dict(payload.get("observed") or {}),
        )

    def promote_best_for_scenario(self, request: PromoteScenarioBaselineRequest) -> PromoteScenarioBaselineResponse:
        payload = self._governance.promote_best_for_scenario(
            scenario=request.scenario,
            run_ids=list(request.run_ids),
            suffix=request.suffix,
            label=request.label,
            metadata={"via": "api"},
        )
        if not payload:
            return PromoteScenarioBaselineResponse()
        return PromoteScenarioBaselineResponse(
            baseline_name=str(payload.get("baseline_name") or ""),
            source_run_id=str(payload.get("source_run_id") or ""),
            goal=str(payload.get("goal") or ""),
            business_id=str(payload.get("business_id") or ""),
            tenant_id=str(payload.get("tenant_id") or ""),
            promoted_at_label=str(payload.get("promoted_at_label") or ""),
            metadata=dict(payload.get("metadata") or {}),
        )

    def rollback_timeline(self, request: RollbackTimelineRequest) -> RollbackTimelineResponse:
        return RollbackTimelineResponse(
            baseline_name=request.baseline_name,
            timeline_text=self._governance.rollback_timeline(baseline_name=request.baseline_name),
        )

    def drift_trend(self, request: DriftTrendRequest) -> DriftTrendResponse:
        payload = self._governance.drift_trend(
            baseline_name=request.baseline_name,
            candidate_run_ids=list(request.candidate_run_ids),
        )
        return DriftTrendResponse(
            baseline_name=str(payload.get("baseline_name") or request.baseline_name),
            samples=int(payload.get("samples") or 0),
            avg_goal_score_delta=float(payload.get("avg_goal_score_delta") or 0.0),
            high_count=int(payload.get("high_count") or 0),
            medium_count=int(payload.get("medium_count") or 0),
            low_count=int(payload.get("low_count") or 0),
            none_count=int(payload.get("none_count") or 0),
            summary=str(payload.get("summary") or ""),
        )

    def business_memory_summary(self, request: BusinessMemoryGovernanceSummaryRequest) -> BusinessMemoryGovernanceSummaryResponse:
        payload = self._governance.memory_summary(tenant_id=request.tenant_id, business_id=request.business_id)
        return BusinessMemoryGovernanceSummaryResponse(
            tenant_id=str(payload.get("tenant_id") or request.tenant_id),
            business_id=str(payload.get("business_id") or request.business_id),
            total_runs=int(payload.get("total_runs") or 0),
            completed_runs=int(payload.get("completed_runs") or 0),
            failed_runs=int(payload.get("failed_runs") or 0),
            average_goal_score=float(payload.get("average_goal_score") or 0.0),
            active_goals=list(payload.get("active_goals") or []),
            learned_preferences=dict(payload.get("learned_preferences") or {}),
            recurring_failures=list(payload.get("recurring_failures") or []),
            recurring_wins=list(payload.get("recurring_wins") or []),
            anti_patterns=list(payload.get("anti_patterns") or []),
            trends=dict(payload.get("trends") or {}),
        )
