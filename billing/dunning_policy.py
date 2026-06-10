from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Mapping

from billing.commercial_cycle_contract import DunningAction, utc_now
from core.tenancy.normalization import require_tenant_id

CANON_BILLING_DUNNING_POLICY = True


@dataclass(frozen=True)
class DunningPolicy:
    grace_days: int = 7
    retry_delays_days: tuple[int, ...] = (1, 3, 5)
    channel_order: tuple[str, ...] = ('email', 'in_product', 'operator')
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if int(self.grace_days) < 0:
            raise ValueError('grace_days must be >= 0')
        if not self.retry_delays_days:
            raise ValueError('retry_delays_days must not be empty')
        if any(int(delay) < 0 for delay in self.retry_delays_days):
            raise ValueError('retry_delays_days must be >= 0')
        if not self.channel_order:
            raise ValueError('channel_order must not be empty')
        for channel in self.channel_order:
            if not str(channel or '').strip():
                raise ValueError('channel names must be non-empty')

    def build_actions(self, *, tenant_id: str, invoice_id: str, started_at: datetime | None = None) -> tuple[DunningAction, ...]:
        self.validate()
        tid = require_tenant_id(tenant_id)
        normalized_invoice = str(invoice_id or '').strip()
        if not normalized_invoice:
            raise ValueError('invoice_id is required')
        base = started_at or utc_now()
        if base.tzinfo is None:
            raise ValueError('started_at must be timezone-aware')
        actions: list[DunningAction] = []
        channels = self.channel_order or ('email',)
        last_execute_at = base
        for index, delay in enumerate(self.retry_delays_days, start=1):
            execute_at = base + timedelta(days=max(0, int(delay)))
            if execute_at < last_execute_at:
                execute_at = last_execute_at
            channel = channels[min(index - 1, len(channels) - 1)]
            action = DunningAction(
                invoice_id=normalized_invoice,
                tenant_id=tid,
                attempt_no=index,
                execute_at=execute_at,
                channel=channel,
                template_key=f'billing.dunning.attempt_{index}',
                metadata={'owner': 'billing.dunning_policy', 'grace_days': int(self.grace_days), **dict(self.metadata)},
            )
            action.validate()
            actions.append(action)
            last_execute_at = execute_at
        return tuple(actions)


__all__ = ['CANON_BILLING_DUNNING_POLICY', 'DunningPolicy']
