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
