import pytest

from entrypoints.api.headless_models import ExecuteGoalRequest
from entrypoints.api.headless_route_handlers import HeadlessRouteHandlers


class _CapturedRequest(RuntimeError):
    pass


class _ContractRuntime:
    def execute_autopilot(self, request):
        raise _CapturedRequest(request)


class _RuntimeProvider:
    def contract_runtime(self):
        return _ContractRuntime()


def _capture_request(meta: dict) -> object:
    request = ExecuteGoalRequest(goal="Plan safely", business_id="business-1", tenant_id="tenant-1", meta=meta)
    with pytest.raises(_CapturedRequest) as captured:
        HeadlessRouteHandlers(runtime_provider=_RuntimeProvider()).execute_goal(request)
    return captured.value.args[0]


def test_owner_workspace_goal_is_forced_to_advisory_at_server_boundary():
    request = _capture_request({"source": "owner_workspace"})
    assert request.autonomy_tier == "advisory"
    assert request.meta == {"source": "owner_workspace"}


@pytest.mark.parametrize("meta", [{"source": "api_client"}, {}])
def test_general_execute_goal_preserves_supervised_semantics(meta):
    assert _capture_request(meta).autonomy_tier == "supervised"
