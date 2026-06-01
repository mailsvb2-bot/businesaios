from __future__ import annotations

import json
from datetime import UTC, datetime

from execution.revenue_os_runtime import RevenueOSRuntime
from runtime.monetization import (
    RevenueAdvisoryService,
    RevenuePaywallVariantInput,
    RevenuePlanInput,
    RevenuePricePointInput,
    RevenueSnapshotInput,
    build_revenue_advisory_store_wiring,
    persist_revenue_advisory_envelope,
)


def _inputs():
    snapshots = (
        RevenueSnapshotInput(
            observed_at=datetime(2026, 4, 9, tzinfo=UTC),
            visitors=500,
            trials_started=100,
            conversions=40,
            retained_subscribers=35,
            churned_subscribers=4,
            refunds=1,
            gross_revenue=1200.0,
            net_revenue=1160.0,
            acquisition_spend=250.0,
            active_subscribers=55,
            trial_subscribers=15,
        ),
    )
    plans = (
        RevenuePlanInput(
            plan_id='pro',
            tier='pro',
            price=RevenuePricePointInput(product_id='pro', currency='EUR', amount=29.0, trial_days=7),
            recommended=True,
        ),
    )
    variants = (RevenuePaywallVariantInput(variant_id='trial-first', headline='Try first', emphasizes_trial=True),)
    return snapshots, plans, variants


def test_persist_revenue_advisory_envelope_registers_experiments_once(tmp_path) -> None:
    wiring = build_revenue_advisory_store_wiring(root_dir=tmp_path / 'runtime')
    service = RevenueAdvisoryService()
    snapshots, plans, variants = _inputs()
    envelope = service.build_envelope(tenant_id='tenant-1', product_id='product-1', snapshots=snapshots, plans=plans, paywall_variants=variants)

    first = persist_revenue_advisory_envelope(wiring=wiring, tenant_id='tenant-1', product_id='product-1', envelope=envelope)
    second = persist_revenue_advisory_envelope(wiring=wiring, tenant_id='tenant-1', product_id='product-1', envelope=envelope)

    assert first['registered_experiments'] >= 1
    assert second['registered_experiments'] == 0
    audit_lines = (tmp_path / 'runtime' / 'audit.jsonl').read_text(encoding='utf-8').strip().splitlines()
    evidence_lines = (tmp_path / 'runtime' / 'evidence.jsonl').read_text(encoding='utf-8').strip().splitlines()
    telemetry_lines = (tmp_path / 'runtime' / 'telemetry.jsonl').read_text(encoding='utf-8').strip().splitlines()
    assert audit_lines
    assert evidence_lines
    assert telemetry_lines
    telemetry = json.loads(telemetry_lines[-1])
    assert telemetry['owner'] == 'runtime.monetization.revenue_advisory'
    assert telemetry['mode'] == 'advisory_only'


def test_revenue_os_runtime_persists_and_returns_execution_envelope(tmp_path) -> None:
    runtime = RevenueOSRuntime(wiring=build_revenue_advisory_store_wiring(root_dir=tmp_path / 'runtime'))
    snapshots, plans, variants = _inputs()
    result = runtime.analyze(tenant_id='tenant-2', product_id='product-2', snapshots=snapshots, plans=plans, paywall_variants=variants)

    assert result.envelope.candidate_actions
    assert result.persisted['telemetry_records'] == 1
    assert result.persisted['registered_experiments'] >= 1
    registry_payload = json.loads((tmp_path / 'runtime' / 'experiments.json').read_text(encoding='utf-8'))
    assert registry_payload
