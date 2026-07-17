from types import SimpleNamespace

from runtime.application import build_runtime_application_service_from_raw


class _DecisionExecutionOwner:
    def __init__(self) -> None:
        self.envelopes = []

    def execute(self, envelope):
        self.envelopes.append(envelope)
        return {"ok": True, "envelope": envelope}


class _AuditLog:
    def event_names(self):
        return ("startup",)


class _Observability:
    def __init__(self) -> None:
        self.audit_log = _AuditLog()


def _envelope():
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            action="demo@v1",
        )
    )


def test_build_runtime_application_service_from_raw_executes_envelope_and_reads_audit_events() -> None:
    owner = _DecisionExecutionOwner()
    service = build_runtime_application_service_from_raw(
        decision_core=owner,
        observability=_Observability(),
    )
    envelope = _envelope()

    result = service.execute_action(envelope)

    assert result["ok"] is True
    assert owner.envelopes == [envelope]
    assert service.startup_audit_events() == ("startup",)
