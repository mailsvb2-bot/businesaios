from runtime.application import build_runtime_service_exports_from_raw


class _DecisionCore:
    def decide_and_execute(self, action):
        return {"ok": True, "action": action}


class _AuditLog:
    def event_names(self):
        return ("evt",)


class _Observability:
    def __init__(self):
        self.audit_log = _AuditLog()


def test_build_runtime_service_exports_from_raw_uses_shared_ports() -> None:
    exports = build_runtime_service_exports_from_raw(
        decision_core=_DecisionCore(),
        observability=_Observability(),
    )
    assert exports.decision_execution.execute_action({"action": "x"})["ok"] is True
    assert exports.observability.audit_events() == ("evt",)


def test_build_runtime_service_exports_from_raw_allows_null_observability() -> None:
    exports = build_runtime_service_exports_from_raw(decision_core=_DecisionCore(), observability=None)
    assert exports.observability.audit_events() == ()
