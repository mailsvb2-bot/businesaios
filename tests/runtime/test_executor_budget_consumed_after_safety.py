from dataclasses import dataclass

import runtime.executor as runtime_executor_module
from runtime.executor import RuntimeExecutor
from runtime.execution.executor_result import ExecutionResult
from runtime.decision import DecisionEnvelope


@dataclass
class _Decision:
    decision_id: str = 'd1'
    correlation_id: str = 'c1'
    action: str = 'send_message@v1'
    payload: dict = None


class _Guard:
    _ledger = None


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


def test_runtime_executor_consumes_budget_after_safety(monkeypatch):
    guard = _BudgetGuard()
    executor = RuntimeExecutor(_Guard(), _Handlers(), _Events(), policy_registry=_Policy(), tenant_execution_budget_guard=guard)
    monkeypatch.setattr(executor, '_dispatch', lambda env, depth, enqueue: ExecutionResult(ok=True, output={}, decision_id='d1', correlation_id='c1'))
    monkeypatch.setattr(executor, '_apply_reliability_gate', lambda env: None)
    monkeypatch.setattr(runtime_executor_module, 'preflight_and_verify', lambda executor, env, timescale: None)
    env = DecisionEnvelope(decision=_Decision(payload={'tenant_id':'tenant-a','business_id':'b1','autonomy_tier':'supervised','approval_policy':{},'constraints':{},'economy':{},'action_type':'send_message@v1'}), payload_hash='h', signature='s', kid='k')
    result = executor._execute(env, depth=0)
    assert result.output['tenant_budget']['consumed'] is True
    assert guard.calls == ['evaluate', 'consume']
