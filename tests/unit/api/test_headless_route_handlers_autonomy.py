from __future__ import annotations

import pytest

from entrypoints.api.headless_models import ExecuteGoalRequest
from entrypoints.api.headless_route_handlers import HeadlessRouteHandlers


class _CapturedRequest(RuntimeError):
    def __init__(self, request):
        super().__init__("captured_goal_execution_request")
        self.request = request


class _ContractRuntime:
    def execute_autopilot(self, request):
        raise _CapturedRequest(request)


class _RuntimeProvider:
    def contract_runtime(self):
        return _ContractRuntime()


def _capture_request(*, meta: dict) -> object:
    handlers = HeadlessRouteHandlers(runtime_provider=_RuntimeProvider())
    with pytest.raises(_CapturedRequest) as captured:
        handlers.execute_goal(
            ExecuteGoalRequest(
                goal="Plan safely",
                business_id="business-1",
                tenant_id="tenant-1",
                meta=meta,
            )
        )
    return captured.value.request


def test_owner_workspace_goal_is_forced_to_advisory_at_server_boundary():
    request = _capture_request(meta={"source": "owner_workspace"})

    assert request.autonomy_tier == "advisory"
    assert request.meta == {"source": "owner_workspace"}


def test_general_execute_goal_preserves_supervised_semantics():
    request = _capture_request(meta={"source": "api_client"})

    assert request.autonomy_tier == "supervised"


def test_missing_source_preserves_supervised_semantics():
    request = _capture_request(meta={})

    assert request.autonomy_tier == "supervised"
