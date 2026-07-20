from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from billing.commercial_cycle_contract import (
    BillingCycleWindow,
    CommercialCollectionResult,
    InvoiceLifecycleStatus,
    SubscriptionCommercialEnvelope,
    SubscriptionLifecycleStatus,
)
from billing.dunning_policy import DunningPolicy
from billing.invoice_lifecycle import CommercialInvoiceEnvelope, InvoiceLifecycleService
from billing.payment_collection import InMemoryCollectionResultStore, PaymentCollectionOrchestrator
from billing.spend_guard import SpendGuard, SpendLimitPolicy
from billing.subscription_lifecycle import SubscriptionLifecycleService

NOW = datetime(2026, 1, 10, 12, tzinfo=UTC)

class _Metrics:

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def inc(self, **kwargs) -> None:
        self.calls.append(('inc', kwargs))

    def set_gauge(self, **kwargs) -> None:
        self.calls.append(('gauge', kwargs))

class _Ledger:

    def __init__(self, *, total=0, entries=()) -> None:
        self.total = total
        self.entries = tuple(entries)

    def total_for_account(self, **kwargs):
        return self.total

    def list_postings(self, **kwargs):
        return (SimpleNamespace(entries=self.entries),) if self.entries else ()

class _Provider:

    def __init__(self, *, name='provider-a', results=()) -> None:
        self.name = name
        self.results = list(results)
        self.attempts = []

    def provider_name(self) -> str:
        return self.name

    def collect(self, attempt):
        self.attempts.append(attempt)
        if not self.results:
            raise AssertionError('unexpected provider call')
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

def _cycle() -> BillingCycleWindow:
    return BillingCycleWindow(start_at=NOW, end_at=NOW + timedelta(days=30), anchor='monthly')

def _subscription(status=SubscriptionLifecycleStatus.ACTIVE, **changes) -> SubscriptionCommercialEnvelope:
    values = {'tenant_id': 'tenant-a', 'subscription_id': 'sub-1', 'plan_id': 'plan-1', 'status': status, 'cycle': _cycle()}
    values.update(changes)
    return SubscriptionCommercialEnvelope(**values)

def _draft_invoice(*, total=100) -> CommercialInvoiceEnvelope:
    return CommercialInvoiceEnvelope(tenant_id='tenant-a', invoice_id='inv-1', currency='USD', subtotal_minor=total, tax_minor=0, total_minor=total, status=InvoiceLifecycleStatus.DRAFT)

def _issued_invoice(*, total=100, paid=0, status=InvoiceLifecycleStatus.ISSUED) -> CommercialInvoiceEnvelope:
    return CommercialInvoiceEnvelope(tenant_id='tenant-a', invoice_id='inv-1', currency='USD', subtotal_minor=total, tax_minor=0, total_minor=total, paid_minor=paid, status=status, issued_at=NOW, due_at=NOW + timedelta(days=7))

def _result(*, successful=True, **changes) -> CommercialCollectionResult:
    values = {'invoice_id': 'inv-1', 'tenant_id': 'tenant-a', 'provider_name': 'provider-a', 'successful': successful, 'external_reference': 'charge-1' if successful else None, 'failure_reason': None if successful else 'declined', 'processed_at': NOW}
    values.update(changes)
    return CommercialCollectionResult(**values)

def test_subscription_activation_and_strict_day_inputs() -> None:
    service = SubscriptionLifecycleService()
    active = service.activate(tenant_id='tenant-a', subscription_id='sub-1', plan_id='plan-1', activated_at=NOW)
    assert active.status is SubscriptionLifecycleStatus.ACTIVE
    trial = service.activate(tenant_id='tenant-a', subscription_id='sub-2', plan_id='plan-1', interval='weekly', trial_days=2, activated_at=NOW)
    assert trial.status is SubscriptionLifecycleStatus.TRIALING
    assert trial.trial_ends_at == NOW + timedelta(days=2)
    for value in (True, '2', 1.5, -1):
        with pytest.raises(ValueError):
            service.activate(tenant_id='tenant-a', subscription_id='sub-x', plan_id='plan-1', trial_days=value, activated_at=NOW)
    with pytest.raises(ValueError, match='activated_at'):
        service.activate(tenant_id='tenant-a', subscription_id='sub-x', plan_id='plan-1', activated_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError, match='interval'):
        service.activate(tenant_id='tenant-a', subscription_id='sub-x', plan_id='plan-1', interval='annual', activated_at=NOW)

