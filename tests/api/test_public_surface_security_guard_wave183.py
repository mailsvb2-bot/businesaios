from __future__ import annotations

from fastapi import APIRouter
from fastapi.testclient import TestClient

import adapters.api.fastapi.public_routes as public_routes_module
from adapters.api.fastapi.public_routes import register_public_api_routes
from entrypoints.api.action_models import ExecuteActionResponse
from entrypoints.api.health_models import HealthResponse
from entrypoints.api.request_context import RequestContext


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


class _ClientOutcomeHandlers:
    def __init__(self) -> None:
        self.select_calls = 0

    def select_package(self, *, now, request):
        self.select_calls += 1
        return {'status': 'selected', 'tenant_id': request.tenant_id, 'business_id': request.business_id}


def _client(guard, *, auth_bundle=None, client_outcome_handlers=None):
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
        auth_bundle=auth_bundle,
        client_outcome_handlers=client_outcome_handlers,
    )
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_public_execute_action_flows_through_security_guard():
    calls = []

    class Guard:
        def requires_external_auth(self, _route_path):
            return False

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
        def requires_external_auth(self, _route_path):
            return False

        def enforce(self, **kwargs):
            raise PermissionError('security_denied')

    client = _client(Guard())
    response = client.post('/business-memory/summary', json={'tenant_id': 'tenant-a', 'business_id': 'biz-1'})
    assert response.status_code == 403
    assert response.json()['detail'] == 'security_denied'


def test_client_outcome_write_route_fails_closed_without_auth_bundle():
    handlers = _ClientOutcomeHandlers()

    class Guard:
        def requires_external_auth(self, route_path):
            return route_path == '/client-outcome/select'

        def enforce(self, **kwargs):
            raise AssertionError('security guard must not run without configured perimeter auth')

    client = _client(Guard(), client_outcome_handlers=handlers)
    response = client.post('/client-outcome/select', json={'tenant_id': 'tenant-a', 'business_id': 'biz-a'})

    assert response.status_code == 403
    assert response.json()['detail'] == 'api_perimeter_auth_unconfigured'
    assert handlers.select_calls == 0


def test_client_outcome_write_route_threads_http_request_into_auth(monkeypatch):
    handlers = _ClientOutcomeHandlers()
    authorize_calls = []
    guard_calls = []
    auth_bundle = object()

    def fake_authorize_request(*, request, auth_bundle):
        authorize_calls.append((request, auth_bundle))
        return RequestContext.from_http_request(request).with_metadata(api_key_verified=True), object()

    monkeypatch.setattr(public_routes_module, 'authorize_request', fake_authorize_request)

    class Guard:
        def requires_external_auth(self, route_path):
            return route_path == '/client-outcome/select'

        def enforce(self, **kwargs):
            guard_calls.append(kwargs)
            assert kwargs['request_context'].metadata['api_key_verified'] is True
            return {'allowed': True}

    client = _client(Guard(), auth_bundle=auth_bundle, client_outcome_handlers=handlers)
    response = client.post('/client-outcome/select', json={'tenant_id': 'tenant-a', 'business_id': 'biz-a'})

    assert response.status_code == 200
    assert response.json()['status'] == 'selected'
    assert handlers.select_calls == 1
    assert len(authorize_calls) == 1
    assert authorize_calls[0][0].url.path == '/client-outcome/select'
    assert authorize_calls[0][1] is auth_bundle
    assert guard_calls and guard_calls[0]['route_path'] == '/client-outcome/select'
