from __future__ import annotations

"""Final owner: adapters.api.fastapi.public_routes."""

CANON_FASTAPI_PUBLIC_ROUTES_FINAL_OWNER = True


from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status

from adapters.api.fastapi.analytics_routes import register_analytics_routes
from entrypoints.api.action_models import ExecuteActionRequest, ExecuteActionResponse
from entrypoints.api.baseline_models import PromoteBaselineRequest, PromoteBaselineResponse, SelectBaselineRequest, SelectBaselineResponse
from entrypoints.api.business_memory_models import BusinessMemoryGetRequest, BusinessMemoryPatternsResponse, BusinessMemoryRecentRunsRequest, BusinessMemoryRecentRunsResponse, BusinessMemoryResponse, BusinessMemorySummaryRequest, BusinessMemorySummaryResponse
from entrypoints.api.client_outcome_admin_models import ClientOutcomeAdminSummaryRequest
from entrypoints.api.client_outcome_cycle_models import ExecuteClientOutcomeCycleRequest
from entrypoints.api.client_outcome_dispute_models import OpenClientOutcomeDisputeRequest, ReverseClientOutcomeDisputeRequest
from entrypoints.api.client_outcome_models import AmendClientOutcomeOrderRequest, SelectClientOutcomePackageRequest
from entrypoints.api.drift_models import DriftAuditRequest, DriftAuditResponse, RollbackBaselineRequest, RollbackBaselineResponse
from entrypoints.api.governance_advanced_models import BusinessMemoryGovernanceSummaryRequest, BusinessMemoryGovernanceSummaryResponse, DriftTrendRequest, DriftTrendResponse, JoinedHistoryRequest, JoinedHistoryResponse, PromoteScenarioBaselineRequest, PromoteScenarioBaselineResponse, PromotionEvidenceVerifyRequest, PromotionEvidenceVerifyResponse, RollbackRecommendationRequest, RollbackRecommendationResponse, RollbackTimelineRequest, RollbackTimelineResponse
from entrypoints.api.health_models import HealthResponse
from entrypoints.api.headless_models import ExecuteGoalRequest, ExecuteGoalResponse
from entrypoints.api.public_surface_security_guard import PublicSurfaceSecurityGuard
from entrypoints.api.request_context import RequestContext
from application.public_site.cta_intake import CTALandingIntakeService


def _cta_submit_response(result) -> dict:
    return {
        'ok': True,
        'intake_id': result.intake_id,
        'created_at': result.created_at,
        'tenant_id': result.tenant_id,
        'business_id': result.business_id,
        'user_id': result.user_id,
        'onboarding_status': result.onboarding_status,
        'next': {'ui_url': result.app_url},
        'next_actions': list(result.next_actions),
        'user_functionality': dict(result.user_functionality or {}),
        'admin_visibility': dict(result.admin_visibility or {}),
        'measurable_outcome': result.outcome,
        'write_actions_enabled': False,
        'approval_required_before_execution': True,
    }


def _cta_status_response(status_payload) -> dict:
    if not status_payload.found:
        return {
            'ok': False,
            'error': 'not_found',
            'intake_id': status_payload.intake_id,
        }
    return {
        'ok': True,
        'intake_id': status_payload.intake_id,
        'found': status_payload.found,
        'created_at': status_payload.created_at,
        'tenant_id': status_payload.tenant_id,
        'business_id': status_payload.business_id,
        'user_id': status_payload.user_id,
        'onboarding_status': status_payload.onboarding_status,
        'next_actions': list(status_payload.next_actions),
        'user_functionality': dict(status_payload.user_functionality or {}),
        'admin_visibility': dict(status_payload.admin_visibility or {}),
        'measurable_outcome': status_payload.outcome,
        'write_actions_enabled': False,
        'approval_required_before_execution': True,
    }


