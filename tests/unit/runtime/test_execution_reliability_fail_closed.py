from __future__ import annotations

import logging
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from reliability.execution_checkpoint_store import InMemoryExecutionCheckpointStore
from reliability.idempotency_contract import (
    IdempotencyDecision,
    IdempotencyKey,
    IdempotencyRecord,
    IdempotencyResolution,
    IdempotencyState,
)
from reliability.outbox_store import InMemoryOutboxStore, OutboxMessage
from runtime.execution.executor_reliability import apply_reliability_gate
from runtime.execution.outcome_persistence_lock import finalize_recovered_outcome, persist_verified_outcome
from runtime.execution.reliability_runtime import RuntimeReliability


@dataclass
class _Decision:
    decision_id: str = "decision-1"
    correlation_id: str = "correlation-1"
    action: str = "send_message@v1"
    payload: dict | None = None


@dataclass
class _Env:
    decision: _Decision


class _BrokenIdempotencyStore:
    def get(self, *, key):
        return IdempotencyRecord(idempotency_key=key, state=IdempotencyState.IN_PROGRESS, owner_id="runtime-executor")

    def mark_completed(self, **kwargs):
        raise RuntimeError("completion persistence unavailable")

    def mark_failed(self, **kwargs):
        raise RuntimeError("failure persistence unavailable")


class _MissingOrTerminalIdempotencyStore:
    def __init__(self, record):
        self.record = record

    def get(self, *, key):
        return self.record

    def mark_completed(self, **kwargs):
        raise AssertionError("terminal or missing record must not be mutated")

    mark_failed = mark_completed


class _BrokenRecovery:
    def reconcile(self, **kwargs):
        raise RuntimeError("reconciliation unavailable")


class _BrokenCheckpointReliability:
    def append_checkpoint(self, *args, **kwargs):
        raise RuntimeError("checkpoint unavailable")

    def mark_completed(self, *args, **kwargs):
        raise RuntimeError("completion unavailable")


class _Events:
    def emit(self, **kwargs) -> None:
        return None


class _Executor:
    def __init__(self, reliability) -> None:
        self._reliability = reliability
        self._events = _Events()
        self._outbox = InMemoryOutboxStore()
        self._logger = logging.getLogger("test.execution.reliability")


def _env() -> _Env:
    return _Env(decision=_Decision(payload={"tenant_id": "tenant-a"}))


def _runtime(*, idempotency_store=None, recovery=None) -> RuntimeReliability:
    return RuntimeReliability(
        checkpoint_store=InMemoryExecutionCheckpointStore(),
        idempotency_store=idempotency_store or _BrokenIdempotencyStore(),
        recovery_orchestrator=recovery or SimpleNamespace(),
        distributed_lock=SimpleNamespace(),
        scheduler_leader_election=SimpleNamespace(),
        recovery_leader_election=SimpleNamespace(),
    )


def test_runtime_reliability_completion_and_failure_persistence_fail_closed() -> None:
    runtime = _runtime()

    with pytest.raises(RuntimeError, match="completion persistence unavailable"):
        runtime.mark_completed(_env())
    with pytest.raises(RuntimeError, match="failure persistence unavailable"):
        runtime.mark_failed(_env(), reason="dispatch failed")


def test_runtime_reliability_missing_or_terminal_reservation_is_explicit_noop() -> None:
    env = _env()
    _runtime(idempotency_store=_MissingOrTerminalIdempotencyStore(None)).mark_completed(env)
    key = _runtime().idempotency_key_for_env(env)
    completed = IdempotencyRecord(idempotency_key=key, state=IdempotencyState.COMPLETED, owner_id="runtime-executor")
    runtime = _runtime(idempotency_store=_MissingOrTerminalIdempotencyStore(completed))
    runtime.mark_completed(env)
    runtime.mark_failed(env, reason="late failure")


def test_runtime_reliability_reconciliation_failure_is_visible() -> None:
    runtime = _runtime(recovery=_BrokenRecovery())

    with pytest.raises(RuntimeError, match="reconciliation unavailable"):
        runtime.reconcile(_env())


def test_outcome_checkpoint_failure_prevents_false_success_return() -> None:
    env = _env()
    executor = _Executor(_BrokenCheckpointReliability())
    executor._outbox.enqueue(
        OutboxMessage(
            tenant_id="tenant-a",
            message_id="decision-1",
            topic="runtime.effect.send_message@v1",
            dedupe_key="decision-1",
            payload={"decision_id": "decision-1"},
            decision_id="decision-1",
        )
    )
    executor._outbox.claim(
        tenant_id="tenant-a",
        message_id="decision-1",
        owner_id="runtime-executor",
        claim_ttl_seconds=60,
    )

    with pytest.raises(RuntimeError, match="checkpoint unavailable"):
        persist_verified_outcome(executor=executor, env=env, verification={"status": "verified"})


