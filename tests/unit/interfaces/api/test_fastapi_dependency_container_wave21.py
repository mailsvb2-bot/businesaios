from __future__ import annotations

from dataclasses import dataclass, field

from interfaces.api.fastapi_dependencies import FastAPIDependencyContainer
from observability.action_audit_log import FileActionAuditLog
from observability.decision_audit_log import FileDecisionAuditLog
from observability.metrics import InMemoryMetrics


@dataclass(frozen=True)
class _RuntimeStub:
    metrics: InMemoryMetrics = field(default_factory=InMemoryMetrics)


@dataclass(frozen=True)
class _BootResultStub:
    runtime: object
    decision_application: object
    startup_report: tuple[str, ...] = ()


class _Service:
    def execute_action(self, action):
        return {"status": "ok", "action_type": action.action_type, "reason": "executed"}


def test_fastapi_dependency_container_uses_file_backed_default_audit_logs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('BUSINESAIOS_DATA_DIR', str(tmp_path))
    container = FastAPIDependencyContainer(boot_result=_BootResultStub(runtime=_RuntimeStub(), decision_application=_Service()))

    action_log = container.action_audit_log()
    decision_log = container.decision_audit_log()

    assert isinstance(action_log, FileActionAuditLog)
    assert isinstance(decision_log, FileDecisionAuditLog)
    assert action_log.path.parent == decision_log.path.parent