def register_public_api_routes(
    *,
    router: APIRouter,
    dependency_container,
    health_handler,
    handlers,
    headless_handlers,
    governance_handlers,
    business_memory_handlers,
    governance_advanced_handlers,
    security_guard: PublicSurfaceSecurityGuard,
    analytics_handlers=None,
    client_outcome_handlers=None,
    economic_handlers=None,
) -> None:

    def enforce_public_security(*, route_path: str, request_context: RequestContext, body: dict | None = None) -> None:
        try:
            security_guard.enforce(route_path=route_path, request_context=request_context, body=body)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    def _body(payload) -> dict | None:
        model_dump = getattr(payload, 'model_dump', None)
        if callable(model_dump):
            return model_dump()
        if isinstance(payload, dict):
            return payload
        return None

    @router.get('/health', response_model=HealthResponse, tags=['system'])
    @router.get('/healthz', response_model=HealthResponse, tags=['system'])
    def health() -> HealthResponse:
        return health_handler.health()

    @router.get('/readyz', response_model=HealthResponse, tags=['system'])
    def readiness() -> HealthResponse:
        return health_handler.readiness()

    @router.get('/storagez', response_model=HealthResponse, tags=['system'])
    def storage_readiness() -> HealthResponse:
        return health_handler.storage()

    @router.get('/executionz', response_model=HealthResponse, tags=['system'])
    def execution_readiness() -> HealthResponse:
        return health_handler.execution()

    @router.post('/actions/execute', response_model=ExecuteActionResponse)
    async def execute_action(http_request: Request, request: ExecuteActionRequest) -> ExecuteActionResponse:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/actions/execute'})
        enforce_public_security(route_path='/actions/execute', request_context=request_context, body=request.model_dump())
        idempotency_key = http_request.headers.get('x-idempotency-key') or http_request.headers.get('idempotency-key')
        action_id = http_request.headers.get('x-action-id') or http_request.headers.get('action-id')
        return handlers.execute_action(
            request,
            request_context=request_context,
            idempotency_key=idempotency_key,
            action_id=action_id,
        )

    @router.post('/goals/execute', response_model=ExecuteGoalResponse)
    def execute_goal(http_request: Request, request: ExecuteGoalRequest) -> ExecuteGoalResponse:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/goals/execute'})
        enforce_public_security(route_path='/goals/execute', request_context=request_context, body=request.model_dump())
        return headless_handlers.execute_goal(request)

    @router.post('/baselines/promote', response_model=PromoteBaselineResponse)
    def promote_baseline(http_request: Request, request: PromoteBaselineRequest) -> PromoteBaselineResponse:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/baselines/promote'})
        enforce_public_security(route_path='/baselines/promote', request_context=request_context, body=request.model_dump())
        return governance_handlers.promote_baseline(request)

    @router.post('/baselines/select', response_model=SelectBaselineResponse)
    def select_baseline(http_request: Request, request: SelectBaselineRequest) -> SelectBaselineResponse:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/baselines/select'})
        enforce_public_security(route_path='/baselines/select', request_context=request_context, body=request.model_dump())
        return governance_handlers.select_baseline(request)

    @router.post('/drift/audit', response_model=DriftAuditResponse)
    def audit_drift(http_request: Request, request: DriftAuditRequest) -> DriftAuditResponse:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/drift/audit'})
        enforce_public_security(route_path='/drift/audit', request_context=request_context, body=request.model_dump())
        return governance_handlers.audit_drift(request)

    @router.post('/baselines/rollback', response_model=RollbackBaselineResponse)
    def rollback_baseline(http_request: Request, request: RollbackBaselineRequest) -> RollbackBaselineResponse:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/baselines/rollback'})
        enforce_public_security(route_path='/baselines/rollback', request_context=request_context, body=request.model_dump())
        return governance_handlers.rollback_baseline(request)

    @router.post('/business-memory/get', response_model=BusinessMemoryResponse)
    def get_business_memory(http_request: Request, request: BusinessMemoryGetRequest) -> BusinessMemoryResponse:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/business-memory/get'})
        enforce_public_security(route_path='/business-memory/get', request_context=request_context, body=request.model_dump())
        return business_memory_handlers.get_memory(request)

    @router.post('/business-memory/summary', response_model=BusinessMemorySummaryResponse)
    def get_business_memory_summary(http_request: Request, request: BusinessMemorySummaryRequest) -> BusinessMemorySummaryResponse:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/business-memory/summary'})
        enforce_public_security(route_path='/business-memory/summary', request_context=request_context, body=request.model_dump())
        return business_memory_handlers.get_summary(request)

    @router.post('/business-memory/recent-runs', response_model=BusinessMemoryRecentRunsResponse)
    def get_business_memory_recent_runs(http_request: Request, request: BusinessMemoryRecentRunsRequest) -> BusinessMemoryRecentRunsResponse:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/business-memory/recent-runs'})
        enforce_public_security(route_path='/business-memory/recent-runs', request_context=request_context, body=request.model_dump())
        return business_memory_handlers.get_recent_runs(request)

    @router.post('/business-memory/failures', response_model=BusinessMemoryPatternsResponse)
    def get_business_memory_failures(http_request: Request, request: BusinessMemorySummaryRequest) -> BusinessMemoryPatternsResponse:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/business-memory/failures'})
        enforce_public_security(route_path='/business-memory/failures', request_context=request_context, body=request.model_dump())
        return business_memory_handlers.get_failures(request)

    @router.post('/business-memory/wins', response_model=BusinessMemoryPatternsResponse)
    def get_business_memory_wins(http_request: Request, request: BusinessMemorySummaryRequest) -> BusinessMemoryPatternsResponse:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/business-memory/wins'})
        enforce_public_security(route_path='/business-memory/wins', request_context=request_context, body=request.model_dump())
        return business_memory_handlers.get_wins(request)

    @router.post('/governance/rollback-recommendation', response_model=RollbackRecommendationResponse)
    def rollback_recommendation(http_request: Request, request: RollbackRecommendationRequest) -> RollbackRecommendationResponse:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/governance/rollback-recommendation'})
        enforce_public_security(route_path='/governance/rollback-recommendation', request_context=request_context, body=request.model_dump())
        return governance_advanced_handlers.rollback_recommendation(request)

    @router.post('/governance/joined-history', response_model=JoinedHistoryResponse)
    def joined_history(http_request: Request, request: JoinedHistoryRequest) -> JoinedHistoryResponse:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/governance/joined-history'})
        enforce_public_security(route_path='/governance/joined-history', request_context=request_context, body=request.model_dump())
        return governance_advanced_handlers.joined_history(request)

    @router.post('/governance/verify-promotion-evidence', response_model=PromotionEvidenceVerifyResponse)
    def verify_promotion_evidence(http_request: Request, request: PromotionEvidenceVerifyRequest) -> PromotionEvidenceVerifyResponse:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/governance/verify-promotion-evidence'})
        enforce_public_security(route_path='/governance/verify-promotion-evidence', request_context=request_context, body=request.model_dump())
        return governance_advanced_handlers.verify_promotion_evidence(request)

    @router.post('/governance/promote-scenario', response_model=PromoteScenarioBaselineResponse)
    def promote_scenario_baseline(http_request: Request, request: PromoteScenarioBaselineRequest) -> PromoteScenarioBaselineResponse:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/governance/promote-scenario'})
        enforce_public_security(route_path='/governance/promote-scenario', request_context=request_context, body=request.model_dump())
        return governance_advanced_handlers.promote_best_for_scenario(request)

    @router.post('/governance/rollback-timeline', response_model=RollbackTimelineResponse)
    def governance_rollback_timeline(http_request: Request, request: RollbackTimelineRequest) -> RollbackTimelineResponse:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/governance/rollback-timeline'})
        enforce_public_security(route_path='/governance/rollback-timeline', request_context=request_context, body=request.model_dump())
        return governance_advanced_handlers.rollback_timeline(request)

    @router.post('/governance/drift-trend', response_model=DriftTrendResponse)
    def governance_drift_trend(http_request: Request, request: DriftTrendRequest) -> DriftTrendResponse:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/governance/drift-trend'})
        enforce_public_security(route_path='/governance/drift-trend', request_context=request_context, body=request.model_dump())
        return governance_advanced_handlers.drift_trend(request)

    @router.post('/cta/intake', tags=['public'])
    def submit_cta_intake(http_request: Request, payload: dict) -> dict:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/cta/intake'})
        enforce_public_security(route_path='/cta/intake', request_context=request_context, body=payload)
        service = CTALandingIntakeService()
        return _cta_submit_response(service.submit(payload))

    @router.get('/cta/intake/{intake_id}', tags=['public'])
    def cta_intake_status(http_request: Request, intake_id: str) -> dict:
        request_context = RequestContext.from_http_request(http_request, metadata={'route': '/cta/intake/status'})
        enforce_public_security(route_path='/cta/intake/status', request_context=request_context)
        service = CTALandingIntakeService()
        return _cta_status_response(service.status(intake_id))

    if analytics_handlers is not None:
        register_analytics_routes(router=router, analytics_handlers=analytics_handlers, enforce_public_security=enforce_public_security)
