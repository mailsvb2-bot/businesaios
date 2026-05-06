from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from billing.commercial_cycle_contract import BillingCycleWindow, SubscriptionCommercialEnvelope, SubscriptionLifecycleStatus, next_cycle_window, utc_now


CANON_BILLING_SUBSCRIPTION_LIFECYCLE = True


class SubscriptionLifecycleService:
    """Passive lifecycle transitions for monetization subscriptions.

    Important:
    - no pricing ownership
    - no product decision ownership
    - status transitions only
    """

    def activate(
        self,
        *,
        tenant_id: str,
        subscription_id: str,
        plan_id: str,
        interval: str = 'monthly',
        trial_days: int = 0,
        activated_at: datetime | None = None,
    ) -> SubscriptionCommercialEnvelope:
        started_at = activated_at or utc_now()
        if started_at.tzinfo is None:
            raise ValueError('activated_at must be timezone-aware')
        cycle = next_cycle_window(current_start_at=started_at, interval=interval)
        trial_days = max(0, int(trial_days))
        status = SubscriptionLifecycleStatus.TRIALING if trial_days else SubscriptionLifecycleStatus.ACTIVE
        trial_ends_at = started_at + timedelta(days=trial_days) if trial_days else None
        envelope = SubscriptionCommercialEnvelope(
            tenant_id=tenant_id,
            subscription_id=str(subscription_id),
            plan_id=str(plan_id),
            status=status,
            cycle=cycle,
            trial_ends_at=trial_ends_at,
            metadata={'owner': 'billing.subscription_lifecycle', 'interval': cycle.anchor},
        )
        envelope.validate()
        return envelope

    def advance_trial(self, envelope: SubscriptionCommercialEnvelope, *, now: datetime | None = None) -> SubscriptionCommercialEnvelope:
        envelope.validate()
        observed_at = now or utc_now()
        if observed_at.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        if envelope.status is not SubscriptionLifecycleStatus.TRIALING:
            return envelope
        if envelope.trial_ends_at is None or observed_at < envelope.trial_ends_at:
            return envelope
        updated = replace(envelope, status=SubscriptionLifecycleStatus.ACTIVE, trial_ends_at=None)
        updated.validate()
        return updated

    def mark_past_due(self, envelope: SubscriptionCommercialEnvelope, *, grace_days: int = 7, now: datetime | None = None) -> SubscriptionCommercialEnvelope:
        envelope.validate()
        observed_at = now or utc_now()
        if observed_at.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        if envelope.status in {SubscriptionLifecycleStatus.SUSPENDED, SubscriptionLifecycleStatus.CANCELED}:
            raise ValueError('cannot mark suspended or canceled subscription as past_due')
        updated = replace(envelope, status=SubscriptionLifecycleStatus.PAST_DUE, grace_until=observed_at + timedelta(days=max(0, int(grace_days))))
        updated.validate()
        return updated

    def enter_grace(self, envelope: SubscriptionCommercialEnvelope, *, now: datetime | None = None) -> SubscriptionCommercialEnvelope:
        envelope.validate()
        observed_at = now or utc_now()
        if observed_at.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        if envelope.status not in {SubscriptionLifecycleStatus.PAST_DUE, SubscriptionLifecycleStatus.GRACE}:
            raise ValueError('grace is only allowed from past_due/grace status')
        updated = replace(envelope, status=SubscriptionLifecycleStatus.GRACE, grace_until=envelope.grace_until or (observed_at + timedelta(days=3)))
        updated.validate()
        return updated

    def suspend_if_expired(self, envelope: SubscriptionCommercialEnvelope, *, now: datetime | None = None) -> SubscriptionCommercialEnvelope:
        envelope.validate()
        observed_at = now or utc_now()
        if observed_at.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        if envelope.status not in {SubscriptionLifecycleStatus.PAST_DUE, SubscriptionLifecycleStatus.GRACE}:
            return envelope
        if envelope.grace_until is None or observed_at < envelope.grace_until:
            return envelope
        updated = replace(envelope, status=SubscriptionLifecycleStatus.SUSPENDED, grace_until=None, trial_ends_at=None)
        updated.validate()
        return updated

    def renew_cycle(self, envelope: SubscriptionCommercialEnvelope, *, interval: str | None = None, now: datetime | None = None) -> SubscriptionCommercialEnvelope:
        envelope.validate()
        observed_at = now or utc_now()
        if observed_at.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        if envelope.status is SubscriptionLifecycleStatus.CANCELED:
            raise ValueError('cannot renew canceled subscription')
        anchor = str(interval or envelope.cycle.anchor).strip().lower()
        cycle_start_at = envelope.cycle.end_at
        next_cycle = next_cycle_window(current_start_at=cycle_start_at, interval=anchor)
        updated = replace(envelope, status=SubscriptionLifecycleStatus.ACTIVE, cycle=next_cycle, grace_until=None, trial_ends_at=None, metadata={**dict(envelope.metadata), 'renewed_at': observed_at.isoformat(), 'interval': anchor})
        updated.validate()
        return updated

    def cancel(self, envelope: SubscriptionCommercialEnvelope, *, canceled_at: datetime | None = None) -> SubscriptionCommercialEnvelope:
        envelope.validate()
        when = canceled_at or utc_now()
        if when.tzinfo is None:
            raise ValueError('canceled_at must be timezone-aware')
        updated = replace(envelope, status=SubscriptionLifecycleStatus.CANCELED, canceled_at=when, grace_until=None, trial_ends_at=None)
        updated.validate()
        return updated

    def plan_change_proration_fraction(self, *, cycle: BillingCycleWindow, changed_at: datetime) -> float:
        cycle.validate()
        if changed_at.tzinfo is None:
            raise ValueError('changed_at must be timezone-aware')
        if changed_at <= cycle.start_at:
            return 1.0
        if changed_at >= cycle.end_at:
            return 0.0
        total_seconds = cycle.duration_seconds
        remaining_seconds = float((cycle.end_at - changed_at).total_seconds())
        if total_seconds <= 0:
            return 0.0
        return max(0.0, min(1.0, remaining_seconds / total_seconds))


__all__ = ['CANON_BILLING_SUBSCRIPTION_LIFECYCLE', 'SubscriptionLifecycleService']
