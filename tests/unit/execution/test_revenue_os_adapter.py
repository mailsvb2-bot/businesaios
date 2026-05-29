from __future__ import annotations

from datetime import datetime, timezone, UTC

from execution.revenue_os_adapter import RevenueOSAdapter
from runtime.monetization import (
    RevenuePaywallVariantInput,
    RevenuePlanInput,
    RevenuePricePointInput,
    RevenueSnapshotInput,
)


def _snapshot(**overrides):
    base = dict(
        observed_at=datetime(2026, 4, 8, 8, 0, tzinfo=UTC),
        visitors=1000,
        trials_started=100,
        conversions=50,
        retained_subscribers=450,
        churned_subscribers=25,
        refunds=1,
        gross_revenue=2500.0,
        net_revenue=2200.0,
        acquisition_spend=500.0,
        active_subscribers=500,
        trial_subscribers=40,
    )
    base.update(overrides)
    return RevenueSnapshotInput(**base)


def test_revenue_os_adapter_builds_advisory_envelope() -> None:
    adapter = RevenueOSAdapter()
    envelope = adapter.build_envelope(
        tenant_id='tenant-a',
        product_id='product-a',
        snapshots=[_snapshot()],
        plans=[RevenuePlanInput(plan_id='pro', tier='pro', price=RevenuePricePointInput(product_id='product-a', currency='usd', amount=49.0))],
        paywall_variants=[RevenuePaywallVariantInput(variant_id='v1', headline='Start now')],
    )
    assert envelope.world_state_patch['economy']['revenue_world_state']['tenant_id'] == 'tenant-a'
    assert envelope.explain['mode'] == 'advisory_only'
    assert envelope.candidate_actions
    assert all(item['owner'] == 'advisory.revenue_os' for item in envelope.candidate_actions)
