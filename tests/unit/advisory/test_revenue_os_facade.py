from __future__ import annotations

from datetime import datetime, timezone, UTC

from advisory.revenue_os import PaywallVariant, PricePoint, RevenueOSFacade, RevenueSnapshot, SubscriptionPlan


def _snapshot(**overrides):
    base = dict(
        observed_at=datetime(2026, 4, 8, 8, 0, tzinfo=UTC),
        visitors=1000,
        trials_started=120,
        conversions=60,
        retained_subscribers=400,
        churned_subscribers=20,
        refunds=2,
        gross_revenue=3000.0,
        net_revenue=2700.0,
        acquisition_spend=600.0,
        active_subscribers=450,
        trial_subscribers=50,
    )
    base.update(overrides)
    return RevenueSnapshot(**base)


def test_revenue_os_facade_emits_advisory_surface() -> None:
    facade = RevenueOSFacade()
    report = facade.analyze(
        tenant_id='tenant-a',
        product_id='product-a',
        snapshots=(_snapshot(), _snapshot(conversions=55, net_revenue=2600.0)),
        plans=(
            SubscriptionPlan(plan_id='starter', tier='starter', price=PricePoint(product_id='product-a', currency='usd', amount=19.0)),
            SubscriptionPlan(plan_id='pro', tier='pro', price=PricePoint(product_id='product-a', currency='usd', amount=49.0), recommended=True),
        ),
        paywall_variants=(
            PaywallVariant(variant_id='v1', headline='Try now', social_proof_density=0.7, friction_score=0.2),
            PaywallVariant(variant_id='v2', headline='Upgrade today', social_proof_density=0.4, friction_score=0.5),
        ),
    )
    assert report.summary['experiments_count'] == 1
    assert report.approval.highest_blast_radius in {'moderate', 'high'}
    assert any(item.action_type == 'revenue.pricing.recommendation' for item in report.intents)
    assert all(item.owner == 'advisory.revenue_os' for item in report.intents)
