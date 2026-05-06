from runtime.application import build_runtime_application_service_from_raw


class _DecisionCore:
    def __init__(self) -> None:
        self.actions = []

    def decide_and_execute(self, action):
        self.actions.append(action)
        return {"ok": True, "action": action}


class _AuditLog:
    def event_names(self):
        return ("startup",)


class _Observability:
    def __init__(self) -> None:
        self.audit_log = _AuditLog()


def test_build_runtime_application_service_from_raw_executes_and_reads_audit_events() -> None:
    core = _DecisionCore()
    service = build_runtime_application_service_from_raw(
        decision_core=core,
        observability=_Observability(),
    )

    result = service.execute_action({"action": "demo"})

    assert result["ok"] is True
    assert core.actions == [{"action": "demo"}]
    assert service.startup_audit_events() == ("startup",)
