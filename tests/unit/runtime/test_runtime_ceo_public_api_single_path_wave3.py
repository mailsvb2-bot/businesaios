from runtime.actions import ACTION_EXECUTE_PLAN_V1
from runtime.ceo import execute_strategy


class _DecisionCore:
    def __init__(self) -> None:
        self.actions = []

    def decide_and_execute(self, action):
        self.actions.append(action)
        return {"ok": True, "action": action}


class _AuditLog:
    def event_names(self):
        return ("ceo.started",)


class _Observability:
    def __init__(self) -> None:
        self.audit_log = _AuditLog()


def test_execute_strategy_routes_through_runtime_application_builder() -> None:
    plan = type("Plan", (), {"steps": []})()
    decision_core = _DecisionCore()
    observability = _Observability()

    result = execute_strategy(
        plan,
        user_id="u-1",
        decision_core=decision_core,
        observability=observability,
    )

    assert result["ok"] is True
    assert decision_core.actions
    assert decision_core.actions[0]["action"] == ACTION_EXECUTE_PLAN_V1
    assert decision_core.actions[0]["user_id"] == "u-1"



def test_execute_strategy_without_decision_core_returns_envelope() -> None:
    plan = type("Plan", (), {"steps": []})()
    envelope = execute_strategy(plan, user_id="u-2")
    assert envelope.action == ACTION_EXECUTE_PLAN_V1
    assert envelope.payload["user_id"] == "u-2"
