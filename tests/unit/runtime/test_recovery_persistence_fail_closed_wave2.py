from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from runtime.execution.executor_result import ExecutionResult
from runtime.executor_recovery_flow import execute_recovery_flow, has_proof_event


class _PendingOutbox:
    def status(self, decision_id: str) -> str:
        assert decision_id == "decision-1"
        return "pending"


class _Guard:
    def __init__(self) -> None:
        self.calls = 0

    def verify_recovery(self, env) -> None:
        self.calls += 1


def _env():
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-1",
            correlation_id="correlation-1",
            action="send_message@v1",
            payload={"tenant_id": "tenant-1"},
        )
    )


def _execute(*, executor, reliability, guard=None):
    executor._reliability = reliability
    return execute_recovery_flow(
        executor=executor,
        env=_env(),
        outbox=_PendingOutbox(),
        guard=guard or _Guard(),
        event_log=None,
        executor_context_cm=lambda _name: nullcontext(),
        warn=lambda *_args: None,
    )


def test_public_proof_lookup_helper_propagates_store_failure() -> None:
    class _Events:
        def has_event(self, decision_id: str, event_type: str) -> bool:
            raise OSError("PROOF_READ_FAILED")

    with pytest.raises(OSError, match="PROOF_READ_FAILED"):
        has_proof_event(
            event_log=_Events(),
            decision_id="decision-1",
            action="send_message@v1",
            warn=lambda *_args: None,
        )


def test_recovery_does_not_dispatch_when_recovery_checkpoint_cannot_be_written() -> None:
    class _Reliability:
        def append_checkpoint(self, *args, **kwargs) -> None:
            raise RuntimeError("CHECKPOINT_STORE_DOWN")

    guard = _Guard()
    executor = SimpleNamespace(
        _runtime_observability=None,
        _mark_delivered_if_already_executed=lambda _env: None,
        _dispatch=lambda *_args, **_kwargs: pytest.fail("dispatch must not run"),
    )

    with pytest.raises(RuntimeError, match="CHECKPOINT_STORE_DOWN"):
        _execute(executor=executor, reliability=_Reliability(), guard=guard)

    assert guard.calls == 0


def test_already_executed_recovery_does_not_duplicate_completion_writes() -> None:
    class _Reliability:
        def __init__(self) -> None:
            self.checkpoints: list[str] = []
            self.completed = 0

        def append_checkpoint(self, _env, *, stage: str, **_kwargs) -> None:
            self.checkpoints.append(stage)

        def mark_completed(self, _env) -> None:
            self.completed += 1

    reliability = _Reliability()
    recovered = ExecutionResult(
        ok=True,
        output={"status": "already_executed"},
        decision_id="decision-1",
        correlation_id="correlation-1",
    )
    executor = SimpleNamespace(
        _runtime_observability=None,
        _mark_delivered_if_already_executed=lambda _env: recovered,
        _dispatch=lambda *_args, **_kwargs: pytest.fail("dispatch must not run"),
    )

    result = _execute(executor=executor, reliability=reliability)

    assert result is recovered
    assert reliability.checkpoints == ["recovery"]
    assert reliability.completed == 0


def test_dispatch_failure_preserves_primary_error_when_failure_persistence_breaks() -> None:
    class _Reliability:
        def __init__(self) -> None:
            self.checkpoints: list[str] = []

        def append_checkpoint(self, _env, *, stage: str, **_kwargs) -> None:
            self.checkpoints.append(stage)
            if stage == "failed":
                raise RuntimeError("FAILED_CHECKPOINT_DOWN")

        def mark_failed(self, _env, *, reason: str) -> None:
            assert reason == "recovery_dispatch:ValueError"
            raise RuntimeError("FAILED_STATE_DOWN")

    executor = SimpleNamespace(
        _runtime_observability=None,
        _mark_delivered_if_already_executed=lambda _env: None,
        _dispatch=lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("DISPATCH_BROKE")),
    )

    with pytest.raises(ValueError, match="DISPATCH_BROKE") as caught:
        _execute(executor=executor, reliability=_Reliability())

    notes = list(getattr(caught.value, "__notes__", ()) or ())
    assert any("mark_failed" in note and "FAILED_STATE_DOWN" in note for note in notes)
    assert any("append_checkpoint:failed" in note and "FAILED_CHECKPOINT_DOWN" in note for note in notes)
