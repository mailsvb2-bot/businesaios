from __future__ import annotations

from datetime import UTC, datetime

from billing.plan_contract import BillingPlanSpec, PlanRateCardItem
from billing.revenue_os_bridge import BillingRevenueOSBridge
from tenancy.tenant_contract import TenantPlan


def test_billing_revenue_os_bridge_translates_plan_and_defaults() -> None:
    bridge = BillingRevenueOSBridge()
    plan = BillingPlanSpec(
        plan_id=TenantPlan.GROWTH,
        display_name='Pro',
        rate_card=(PlanRateCardItem(meter_key='actions', unit_price=0.05, currency='eur', included_units=100),),
        metadata={'base_amount': 49.0, 'interval': 'monthly', 'trial_days': 7, 'included_seats': 5, 'recommended': True},
        created_at=datetime(2026, 4, 9, tzinfo=UTC),
    )
    subscription_plan = bridge.subscription_plan_from_spec(plan)
    paywalls = bridge.default_paywall_variants((plan,))

    assert subscription_plan.plan_id == 'growth'
    assert subscription_plan.price.currency == 'EUR'
    assert subscription_plan.price.trial_days == 7
    assert subscription_plan.seats_included == 5
    assert len(paywalls) == 2
    assert all(item.metadata['owner'] == 'billing.revenue_os_bridge' for item in paywalls)