def test_recovered_outcome_completion_failure_is_visible() -> None:
    env = _env()
    reliability = _BrokenCheckpointReliability()
    reliability.append_checkpoint = lambda *args, **kwargs: None
    executor = _Executor(reliability)
    executor._outbox.enqueue(
        OutboxMessage(
            tenant_id="tenant-a",
            message_id="decision-1",
            topic="runtime.effect.send_message@v1",
            dedupe_key="decision-1",
            payload={"decision_id": "decision-1"},
            decision_id="decision-1",
        )
    )
    executor._outbox.claim(
        tenant_id="tenant-a",
        message_id="decision-1",
        owner_id="runtime-recovery",
        claim_ttl_seconds=60,
    )

    with pytest.raises(RuntimeError, match="completion unavailable"):
        finalize_recovered_outcome(executor=executor, env=env, reason="existing_proof")


class _ReserveFailure:
    def reserve(self, env):
        raise RuntimeError("reservation unavailable")


class _CheckpointFailure:
    def reserve(self, env):
        key = IdempotencyKey(
            tenant_id="tenant-a",
            namespace="runtime",
            operation="execute",
            key="decision-1",
        )
        return IdempotencyDecision(
            resolution=IdempotencyResolution.REJECTED_IN_PROGRESS,
            record=IdempotencyRecord(idempotency_key=key, state=IdempotencyState.IN_PROGRESS),
        )

    def append_checkpoint(self, *args, **kwargs):
        raise RuntimeError("checkpoint unavailable")


def test_reliability_reservation_failure_blocks_execution() -> None:
    result = apply_reliability_gate(executor=_Executor(_ReserveFailure()), env=_env())

    assert result is not None
    assert result.ok is False
    assert result.error == "reliability_reservation_failed:RuntimeError"
    assert result.output["status"] == "blocked"


def test_reliability_checkpoint_failure_blocks_already_claimed_success() -> None:
    result = apply_reliability_gate(executor=_Executor(_CheckpointFailure()), env=_env())

    assert result is not None
    assert result.ok is False
    assert result.error == "reliability_checkpoint_failed:RuntimeError"
    assert result.output["status"] == "blocked"


@pytest.mark.parametrize("dispatch_started", [False, True])
@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_stable_telegram_update_key_recovers_only_before_dispatch(monkeypatch, tmp_path, backend, dispatch_started) -> None:
    """Never poison a pre-effect update; never replay ambiguous effects blindly."""
    from contextlib import nullcontext
    from datetime import datetime, timedelta, timezone

    from reliability.idempotency_store import InMemoryIdempotencyStore
    from reliability.idempotency_sqlite_backend import SQLiteIdempotencyStore
    from runtime.execution import executor_trace_runtime as trace_runtime

    now = datetime(2026, 11, 17, tzinfo=timezone.utc)
    store = InMemoryIdempotencyStore() if backend == "memory" else SQLiteIdempotencyStore(tmp_path / "inbox-reliability.sqlite3")
    key = IdempotencyKey(
        tenant_id="tenant-a", namespace="runtime", operation="execute",
        key="telegram:verified-update-42",
    )
    assert store.reserve(key=key, owner_id="runtime-executor", now=now).resolution is IdempotencyResolution.ACCEPTED

    class Reliability:
        marked_failed = False

        def mark_failed(self, _env, *, reason):
            self.marked_failed = True
            store.mark_failed(key=key, owner_id="runtime-executor", reason=reason, now=now)

        def append_checkpoint(self, *_args, **_kwargs):
            pass

    class Executor:
        _reliability = Reliability()
        _events = None
        _execution_trace_store = None

        @staticmethod
        def _safe_dict(value):
            return dict(value or {})

        @staticmethod
        def _tenant_runtime_context(**_kwargs):
            return nullcontext()

        @staticmethod
        def _apply_reliability_gate(_env):
            return None

        @staticmethod
        def _enforce_runtime_budget_and_blast_radius(_env):
            return None

        @staticmethod
        def _dispatch(_env, *, depth, enqueue):
            raise OSError("temporary transport interruption")

    monkeypatch.setattr(trace_runtime, "execution_span", lambda **_kwargs: nullcontext())
    monkeypatch.setattr(trace_runtime, "record_execution_outcome", lambda **_kwargs: None)
    env = _Env(_Decision(payload={
        "tenant_id": "tenant-a", "user_id": "4001", "idempotency_key": key.key,
    }))

    def preflight_fn(**_kwargs):
        if not dispatch_started:
            raise OSError("temporary preflight interruption")

    with pytest.raises(OSError, match="temporary"):
        trace_runtime.execute_core_flow(
            executor=Executor(), env=env, depth=0,
            timescale=SimpleNamespace(value="instant"), preflight_fn=preflight_fn,
        )

    assert Executor._reliability.marked_failed is dispatch_started
    if dispatch_started:
        assert store.get(key=key).state is IdempotencyState.FAILED
        assert store.reserve(key=key, owner_id="runtime-executor", now=now + timedelta(seconds=301)).resolution is IdempotencyResolution.REJECTED_TERMINAL_FAILED
    else:
        assert store.get(key=key).state is IdempotencyState.IN_PROGRESS
        assert store.reserve(key=key, owner_id="runtime-executor", now=now + timedelta(seconds=1)).resolution is IdempotencyResolution.REJECTED_IN_PROGRESS
        recovered = store.reserve(key=key, owner_id="runtime-executor", now=now + timedelta(seconds=301))
        assert recovered.resolution is IdempotencyResolution.ACCEPTED
        assert recovered.record.attempt_count == 2


