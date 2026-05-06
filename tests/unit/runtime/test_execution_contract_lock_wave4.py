from dataclasses import dataclass

import pytest

from reliability.outbox_store import InMemoryOutboxStore, OutboxMessage, OutboxState
from runtime.execution.execution_contract_lock import (
    ExecutionContractLockError,
    commit_verified_execution,
    verify_execution_contract,
)


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

    def append_checkpoint(self, env, stage: str, checkpoint_id: str, payload: dict) -> None:
        self.rows.append((stage, dict(payload)))


class _Events:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def emit(self, **kwargs) -> None:
        self.rows.append(dict(kwargs))


class _VerifiedEvidenceVerifier:
    def verify(self, **kwargs):
        class _Result:
            def to_dict(self_nonlocal):
                return {
                    'verified': True,
                    'verification': {'status': 'verified', 'code': 'verified', 'outcome': {'external_refs': ['x-1']}},
                    'evidence_bundle': {'records': [{'source': 'executor'}]},
                    'context': {},
                }
        return _Result()


class _RejectedEvidenceVerifier:
    def verify(self, **kwargs):
        class _Result:
            def to_dict(self_nonlocal):
                return {
                    'verified': False,
                    'verification': {'status': 'failed', 'code': 'missing_external_confirmation'},
                    'evidence_bundle': {'records': []},
                    'context': {},
                }
        return _Result()


class _Executor:
    def __init__(self, verifier) -> None:
        self._evidence_verifier = verifier
        self._reliability = _Reliability()
        self._events = _Events()
        self._outbox = InMemoryOutboxStore()


def test_execution_contract_verifies_before_commit_and_persists_single_state_update() -> None:
    env = _Env(decision=_Decision(payload={'tenant_id': 'tenant-a', 'action_id': 'act-1'}))
    executor = _Executor(_VerifiedEvidenceVerifier())
    executor._outbox.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='dec-1', topic='runtime.effect.send_message@v1', dedupe_key='act-1', payload={'decision_id': 'dec-1'}, decision_id='dec-1'))
    executor._outbox.claim(tenant_id='tenant-a', message_id='dec-1', owner_id='runtime-executor', claim_ttl_seconds=60)

    verified = verify_execution_contract(executor=executor, env=env, output={'status': 'ok'})
    committed = commit_verified_execution(executor=executor, env=env, output={'status': 'ok'}, verification_result=verified)

    row = executor._outbox.get(tenant_id='tenant-a', message_id='dec-1')
    assert row is not None
    assert row.state is OutboxState.DELIVERED
    stages = [stage for stage, _ in executor._reliability.rows]
    assert 'verification' in stages
    assert stages.count('state_update') == 1
    assert stages.count('evidence') == 1
    assert committed['verification']['status'] == 'verified'
    assert committed['next_step_context']['verified'] is True
    assert committed['evidence_bundle']['records'][0]['source'] == 'executor'
    assert any(item['event_type'] == 'decision_executed' for item in executor._events.rows)


def test_execution_contract_fail_closed_before_commit_when_unverified() -> None:
    env = _Env(decision=_Decision(payload={'tenant_id': 'tenant-a'}))
    executor = _Executor(_RejectedEvidenceVerifier())
    with pytest.raises(ExecutionContractLockError):
        verify_execution_contract(executor=executor, env=env, output={'status': 'ok'})
    assert executor._outbox.get(tenant_id='tenant-a', message_id='dec-1') is None
    stages = [stage for stage, _ in executor._reliability.rows]
    assert 'verification' in stages
    assert 'state_update' not in stages
    assert 'evidence' not in stages
