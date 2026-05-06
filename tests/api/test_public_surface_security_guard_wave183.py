from __future__ import annotations

from fastapi import APIRouter
from fastapi.testclient import TestClient

from adapters.api.fastapi.public_routes import register_public_api_routes
from entrypoints.api.action_models import ExecuteActionResponse
from entrypoints.api.health_models import HealthResponse


class _HealthHandler:
    def health(self) -> HealthResponse:
        return HealthResponse(status='ok', startup_audit_events=[])

    def readiness(self) -> HealthResponse:
        return HealthResponse(status='ok', startup_audit_events=[])


class _Handlers:
    def execute_action(self, request, *, request_context=None, idempotency_key=None, action_id=None):
        return ExecuteActionResponse(status='ok', action_type=request.action_type, details={'request_path': request_context.metadata.get('path')})


class _HeadlessHandlers:
    def execute_goal(self, request):
        return {'goal': request.goal, 'business_id': request.business_id, 'tenant_id': request.tenant_id, 'completed': True, 'stop_reason': 'done', 'steps': [], 'final_feedback': {}, 'capability_view': {}}


class _GovernanceHandlers:
    def promote_baseline(self, request):
        return {'baseline_name': request.baseline_name, 'source_run_id': request.run_id, 'goal': 'g', 'business_id': 'b', 'tenant_id': 'tenant-a', 'promoted_at_label': request.label, 'metadata': {}}

    def select_baseline(self, request):
        return {'selected_run_id': request.run_ids[0], 'completed': True, 'stop_reason': 'ok', 'goal_score': 1.0}

    def audit_drift(self, request):
        return {'severity': 'low', 'goal_score_delta': 0.1, 'report_text': 'ok'}

    def rollback_baseline(self, request):
        return {'baseline_name': request.baseline_name, 'source_run_id': request.fallback_run_id, 'metadata': {'rollback_reason': request.reason}}


class _BusinessMemoryHandlers:
    def get_memory(self, request):
        return {'payload': {'tenant_id': request.tenant_id, 'business_id': request.business_id}}

    def get_summary(self, request):
        return {'tenant_id': request.tenant_id, 'business_id': request.business_id, 'total_runs': 1, 'completed_runs': 1, 'failed_runs': 0, 'average_goal_score': 1.0, 'active_goals': [], 'learned_preferences': {}, 'recurring_failures': [], 'recurring_wins': [], 'anti_patterns': [], 'trends': {}}

    def get_recent_runs(self, request):
        return {'runs': []}

    def get_failures(self, request):
        return {'patterns': []}

    def get_wins(self, request):
        return {'patterns': []}


class _GovernanceAdvancedHandlers:
    def rollback_recommendation(self, request):
        return {'baseline_name': request.baseline_name, 'candidate_run_id': request.candidate_run_id, 'should_rollback': False, 'confidence': 0.5, 'reason': 'stable', 'recommended_run_id': None}

    def joined_history(self, request):
        return {'payload': {'baseline_name': request.baseline_name}}

    def verify_promotion_evidence(self, request):
        return {'ok': True, 'expected': {}, 'observed': {}}

    def promote_best_for_scenario(self, request):
        return {'baseline_name': 'base', 'source_run_id': request.run_ids[0], 'goal': 'g', 'business_id': 'b', 'tenant_id': 'tenant-a', 'promoted_at_label': request.label, 'metadata': {}}

    def rollback_timeline(self, request):
        return {'baseline_name': request.baseline_name, 'timeline_text': 'timeline'}

    def drift_trend(self, request):
        return {'baseline_name': request.baseline_name, 'samples': 1, 'avg_goal_score_delta': 0.0, 'high_count': 0, 'medium_count': 0, 'low_count': 1, 'none_count': 0, 'summary': 'ok'}

    def business_memory_summary(self, request):
        return {'tenant_id': request.tenant_id, 'business_id': request.business_id, 'total_runs': 1, 'completed_runs': 1, 'failed_runs': 0, 'average_goal_score': 1.0, 'active_goals': [], 'learned_preferences': {}, 'recurring_failures': [], 'recurring_wins': [], 'anti_patterns': [], 'trends': {}}


def _client(guard):
    router = APIRouter()
    register_public_api_routes(
        router=router,
        dependency_container=None,
        health_handler=_HealthHandler(),
        handlers=_Handlers(),
        headless_handlers=_HeadlessHandlers(),
        governance_handlers=_GovernanceHandlers(),
        business_memory_handlers=_BusinessMemoryHandlers(),
        governance_advanced_handlers=_GovernanceAdvancedHandlers(),
        security_guard=guard,
    )
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_public_execute_action_flows_through_security_guard():
    calls = []

    class Guard:
        def enforce(self, **kwargs):
            calls.append(kwargs)
            return {'allowed': True}

    client = _client(Guard())
    response = client.post('/actions/execute', json={'action_type': 'launch', 'payload': {'tenant_id': 'tenant-a'}}, headers={'x-request-id': 'req-1'})
    assert response.status_code == 200
    assert response.json()['details']['request_path'] == '/actions/execute'
    assert calls and calls[0]['route_path'] == '/actions/execute'
    assert calls[0]['request_context'].metadata['path'] == '/actions/execute'


def test_business_memory_summary_denied_when_security_guard_blocks():
    class Guard:
        def enforce(self, **kwargs):
            raise PermissionError('security_denied')

    client = _client(Guard())
    response = client.post('/business-memory/summary', json={'tenant_id': 'tenant-a', 'business_id': 'biz-1'})
    assert response.status_code == 403
    assert response.json()['detail'] == 'security_denied'
