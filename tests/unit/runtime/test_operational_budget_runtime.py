from types import SimpleNamespace

from contracts.action_impact_contract import ActionExecutionContext
from core.safety.operational.factory import build_operational_safety_runtime_with_components
from core.safety.operational.operational_budget_ledger import InMemoryOperationalBudgetLedger
from core.safety.operational.operational_budget_policy import OperationalBudgetPolicy
from core.safety.operational.tenant_policy_provider import TenantOperationalBudgetPolicyProvider
from runtime.execution.operational_budget_runtime import (
    OperationalBudgetBlocked,
    build_action_execution_context,
    review_operational_budget,
)


class _Events:
    def __init__(self) -> None:
        self.items = []

    def emit(self, **payload):
        self.items.append(payload)


def _env(*, action='send_email', payload=None):
    return SimpleNamespace(
        decision=SimpleNamespace(
            action=action,
            payload=payload or {'tenant_id': 't1', 'user_id': 'u1', 'recipient_count': 1},
            decision_id='d1',
            correlation_id='c1',
        )
    )


def test_build_action_execution_context_uses_decision_payload() -> None:
    ctx = build_action_execution_context(env=_env())
    assert isinstance(ctx, ActionExecutionContext)
    assert ctx.tenant_id == 't1'
    assert ctx.action_name == 'send_email'


def test_review_operational_budget_blocks_and_emits_event() -> None:
    provider = TenantOperationalBudgetPolicyProvider(
        default_policy=OperationalBudgetPolicy(),
        tenant_overrides={
            't1': OperationalBudgetPolicy(
                max_actions_per_hour=100,
                max_actions_per_day=100,
                max_budget_minor_per_day=100000,
                max_new_publications_per_day=100,
                max_outbound_messages_per_day=0,
                max_strategic_changes_without_human_approval_per_day=0,
                max_rollback_triggers_per_day=0,
            )
        },
    )
    runtime = build_operational_safety_runtime_with_components(
        ledger=InMemoryOperationalBudgetLedger(),
        policy_provider=provider,
    )
    events = _Events()
    executor = SimpleNamespace(_operational_budget_service=runtime.service, _events=events)

    try:
        review_operational_budget(executor=executor, env=_env())
    except OperationalBudgetBlocked as exc:
        assert exc.error == 'operational_budget_exceeded'
        assert exc.output['blocked_by_policy'] is True
    else:
        raise AssertionError('expected operational budget veto')

    assert events.items
    assert events.items[0]['event_type'] == 'operational_budget_veto'
