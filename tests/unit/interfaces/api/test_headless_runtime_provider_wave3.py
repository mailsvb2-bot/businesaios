from __future__ import annotations

from interfaces.api.business_memory_models import BusinessMemorySummaryRequest
from interfaces.api.business_memory_route_handlers import build_business_memory_route_handlers
from interfaces.api.headless_models import ExecuteGoalRequest
from interfaces.api.headless_route_handlers import build_headless_route_handlers
from interfaces.api.headless_runtime_provider import build_headless_runtime_provider


class _StubBusinessMemoryQuery:
    def get_memory(self, *, tenant_id, business_id):
        return {'tenant_id': tenant_id, 'business_id': business_id}

    def get_summary(self, *, tenant_id, business_id):
        return {
            'tenant_id': tenant_id,
            'business_id': business_id,
            'total_runs': 1,
            'completed_runs': 1,
            'failed_runs': 0,
            'average_goal_score': 1.0,
            'active_goals': [],
            'learned_preferences': {},
            'recurring_failures': [],
            'recurring_wins': [],
            'anti_patterns': [],
            'trends': {},
        }


class _StubContract:
    def __init__(self) -> None:
        self.calls = 0

    def execute_autopilot(self, request):
        self.calls += 1
        class _Step:
            step_index = 0
            decision_id = 'd-1'
            action_id = 'a-1'
            action = 'notify_owner'
            status = 'completed'
            ok = True
            correlation_id = 'c-1'
            reason = 'done'
            payload = {}
            feedback = {}
        class _Report:
            goal = request.goal
            business_id = request.business_id
            tenant_id = request.tenant_id
            completed = True
            stop_reason = 'done'
            steps = (_Step(),)
            final_feedback = {}
        return _Report()


class _StubRuntime:
    def __init__(self) -> None:
        self.contract = _StubContract()
        self.business_memory_query = _StubBusinessMemoryQuery()


def test_headless_runtime_provider_reuses_runtime_instance_across_handlers() -> None:
    runtime = _StubRuntime()
    provider = build_headless_runtime_provider(runtime=runtime)
    headless = build_headless_route_handlers(runtime_provider=provider)
    business_memory = build_business_memory_route_handlers(runtime_provider=provider)

    response = headless.execute_goal(
        ExecuteGoalRequest(
            goal='grow',
            business_id='biz-1',
            tenant_id='tenant-1',
            user_id=None,
            region='global',
            max_steps=1,
            profile={},
            signals=[],
            constraints={},
            economy={},
            meta={},
        )
    )
    summary = business_memory.get_summary(BusinessMemorySummaryRequest(tenant_id='tenant-1', business_id='biz-1'))

    assert response.completed is True
    assert summary.total_runs == 1
    assert runtime.contract.calls == 1
