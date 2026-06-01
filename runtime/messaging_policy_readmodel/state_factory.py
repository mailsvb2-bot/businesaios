from __future__ import annotations

from runtime.messaging_policy_readmodel.state_accumulator import MessagingPolicyAccumulator
from runtime.tenancy import normalize_tenant_scope


def new_accumulator(*, tenant_id: str, user_id: str, correlation_id: str) -> MessagingPolicyAccumulator:
    return MessagingPolicyAccumulator(
        tenant_id=normalize_tenant_scope(tenant_id, allow_unknown=True),
        user_id=str(user_id),
        correlation_id=str(correlation_id),
        delivered=[],
        failed=[],
        blocked=[],
        last_plan_channels=(),
        last_selected_channel='',
        last_terminal_reason='',
        attempts_count=0,
    )
