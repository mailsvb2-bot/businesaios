from __future__ import annotations

from types import SimpleNamespace

from runtime.application import build_runtime_service_exports_from_raw


class _ExecutionOwner:
    def __init__(self) -> None:
        self.envelopes: list[object] = []

    def execute(self, envelope: object):
        self.envelopes.append(envelope)
        return {"ok": True, "envelope": envelope}


class _AuditLog:
    def event_names(self):
        return ("evt",)


class _Observability:
    def __init__(self):
        self.audit_log = _AuditLog()


def _envelope():
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            action="x@v1",
        )
    )


def test_build_runtime_service_exports_from_raw_uses_shared_ports() -> None:
    owner = _ExecutionOwner()
    exports = build_runtime_service_exports_from_raw(
        decision_core=owner,
        observability=_Observability(),
    )
    envelope = _envelope()

    result = exports.decision_execution.execute_action(envelope)

    assert result["ok"] is True
    assert owner.envelopes == [envelope]
    assert exports.observability.audit_events() == ("evt",)


def test_build_runtime_service_exports_from_raw_allows_null_observability() -> None:
    exports = build_runtime_service_exports_from_raw(
        decision_core=_ExecutionOwner(),
        observability=None,
    )

    assert exports.observability.audit_events() == ()
