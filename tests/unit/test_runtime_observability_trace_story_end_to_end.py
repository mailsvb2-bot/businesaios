from __future__ import annotations

from types import SimpleNamespace

from runtime.audit_log import RuntimeAuditLog
from runtime.execution.executor_trace_runtime import _record_runtime_trace_story
from runtime.executor_recovery_flow import _record_recovery_trace
from runtime.runtime_observability import RuntimeObservability


def test_runtime_execution_trace_story_records_execution_event() -> None:
    observability = RuntimeObservability(audit_log=RuntimeAuditLog())
    executor = SimpleNamespace(_runtime_observability=observability)
    env = SimpleNamespace(decision=SimpleNamespace(decision_id="d-1", action="send_email", payload={"generated_at_ms": 123}))

    _record_runtime_trace_story(executor=executor, env=env, trace_kind="execution", stage="started", trace_id="t-1")

    records = observability.audit_log.records()
    assert records[-1].name == "runtime_trace_story"
    assert records[-1].payload["trace_kind"] == "execution"
    assert records[-1].payload["stage"] == "started"


def test_runtime_recovery_trace_story_records_recovery_event() -> None:
    observability = RuntimeObservability(audit_log=RuntimeAuditLog())
    executor = SimpleNamespace(_runtime_observability=observability)
    env = SimpleNamespace(decision=SimpleNamespace(decision_id="d-2", action="retry", payload={"generated_at_ms": 456}))

    _record_recovery_trace(executor=executor, env=env, stage="started", reason="resume")

    records = observability.audit_log.records()
    assert records[-1].name == "runtime_trace_story"
    assert records[-1].payload["trace_kind"] == "recovery"
    assert records[-1].payload["stage"] == "started"
