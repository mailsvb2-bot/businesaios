from __future__ import annotations

from dataclasses import dataclass

import pytest

from core.ai.decision import Decision
from runtime.decision import DecisionEnvelope
from runtime.executor import RuntimeExecutor
from runtime.handlers import ActionHandlerRegistry


@dataclass
class _Guard:
    def verify(self, env):
        return env


class _Events:
    def __init__(self):
        self.last = None

    def emit(self, **kwargs):
        self.last = kwargs


class _Handler:
    def handle(self, payload):
        return {'ok': True}


class _PolicyRegistry:
    def resolve(self, action):
        return None


def _envelope(payload: dict[str, object]) -> DecisionEnvelope:
    return DecisionEnvelope(
        decision=Decision(
            decision_id='dec-1', issuer_id='core', issued_at_ms=1, expires_at_ms=2,
            policy_id='p', action='launch_campaign', payload=payload,
            snapshot_id='snap', state_hash='h', correlation_id='corr',
            state_schema_version=1, action_schema_version=1,
        ),
        payload_hash='h', signature='sig', kid='kid',
    )


def test_runtime_executor_emits_denial_event_for_missing_tenant_id() -> None:
    reg = ActionHandlerRegistry()
    reg.register('launch_campaign', _Handler())
    events = _Events()
    executor = RuntimeExecutor(_Guard(), reg, events, policy_registry=_PolicyRegistry())
    with pytest.raises(RuntimeError, match='missing_runtime_identity'):
        executor._enforce_runtime_budget_and_blast_radius(_envelope({'autonomy_tier': 'bounded_autonomy'}))
    assert events.last['event_type'] == 'runtime_autonomy_execution_denied'
    assert events.last['payload']['reason'] == 'autonomy_safety_denied:missing_runtime_identity'