def test_subscription_transitions_and_proration_edges() -> None:
    service = SubscriptionLifecycleService()
    active = _subscription()
    assert service.advance_trial(active, now=NOW) is active
    trial = _subscription(SubscriptionLifecycleStatus.TRIALING, trial_ends_at=NOW + timedelta(days=2))
    assert service.advance_trial(trial, now=NOW + timedelta(days=1)) is trial
    assert service.advance_trial(trial, now=NOW + timedelta(days=2)).status is SubscriptionLifecycleStatus.ACTIVE
    with pytest.raises(ValueError, match='now'):
        service.advance_trial(trial, now=datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        service.mark_past_due(_subscription(SubscriptionLifecycleStatus.SUSPENDED), now=NOW)
    canceled = _subscription(SubscriptionLifecycleStatus.CANCELED, canceled_at=NOW)
    with pytest.raises(ValueError):
        service.mark_past_due(canceled, now=NOW)
    for value in (True, '7', 1.5, -1):
        with pytest.raises(ValueError, match='grace_days'):
            service.mark_past_due(active, grace_days=value, now=NOW)
    past_due = service.mark_past_due(active, grace_days=2, now=NOW)
    assert past_due.grace_until == NOW + timedelta(days=2)
    with pytest.raises(ValueError, match='grace is only'):
        service.enter_grace(active, now=NOW)
    no_deadline = _subscription(SubscriptionLifecycleStatus.PAST_DUE)
    grace = service.enter_grace(no_deadline, now=NOW)
    assert grace.grace_until == NOW + timedelta(days=3)
    assert service.enter_grace(grace, now=NOW).grace_until == grace.grace_until
    assert service.suspend_if_expired(active, now=NOW) is active
    assert service.suspend_if_expired(no_deadline, now=NOW) is no_deadline
    assert service.suspend_if_expired(past_due, now=NOW + timedelta(days=1)) is past_due
    suspended = service.suspend_if_expired(past_due, now=NOW + timedelta(days=2))
    assert suspended.status is SubscriptionLifecycleStatus.SUSPENDED
    with pytest.raises(ValueError, match='now'):
        service.suspend_if_expired(past_due, now=datetime(2026, 1, 1))
    renewed = service.renew_cycle(active, now=NOW)
    assert renewed.cycle.start_at == active.cycle.end_at
    assert renewed.status is SubscriptionLifecycleStatus.ACTIVE
    with pytest.raises(ValueError, match='cannot renew'):
        service.renew_cycle(canceled, now=NOW)
    with pytest.raises(ValueError, match='interval'):
        service.renew_cycle(active, interval='quarterly', now=NOW)
    with pytest.raises(ValueError, match='now'):
        service.renew_cycle(active, now=datetime(2026, 1, 1))
    canceled_now = service.cancel(active, canceled_at=NOW + timedelta(days=1))
    assert canceled_now.status is SubscriptionLifecycleStatus.CANCELED
    with pytest.raises(ValueError, match='canceled_at'):
        service.cancel(active, canceled_at=datetime(2026, 1, 1))
    cycle = _cycle()
    assert service.plan_change_proration_fraction(cycle=cycle, changed_at=cycle.start_at) == 1.0
    assert service.plan_change_proration_fraction(cycle=cycle, changed_at=cycle.end_at) == 0.0
    assert service.plan_change_proration_fraction(cycle=cycle, changed_at=cycle.start_at + timedelta(days=15)) == 0.5
    with pytest.raises(ValueError, match='changed_at'):
        service.plan_change_proration_fraction(cycle=cycle, changed_at=datetime(2026, 1, 1))

    class _ZeroDurationCycle(BillingCycleWindow):

        def validate(self) -> None:
            return None

        @property
        def duration_seconds(self) -> float:
            return 0.0
    zero = _ZeroDurationCycle(start_at=NOW, end_at=NOW + timedelta(days=1))
    assert service.plan_change_proration_fraction(cycle=zero, changed_at=NOW + timedelta(hours=12)) == 0.0

def test_dunning_policy_rejects_coercion_and_builds_monotonic_actions() -> None:
    for policy, message in ((DunningPolicy(grace_days=True), 'grace_days'), (DunningPolicy(grace_days=-1), 'grace_days'), (DunningPolicy(retry_delays_days=()), 'retry_delays_days'), (DunningPolicy(retry_delays_days=(1, '2')), 'retry delay'), (DunningPolicy(retry_delays_days=(1, -1)), 'retry delay'), (DunningPolicy(channel_order=()), 'channel_order'), (DunningPolicy(channel_order=('',)), 'channel names'), (DunningPolicy(metadata=[]), 'metadata')):
        with pytest.raises(ValueError, match=message):
            policy.validate()
    policy = DunningPolicy(grace_days=5, retry_delays_days=(3, 1, 5), channel_order=('email', 'operator'), metadata={'campaign': 'dunning'})
    actions = policy.build_actions(tenant_id='tenant-a', invoice_id='inv-1', started_at=NOW)
    assert [item.execute_at for item in actions] == [NOW + timedelta(days=3), NOW + timedelta(days=3), NOW + timedelta(days=5)]
    assert [item.channel for item in actions] == ['email', 'operator', 'operator']
    assert actions[0].metadata['grace_days'] == 5
    with pytest.raises(ValueError, match='tenant'):
        policy.build_actions(tenant_id='', invoice_id='inv-1', started_at=NOW)
    with pytest.raises(ValueError, match='invoice_id'):
        policy.build_actions(tenant_id='tenant-a', invoice_id='', started_at=NOW)
    with pytest.raises(ValueError, match='started_at'):
        policy.build_actions(tenant_id='tenant-a', invoice_id='inv-1', started_at=datetime(2026, 1, 1))

def test_spend_guard_strict_policy_and_amount_boundaries() -> None:
    for policy, message in ((SpendLimitPolicy(tenant_id=''), 'tenant'), (SpendLimitPolicy(tenant_id='tenant-a', cycle_limit_minor=True), 'integer'), (SpendLimitPolicy(tenant_id='tenant-a', cycle_limit_minor=-1), '>= 0'), (SpendLimitPolicy(tenant_id='tenant-a', hard_stop=1), 'boolean'), (SpendLimitPolicy(tenant_id='tenant-a', currency=''), 'currency'), (SpendLimitPolicy(tenant_id='tenant-a', metadata=[]), 'metadata')):
        with pytest.raises(ValueError, match=message):
            policy.validate()
    guard = SpendGuard(ledger_store=_Ledger())
    for value in (True, '1', 1.5, -1):
        with pytest.raises(ValueError, match='pending_minor'):
            guard.check(policy=SpendLimitPolicy(tenant_id='tenant-a'), pending_minor=value)
    for value in (True, '1', 1.5, -1):
        with pytest.raises(ValueError, match='observed_minor'):
            SpendGuard(ledger_store=_Ledger(total=value)).check(policy=SpendLimitPolicy(tenant_id='tenant-a'), pending_minor=1)
    mixed = SpendGuard(ledger_store=_Ledger(entries=(SimpleNamespace(account_code='billing.accounts.revenue', currency='EUR'), SimpleNamespace(account_code='other', currency='GBP')))).check(policy=SpendLimitPolicy(tenant_id='tenant-a', cycle_limit_minor=100), pending_minor=1)
    assert mixed.allowed is False
    assert mixed.reason == 'mixed_currency_ledger'
    assert guard.check(policy=SpendLimitPolicy(tenant_id='tenant-a'), pending_minor=50).allowed
    assert guard.check(policy=SpendLimitPolicy(tenant_id='tenant-a', cycle_limit_minor=100), pending_minor=50).reason == 'ok'
    hard = guard.check(policy=SpendLimitPolicy(tenant_id='tenant-a', cycle_limit_minor=40), pending_minor=50)
    assert hard.allowed is False and hard.reason == 'spend_limit_exceeded'
    soft = guard.check(policy=SpendLimitPolicy(tenant_id='tenant-a', cycle_limit_minor=40, hard_stop=False), pending_minor=50)
    assert soft.allowed is True and soft.reason == 'spend_limit_soft_exceeded'
    metrics = _Metrics()
    measured = SpendGuard(ledger_store=_Ledger(total=10), metrics=metrics).check(policy=SpendLimitPolicy(tenant_id='tenant-a', cycle_limit_minor=100), pending_minor=20)
    assert measured.projected_minor == 30
    assert metrics.calls[0][0] == 'gauge'

def test_collection_result_store_idempotency_and_tenant_queries() -> None:
    store = InMemoryCollectionResultStore()
    one = _result()
    assert store.append(one, idempotency_key='key-1') is one
    assert store.append(one, idempotency_key='key-1') is one
    with pytest.raises(ValueError, match='collision'):
        store.append(replace(one, external_reference='other'), idempotency_key='key-1')
    two = _result(tenant_id='tenant-b', external_reference='charge-2')
    store.append(two)
    assert store.list_for_invoice('inv-1', tenant_id='tenant-a') == (one,)
    assert store.list_for_invoice('inv-1') == (one, two)
    assert store.get_by_idempotency(tenant_id='tenant-a', invoice_id='inv-1', idempotency_key='key-1') is one

def test_payment_collection_new_success_failure_noop_and_validation() -> None:
    issued = _issued_invoice()
    metrics = _Metrics()
    provider = _Provider(results=[_result()])
    orchestrator = PaymentCollectionOrchestrator(provider=provider, metrics=metrics)
    updated, saved = orchestrator.collect(invoice=issued, idempotency_key='key-1', attempt_no=2, metadata={'source': 'test'})
    assert saved.successful is True
    assert updated.status is InvoiceLifecycleStatus.PAID
    assert provider.attempts[0].attempt_no == 2
    assert provider.attempts[0].metadata == {'source': 'test'}
    assert metrics.calls[0][0] == 'inc'
    failure_provider = _Provider(results=[_result(successful=False)])
    failure_orchestrator = PaymentCollectionOrchestrator(provider=failure_provider)
    unchanged, failed = failure_orchestrator.collect(invoice=issued, idempotency_key='key-fail')
    assert unchanged is issued
    assert failed.successful is False
    zero = _issued_invoice(total=0)
    noop_metrics = _Metrics()
    noop_provider = _Provider(results=[])
    noop_orchestrator = PaymentCollectionOrchestrator(provider=noop_provider, metrics=noop_metrics)
    same, noop = noop_orchestrator.collect(invoice=zero, idempotency_key='noop')
    assert same is zero and noop.metadata['noop'] is True
    assert noop_metrics.calls[0][1]['labels']['noop'] == 'true'
    no_metrics_same, no_metrics_noop = PaymentCollectionOrchestrator(provider=_Provider(results=[])).collect(invoice=zero, idempotency_key='noop-no-metrics')
    assert no_metrics_same is zero and no_metrics_noop.metadata['noop'] is True
    with pytest.raises(ValueError, match='idempotency_key'):
        orchestrator.collect(invoice=issued, idempotency_key='')
    for value in (True, '1', 1.5, 0):
        with pytest.raises(ValueError, match='attempt_no'):
            PaymentCollectionOrchestrator(provider=_Provider(results=[_result()])).collect(invoice=issued, idempotency_key=f'bad-{value}', attempt_no=value)
    for status in (InvoiceLifecycleStatus.DRAFT, InvoiceLifecycleStatus.PAID, InvoiceLifecycleStatus.VOID, InvoiceLifecycleStatus.CREDITED):
        invoice = _draft_invoice() if status is InvoiceLifecycleStatus.DRAFT else _issued_invoice(paid=100 if status is InvoiceLifecycleStatus.PAID else 0, status=status)
        with pytest.raises(ValueError, match='cannot collect'):
            PaymentCollectionOrchestrator(provider=_Provider()).collect(invoice=invoice, idempotency_key=f'state-{status.value}')

def test_payment_collection_replay_safety_and_provider_result_binding() -> None:
    issued = _issued_invoice()
    store = InMemoryCollectionResultStore()
    existing = replace(_result(), metadata={'currency': 'USD', 'collected_amount_minor': 40})
    store.append(existing, idempotency_key='replay')
    provider = _Provider()
    orchestrator = PaymentCollectionOrchestrator(provider=provider, result_store=store)
    replayed, same = orchestrator.collect(invoice=issued, idempotency_key='replay')
    assert same is existing
    assert replayed.paid_minor == 40
    assert provider.attempts == []
    fully_paid = InvoiceLifecycleService().record_payment(issued, amount_minor=100, paid_at=NOW)
    replayed_paid, _ = orchestrator.collect(invoice=fully_paid, idempotency_key='replay')
    assert replayed_paid is fully_paid
    failed_store = InMemoryCollectionResultStore()
    failed_store.append(replace(_result(successful=False), metadata={'currency': 'USD', 'collected_amount_minor': 0}), idempotency_key='failed')
    failed_replay, _ = PaymentCollectionOrchestrator(provider=_Provider(), result_store=failed_store).collect(invoice=issued, idempotency_key='failed')
    assert failed_replay is issued
    bad_amount_store = InMemoryCollectionResultStore()
    bad_amount_store.append(replace(_result(), metadata={'currency': 'USD', 'collected_amount_minor': '40'}), idempotency_key='bad-amount')
    with pytest.raises(ValueError, match='collected_amount_minor'):
        PaymentCollectionOrchestrator(provider=_Provider(), result_store=bad_amount_store).collect(invoice=issued, idempotency_key='bad-amount')
    for replay_invoice in (_draft_invoice(), _issued_invoice(status=InvoiceLifecycleStatus.VOID), _issued_invoice(status=InvoiceLifecycleStatus.CREDITED)):
        with pytest.raises(ValueError, match='cannot replay'):
            orchestrator.collect(invoice=replay_invoice, idempotency_key='replay')
    with pytest.raises(ValueError, match='provider mismatch'):
        PaymentCollectionOrchestrator(provider=_Provider(name='provider-b'), result_store=store).collect(invoice=issued, idempotency_key='replay')
    currency_store = InMemoryCollectionResultStore()
    currency_store.append(replace(_result(), metadata={'currency': 'EUR', 'collected_amount_minor': 40}), idempotency_key='currency')
    with pytest.raises(ValueError, match='currency mismatch'):
        PaymentCollectionOrchestrator(provider=_Provider(), result_store=currency_store).collect(invoice=issued, idempotency_key='currency')
    mismatches = ((_result(invoice_id='other'), 'invoice_id'), (_result(tenant_id='tenant-b'), 'tenant_id'), (_result(provider_name='provider-b'), 'provider_name'))
    for result, message in mismatches:
        with pytest.raises(ValueError, match=message):
            PaymentCollectionOrchestrator(provider=_Provider(results=[result])).collect(invoice=issued, idempotency_key=f'mismatch-{message}')
    with pytest.raises(ValueError, match='retryable'):
        PaymentCollectionOrchestrator(provider=_Provider(results=[_result(retryable=True)])).collect(invoice=issued, idempotency_key='retryable-success')
