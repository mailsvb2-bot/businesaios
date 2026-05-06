from __future__ import annotations

from typing import Optional

from application.business_autonomy.contracts import (
    BusinessExecutionRequest,
    BusinessExecutionResult,
    ExecutionVerdict,
)
from application.business_autonomy.policy import BusinessAutonomyPolicy
from application.business_autonomy.registry import BusinessAdapterRegistry


class BusinessAutonomyService:
    """
    Single platform owner for connected autonomous businesses.
    It may route and govern, but it must not embed domain logic of the business.
    """

    def __init__(
        self,
        *,
        adapter_registry: BusinessAdapterRegistry,
        autonomy_policy: BusinessAutonomyPolicy,
        audit_sink: Optional[object] = None,
    ) -> None:
        self._adapter_registry = adapter_registry
        self._autonomy_policy = autonomy_policy
        self._audit_sink = audit_sink

    async def execute(self, request: BusinessExecutionRequest) -> BusinessExecutionResult:
        decision = self._autonomy_policy.choose_mode(request)
        if not decision.allowed:
            return BusinessExecutionResult(
                verdict=ExecutionVerdict.REJECTED,
                business_id=request.envelope.business_id,
                goal_id=request.envelope.goal_id,
                execution_id=request.correlation_id,
                message=decision.reason,
                delegated_to_domain_engine=False,
                adapter_name=None,
                metadata={"policy_reason": decision.reason},
            )

        adapter = self._adapter_registry.get(request.envelope.business_id)
        delegated_request = BusinessExecutionRequest(
            envelope=request.envelope,
            integration_mode=decision.mode,
            correlation_id=request.correlation_id,
            idempotency_key=request.idempotency_key,
            timeout_seconds=request.timeout_seconds,
        )
        supported_modes = tuple(adapter.supported_modes())
        if delegated_request.integration_mode not in supported_modes:
            return BusinessExecutionResult(
                verdict=ExecutionVerdict.REJECTED,
                business_id=request.envelope.business_id,
                goal_id=request.envelope.goal_id,
                execution_id=request.correlation_id,
                message=f"Adapter does not support integration mode: {delegated_request.integration_mode.value}",
                delegated_to_domain_engine=False,
                adapter_name=adapter.adapter_name,
                metadata={"supported_modes": [item.value for item in supported_modes]},
            )

        result = await adapter.execute(delegated_request)
        if self._audit_sink is not None and hasattr(self._audit_sink, "record"):
            self._audit_sink.record(
                event_type="business_autonomy_result",
                business_id=result.business_id,
                goal_id=result.goal_id,
                detail={"verdict": result.verdict.value, "adapter_name": result.adapter_name},
            )
        return result
