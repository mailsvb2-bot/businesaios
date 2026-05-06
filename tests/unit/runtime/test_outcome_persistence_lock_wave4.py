from dataclasses import dataclass

from reliability.outbox_store import InMemoryOutboxStore, OutboxMessage, OutboxState
from runtime.execution.outcome_persistence_lock import finalize_recovered_outcome, persist_verified_outcome


@dataclass
class _Decision:
    decision_id: str = 'dec-1'
    correlation_id: str = 'corr-1'
    action: str = 'send_message@v1'
    payload: dict | None = None


@dataclass
class _Env:
    decision: _Decision


class _Reliability:
    def __init__(self) -> None:
        self.rows: list[tuple[str, dict]] = []
        self.completed = 0

    def append_checkpoint(self, env, stage: str, checkpoint_id: str, payload: dict) -> None:
        self.rows.append((stage, dict(payload)))

    def mark_completed(self, env) -> None:
        self.completed += 1


class _Events:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def emit(self, **kwargs) -> None:
        self.rows.append(dict(kwargs))


class _Executor:
    def __init__(self) -> None:
        self._reliability = _Reliability()
        self._events = _Events()
        self._outbox = InMemoryOutboxStore()


def test_persist_verified_outcome_is_single_owner_for_state_update_and_evidence() -> None:
    env = _Env(decision=_Decision(payload={'tenant_id': 'tenant-a', 'action_id': 'act-1'}))
    executor = _Executor()
    executor._outbox.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='dec-1', topic='runtime.effect.send_message@v1', dedupe_key='act-1', payload={'decision_id': 'dec-1'}, decision_id='dec-1'))
    executor._outbox.claim(tenant_id='tenant-a', message_id='dec-1', owner_id='runtime-executor', claim_ttl_seconds=60)

    persisted = persist_verified_outcome(executor=executor, env=env, verification={'status': 'verified', 'verified': True})

    row = executor._outbox.get(tenant_id='tenant-a', message_id='dec-1')
    assert row is not None
    assert row.state is OutboxState.DELIVERED
    stages = [stage for stage, _ in executor._reliability.rows]
    assert stages.count('state_update') == 1
    assert stages.count('evidence') == 1
    assert persisted['state_update']['owner'] == 'runtime.execution.outcome_persistence_lock'
    assert persisted['evidence_record']['event_type'] == 'decision_executed'
    assert any(item['event_type'] == 'decision_executed' for item in executor._events.rows)


def test_finalize_recovered_outcome_commits_canonical_recovery_persistence() -> None:
    env = _Env(decision=_Decision(payload={'tenant_id': 'tenant-a'}))
    executor = _Executor()
    executor._outbox.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='dec-1', topic='runtime.effect.send_message@v1', dedupe_key='dec-1', payload={'decision_id': 'dec-1'}, decision_id='dec-1'))
    executor._outbox.claim(tenant_id='tenant-a', message_id='dec-1', owner_id='runtime-recovery', claim_ttl_seconds=60)

    persisted = finalize_recovered_outcome(executor=executor, env=env, reason='has_proof_event')

    row = executor._outbox.get(tenant_id='tenant-a', message_id='dec-1')
    assert row is not None
    assert row.state is OutboxState.DELIVERED
    stages = [stage for stage, _ in executor._reliability.rows]
    assert stages.count('state_update') == 1
    assert stages.count('evidence') == 1
    assert stages.count('completed') == 1
    assert executor._reliability.completed == 1
    assert persisted['evidence_record']['source'] == 'existing_proof_event'