def test_completed_update_replay_skips_dispatch() -> None:
    from runtime.safety import verified_inbound_reply_scope
    from core.safety.controls.action_budget.models import issue_verified_update_idempotency_key

    class AlreadyCompleted:
        def reserve(self, env):
            key = IdempotencyKey(
                tenant_id="tenant-a", namespace="runtime", operation="execute",
                key=env.decision.payload["idempotency_key"],
            )
            return IdempotencyDecision(
                resolution=IdempotencyResolution.REPLAY_COMPLETED,
                record=IdempotencyRecord(idempotency_key=key, state=IdempotencyState.COMPLETED),
                replay_result_ref="previous-execution",
                replay_result_digest="previous-evidence",
            )

    class CheckedGuard:
        verified = False
        def verify(self, env):
            self.verified = True

    executor = _Executor(AlreadyCompleted())
    executor._guard = CheckedGuard()
    with verified_inbound_reply_scope(
        tenant_id="tenant-a", channel="telegram", user_id="4001",
        update_id=42, chat_id="4001",
    ):
        key = issue_verified_update_idempotency_key(
            tenant_id="tenant-a", channel="telegram", user_id="4001",
            update_id=42, chat_id="4001",
        )
        env = _Env(_Decision(payload={
            "tenant_id": "tenant-a", "user_id": "4001",
            "idempotency_key": key,
        }))
        result = apply_reliability_gate(executor=executor, env=env)
    assert executor._guard.verified is True
    assert result is not None
    assert result.ok is True
    assert result.output["status"] == "already_completed"
    assert result.output["idempotency_resolution"] == "replay_completed"
    assert result.output["replay_result_ref"] == "previous-execution"


def test_unverified_completed_replay_preserves_legacy_guard_path() -> None:
    key = IdempotencyKey(
        tenant_id="tenant-a", namespace="runtime", operation="execute",
        key="decision-1",
    )
    class AlreadyCompleted:
        def reserve(self, env):
            return IdempotencyDecision(
                resolution=IdempotencyResolution.REPLAY_COMPLETED,
                record=IdempotencyRecord(idempotency_key=key, state=IdempotencyState.COMPLETED),
            )

    # Returning None lets the canonical guard enforce DUPLICATE_EXECUTION
    # and allows independent-ledger replay to preserve its original output.
    assert apply_reliability_gate(executor=_Executor(AlreadyCompleted()), env=_env()) is None

def test_live_idempotency_lease_does_not_ack_telegram_inbox() -> None:
    key = IdempotencyKey(
        tenant_id="tenant-a", namespace="runtime", operation="execute",
        key="telegram:verified-update-42",
    )
    class AlreadyInProgress:
        def reserve(self, env):
            return IdempotencyDecision(
                resolution=IdempotencyResolution.REJECTED_IN_PROGRESS,
                record=IdempotencyRecord(idempotency_key=key, state=IdempotencyState.IN_PROGRESS),
            )
        def append_checkpoint(self, *_args, **_kwargs):
            return None

    result = apply_reliability_gate(executor=_Executor(AlreadyInProgress()), env=_env())
    assert result is not None
    assert result.ok is False
    assert result.output["status"] == "already_claimed"
    assert result.error == "idempotency_resolution:rejected_in_progress"
