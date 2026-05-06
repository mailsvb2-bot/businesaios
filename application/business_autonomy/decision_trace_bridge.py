from __future__ import annotations

from dataclasses import dataclass

from application.business_autonomy.contracts import BusinessExecutionRequest, BusinessExecutionResult
from observability.decision_trace_store import PersistentDecisionTraceStore
from observability.execution_trace_contract import DecisionTraceEvent


@dataclass(frozen=True)
class BusinessAutonomyDecisionTraceBridge:
    store: object

    @classmethod
    def default(cls) -> 'BusinessAutonomyDecisionTraceBridge':
        return cls(store=PersistentDecisionTraceStore())

    def append_execution(self, *, request: BusinessExecutionRequest, result: BusinessExecutionResult, evidence_id: str) -> None:
        tenant_id = str(request.envelope.metadata.get('tenant_id') or result.metadata.get('tenant_id') or result.business_id).strip() or result.business_id
        trace_id = str(request.correlation_id or request.idempotency_key or result.execution_id).strip() or result.execution_id
        decision_id = str(request.correlation_id or request.idempotency_key or f'business_autonomy:{result.business_id}:{result.goal_id}').strip()
        event = DecisionTraceEvent(
            tenant_id=tenant_id,
            trace_id=trace_id,
            decision_id=decision_id,
            correlation_id=str(request.correlation_id or '').strip() or None,
            route_name=str(request.integration_mode.value),
            selected_action=str(result.adapter_name or '').strip() or None,
            rationale_summary=str(result.message or '').strip() or None,
            candidate_count=1,
            component='application.business_autonomy.persistence',
            evidence_refs=(str(evidence_id),),
            payload={
                'business_id': result.business_id,
                'goal_id': result.goal_id,
                'execution_id': result.execution_id,
                'verdict': result.verdict.value,
            },
        )
        append = getattr(self.store, 'append', None)
        if callable(append):
            append(event)


__all__ = ['BusinessAutonomyDecisionTraceBridge']
