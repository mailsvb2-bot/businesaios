from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from billing.commercial_cycle_contract import DunningAction, utc_now
from billing.dunning_policy import DunningPolicy
from observability.tenant_metrics_registry import TenantMetricsRegistry

CANON_BILLING_DUNNING_ORCHESTRATOR = True


@dataclass
class InMemoryDunningScheduleStore:
    actions_by_invoice: dict[tuple[str, str], tuple[DunningAction, ...]] = field(default_factory=dict)
    executed_actions: set[tuple[str, str, int]] = field(default_factory=set)

    def save(self, *, tenant_id: str, invoice_id: str, actions: tuple[DunningAction, ...], replace_existing: bool = True) -> tuple[DunningAction, ...]:
        key = (str(tenant_id), str(invoice_id))
        validated: list[DunningAction] = []
        seen_attempts: set[int] = set()
        last_execute_at = None
        for action in actions:
            action.validate()
            if str(action.tenant_id) != key[0] or str(action.invoice_id) != key[1]:
                raise ValueError('dunning action tenant_id/invoice_id mismatch')
            if int(action.attempt_no) in seen_attempts:
                raise ValueError('duplicate dunning attempt_no for invoice')
            seen_attempts.add(int(action.attempt_no))
            if last_execute_at is not None and action.execute_at < last_execute_at:
                raise ValueError('dunning actions must be ordered by execute_at')
            last_execute_at = action.execute_at
            validated.append(action)
        if not replace_existing and key in self.actions_by_invoice:
            return tuple(self.actions_by_invoice[key])
        if replace_existing:
            self.executed_actions = {item for item in self.executed_actions if item[:2] != key}
        self.actions_by_invoice[key] = tuple(validated)
        return tuple(validated)

    def get(self, *, tenant_id: str, invoice_id: str) -> tuple[DunningAction, ...]:
        return tuple(self.actions_by_invoice.get((str(tenant_id), str(invoice_id)), ()))

    def mark_executed(self, *, tenant_id: str, invoice_id: str, attempt_no: int) -> None:
        actions = self.get(tenant_id=tenant_id, invoice_id=invoice_id)
        if not any(int(item.attempt_no) == int(attempt_no) for item in actions):
            raise LookupError('unknown dunning attempt for invoice')
        key = (str(tenant_id), str(invoice_id), int(attempt_no))
        self.executed_actions.add(key)

    def is_executed(self, *, tenant_id: str, invoice_id: str, attempt_no: int) -> bool:
        return (str(tenant_id), str(invoice_id), int(attempt_no)) in self.executed_actions


class DunningOrchestrator:
    def __init__(self, *, policy: DunningPolicy | None = None, store: InMemoryDunningScheduleStore | None = None, metrics: TenantMetricsRegistry | None = None) -> None:
        self._policy = policy or DunningPolicy()
        self._store = store or InMemoryDunningScheduleStore()
        self._metrics = metrics

    def open_run(self, *, tenant_id: str, invoice_id: str, started_at: datetime | None = None, replace_existing: bool = False) -> tuple[DunningAction, ...]:
        run_started_at = started_at or utc_now()
        if run_started_at.tzinfo is None:
            raise ValueError('started_at must be timezone-aware')
        existing = self._store.get(tenant_id=tenant_id, invoice_id=invoice_id)
        if existing and not replace_existing:
            return existing
        actions = self._policy.build_actions(tenant_id=tenant_id, invoice_id=invoice_id, started_at=run_started_at)
        saved = self._store.save(tenant_id=tenant_id, invoice_id=invoice_id, actions=actions, replace_existing=replace_existing)
        if self._metrics is not None:
            self._metrics.inc(tenant_id=tenant_id, metric_name='billing_dunning_runs_opened_total', amount=1.0, labels={'invoice_id': invoice_id})
            self._metrics.set_gauge(tenant_id=tenant_id, metric_name='billing_dunning_actions_pending', value=float(len(saved)), labels={'invoice_id': invoice_id})
        return saved

    def due_actions(self, *, tenant_id: str, invoice_id: str, now: datetime | None = None) -> tuple[DunningAction, ...]:
        observed_at = now or utc_now()
        if observed_at.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        due = [
            item
            for item in self._store.get(tenant_id=tenant_id, invoice_id=invoice_id)
            if item.execute_at <= observed_at and not self._store.is_executed(tenant_id=tenant_id, invoice_id=invoice_id, attempt_no=item.attempt_no)
        ]
        return tuple(sorted(due, key=lambda item: (item.execute_at, item.attempt_no)))

    def mark_action_executed(self, *, tenant_id: str, invoice_id: str, attempt_no: int) -> None:
        self._store.mark_executed(tenant_id=tenant_id, invoice_id=invoice_id, attempt_no=attempt_no)


__all__ = ['CANON_BILLING_DUNNING_ORCHESTRATOR', 'DunningOrchestrator', 'InMemoryDunningScheduleStore']
