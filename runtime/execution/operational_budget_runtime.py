from __future__ import annotations

from dataclasses import asdict
from typing import Any

from contracts.action_impact_contract import ActionExecutionContext

CANON_RUNTIME_OPERATIONAL_BUDGET_GATE = True


class OperationalBudgetBlocked(RuntimeError):
    def __init__(self, *, error: str, output: dict[str, object]) -> None:
        super().__init__(str(error))
        self.error = str(error)
        self.output = dict(output)


def review_operational_budget(*, executor: Any, env: Any) -> None:
    service = getattr(executor, '_operational_budget_service', None)
    if service is None:
        return
    ctx = build_action_execution_context(env=env)
    precheck = service.precheck(ctx)
    if precheck.decision.status != 'allow':
        if executor._events is not None:
            executor._events.emit(
                event_type='operational_budget_veto',
                source='core.safety.operational',
                user_id=str(ctx.user_id or 'system'),
                decision_id=str(env.decision.decision_id),
                correlation_id=str(env.decision.correlation_id),
                payload={
                    'action_name': ctx.action_name,
                    'tenant_id': ctx.tenant_id,
                    'decision': asdict(precheck.decision),
                    'impact': asdict(precheck.impact),
                },
            )
        raise OperationalBudgetBlocked(
            error=str(precheck.decision.reason or 'operational_budget_blocked'),
            output={
                'blocked_by_policy': True,
                'operator_required': bool(precheck.impact.requires_human_approval),
                'operational_budget': {
                    'decision': asdict(precheck.decision),
                    'impact': asdict(precheck.impact),
                },
            },
        )
    service.commit(precheck.envelope)


def build_action_execution_context(*, env: Any) -> ActionExecutionContext:
    payload = env.decision.payload if isinstance(env.decision.payload, dict) else {}
    metadata = payload.get('meta') if isinstance(payload.get('meta'), dict) else {}
    ctx = ActionExecutionContext(
        tenant_id=str(payload.get('tenant_id') or 'default'),
        user_id=str(payload.get('user_id')).strip() if payload.get('user_id') is not None else None,
        action_name=str(env.decision.action or '').strip(),
        payload=dict(payload),
        metadata=dict(metadata),
        execution_id=str(env.decision.decision_id or '').strip() or None,
    )
    ctx.validate()
    return ctx


__all__ = [
    'CANON_RUNTIME_OPERATIONAL_BUDGET_GATE',
    'OperationalBudgetBlocked',
    'build_action_execution_context',
    'review_operational_budget',
]
