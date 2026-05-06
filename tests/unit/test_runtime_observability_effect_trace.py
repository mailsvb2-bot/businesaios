from __future__ import annotations

from types import SimpleNamespace

from runtime.audit_log import RuntimeAuditLog
from runtime.execution.executor_observability import record_connector_runtime_event
from runtime.runtime_observability import RuntimeObservability


class _ConnectorObservability:
    def __init__(self) -> None:
        self.events = []

    def record(self, event) -> None:
        self.events.append(event)


def test_connector_runtime_event_emits_effect_trace_story() -> None:
    connector_observability = _ConnectorObservability()
    runtime_observability = RuntimeObservability(audit_log=RuntimeAuditLog())
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="d-1",
            correlation_id="c-1",
            action="send_email",
            payload={
                "tenant_id": "tenant-a",
                "connector_id": "mailgun",
                "connector_provider": "mail",
                "generated_at_ms": 123,
            },
        )
    )

    record_connector_runtime_event(
        observability=connector_observability,
        env=env,
        status="runtime_succeeded",
        payload={"attempt": 1},
        safe_dict=lambda value: dict(value),
        runtime_observability=runtime_observability,
    )

    records = runtime_observability.audit_log.records()
    assert records[-1].name == "runtime_trace_story"
    assert records[-1].payload["trace_kind"] == "effect"
    assert records[-1].payload["stage"] == "runtime_succeeded"
    assert records[-1].payload["connector_id"] == "mailgun"
