from __future__ import annotations

from datetime import UTC, datetime

from runtime.monetization import (
    RevenueAdvisoryService,
    RevenuePaywallVariantInput,
    RevenuePlanInput,
    RevenuePricePointInput,
    RevenueSnapshotInput,
)


def test_revenue_advisory_service_builds_runtime_summary() -> None:
    service = RevenueAdvisoryService()
    summary = service.analyze(
        tenant_id='tenant-1',
        product_id='product-1',
        snapshots=(
            RevenueSnapshotInput(
                observed_at=datetime(2026, 4, 9, tzinfo=UTC),
                visitors=1000,
                trials_started=150,
                conversions=60,
                retained_subscribers=55,
                churned_subscribers=5,
                refunds=2,
                gross_revenue=1500.0,
                net_revenue=1450.0,
                acquisition_spend=300.0,
                active_subscribers=80,
                trial_subscribers=20,
            ),
        ),
        plans=(
            RevenuePlanInput(
                plan_id='pro',
                tier='pro',
                price=RevenuePricePointInput(product_id='pro', currency='EUR', amount=29.0),
                seats_included=3,
                recommended=True,
            ),
        ),
        paywall_variants=(
            RevenuePaywallVariantInput(
                variant_id='trial-first',
                headline='Start your free trial',
                emphasizes_trial=True,
                social_proof_density=0.4,
                friction_score=0.2,
            ),
        ),
    )
    payload = service.build_payload(summary)
    assert payload['tenant_id'] == 'tenant-1'
    assert payload['product_id'] == 'product-1'
    assert payload['recommended_subscription_plan_id'] == 'pro'
    assert payload['recommended_paywall_variant_id'] == 'trial-first'
    assert payload['experiments_count'] >= 1


def test_revenue_advisory_service_builds_execution_envelope_from_runtime_contracts() -> None:
    service = RevenueAdvisoryService()
    envelope = service.build_envelope(
        tenant_id='tenant-2',
        product_id='product-2',
        snapshots=(
            RevenueSnapshotInput(
                observed_at=datetime(2026, 4, 9, tzinfo=UTC),
                visitors=200,
                trials_started=50,
                conversions=20,
                retained_subscribers=35,
                churned_subscribers=3,
                refunds=1,
                gross_revenue=900.0,
                net_revenue=850.0,
                acquisition_spend=120.0,
                active_subscribers=40,
                trial_subscribers=10,
            ),
        ),
        plans=(
            RevenuePlanInput(
                plan_id='growth',
                tier='growth',
                price=RevenuePricePointInput(product_id='growth', currency='USD', amount=39.0, trial_days=7),
                recommended=True,
            ),
        ),
        paywall_variants=(RevenuePaywallVariantInput(variant_id='v1', headline='Start now'),),
    )
    assert envelope.world_state_patch['economy']['revenue_world_state']['tenant_id'] == 'tenant-2'
    assert envelope.explain['owner'] == 'runtime.monetization.revenue_advisory'
    assert envelope.candidate_actions
    assert all(item.owner == 'advisory.revenue_os' for item in envelope.candidate_actions)
