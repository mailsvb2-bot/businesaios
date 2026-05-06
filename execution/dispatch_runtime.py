from __future__ import annotations

from dataclasses import dataclass

from contracts.action_result import ActionResult
from contracts.executable_action import ExecutableAction
from execution.dispatch_runner_chain import DispatchRunnerChain
from observability.action_audit_log import ActionAuditLog
from observability.metrics import CounterStore
from observability.tracing import Tracer
from execution.run_result_store import ActionResultStore


@dataclass(frozen=True)
class DispatchRuntime:
    chain: DispatchRunnerChain
    store: ActionResultStore
    audit_log: ActionAuditLog
    metrics: CounterStore
    tracer: Tracer

    def dispatch(self, action: ExecutableAction) -> ActionResult:
        self.tracer.start(
            'action.dispatch',
            action_id=action.action_id,
            action_type=action.action_type,
            decision_id=action.decision_id,
            correlation_id=action.correlation_id,
        )
        result = self.chain.dispatch(action)
        self.store.save(action.action_id, result)
        self.audit_log.record(
            {
                'action_id': action.action_id,
                'decision_id': action.decision_id,
                'correlation_id': action.correlation_id,
                'objective_name': action.objective_name,
                'status': result.status,
                'action_type': action.action_type,
                'accepted': result.accepted,
            }
        )
        self.metrics.inc(f'action_dispatch.{result.status}')
        return result


__all__ = ['DispatchRuntime']
