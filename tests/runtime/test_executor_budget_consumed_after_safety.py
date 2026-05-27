from dataclasses import dataclass

from core.ai.decision import Decision
from runtime.decision import DecisionEnvelope
from runtime.execution.executor_result import ExecutionResult
from runtime.executor import RuntimeExecutor


class _Guard:
    _ledger = None

    def execute_once(self, env):
        return None


class _Handlers: ...
class _Events:
    def emit(self, *args, **kwargs):
        return None

class _Policy: ...

class _BudgetGuard:
    def __init__(self):
        self.calls = []
    @staticmethod
    def from_execution_payload(*, tenant_id, payload):
        from tenancy.tenant_execution_budget_guard import TenantExecutionUsage
        return TenantExecutionUsage(tenant_id=tenant_id, action_count=1)
    def evaluate(self, *, usage):
        self.calls.append('evaluate')
        class V: allowed=True; reason='ok'; tenant_id=usage.tenant_id; violations=(); consumed=False
        return V()
    def consume(self, *, usage):
        self.calls.append('consume')
        class V: allowed=True; reason='ok'; tenant_id=usage.tenant_id; violations=(); consumed=True
        return V()


def _decision(*, payload: dict) -> Decision:
    return Decision(
        decision_id='d1',
        issuer_id='test-decision-core',
        issued_at_ms=1,
        expires_at_ms=2,
        policy_id='test-policy@v1',
        action='send_message@v1',
        payload=payload,
        snapshot_id='snapshot-1',
        state_hash='state-hash-1',
        correlation_id='c1',
        state_schema_version=1,
        action_schema_version=1,
    )


def test_runtime_executor_consumes_budget_after_safety(monkeypatch):
    guard = _BudgetGuard()
    executor = RuntimeExecutor(_Guard(), _Handlers(), _Events(), policy_registry=_Policy(), tenant_execution_budget_guard=guard)
    monkeypatch.setattr(executor, '_dispatch', lambda env, depth, enqueue: ExecutionResult(ok=True, output={}, decision_id='d1', correlation_id='c1'))
    monkeypatch.setattr(executor, '_apply_reliability_gate', lambda env: None)
    env = DecisionEnvelope(
        decision=_decision(
            payload={
                'tenant_id':'tenant-a',
                'business_id':'b1',
                'autonomy_tier':'supervised',
                'approval_policy':{},
                'constraints':{},
                'economy':{},
                'action_type':'send_message@v1',
            }
        ),
        payload_hash='h',
        signature='s',
        kid='k',
    )
    result = executor._execute(env, depth=0)
    assert result.output['tenant_budget']['consumed'] is True
    assert guard.calls == ['evaluate', 'consume']
