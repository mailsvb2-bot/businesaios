from types import SimpleNamespace

from runtime.handlers.ai_ceo_plan import _best_effort_route_ids


def test_ai_ceo_plan_route_violation_uses_env_ids_when_present():
    env = SimpleNamespace(decision=SimpleNamespace(decision_id="d-1", correlation_id="c-1"))
    decision_id, correlation_id = _best_effort_route_ids(payload={}, env=env)
    assert decision_id == "d-1"
    assert correlation_id == "c-1"
