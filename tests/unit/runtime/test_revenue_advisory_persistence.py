from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest

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
from storage.evidence_store import InMemoryEvidenceStore


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
    evidence_store = InMemoryEvidenceStore()
    wiring = build_revenue_advisory_store_wiring(root_dir=tmp_path / 'runtime', evidence_store=evidence_store)
    service = RevenueAdvisoryService()
    snapshots, plans, variants = _inputs()
    envelope = service.build_envelope(tenant_id='tenant-1', product_id='product-1', snapshots=snapshots, plans=plans, paywall_variants=variants)

    first = persist_revenue_advisory_envelope(wiring=wiring, tenant_id='tenant-1', product_id='product-1', envelope=envelope)
    second = persist_revenue_advisory_envelope(wiring=wiring, tenant_id='tenant-1', product_id='product-1', envelope=envelope)

    assert first['registered_experiments'] >= 1
    assert second['registered_experiments'] == 0
    audit_lines = (tmp_path / 'runtime' / 'audit.jsonl').read_text(encoding='utf-8').strip().splitlines()
    evidence_rows = evidence_store.list_for_tenant(tenant_id='tenant-1')
    telemetry_lines = (tmp_path / 'runtime' / 'telemetry.jsonl').read_text(encoding='utf-8').strip().splitlines()
    assert audit_lines
    assert len(evidence_rows) == 1
    assert evidence_rows[0].source_type == 'revenue_advisory'
    assert evidence_rows[0].business_id == 'unknown'
    assert evidence_rows[0].lineage['derived_fact'].startswith('revenue-advisory:')
    assert not (tmp_path / 'runtime' / 'evidence.jsonl').exists()
    assert telemetry_lines
    telemetry = json.loads(telemetry_lines[-1])
    assert telemetry['owner'] == 'runtime.monetization.revenue_advisory'
    assert telemetry['mode'] == 'advisory_only'


def test_revenue_os_runtime_persists_and_returns_execution_envelope(tmp_path) -> None:
    evidence_store = InMemoryEvidenceStore()
    runtime = RevenueOSRuntime(
        wiring=build_revenue_advisory_store_wiring(root_dir=tmp_path / 'runtime', evidence_store=evidence_store)
    )
    snapshots, plans, variants = _inputs()
    result = runtime.analyze(tenant_id='tenant-2', product_id='product-2', snapshots=snapshots, plans=plans, paywall_variants=variants)

    assert result.envelope.candidate_actions
    assert result.persisted['telemetry_records'] == 1
    assert result.persisted['registered_experiments'] >= 1
    registry_payload = json.loads((tmp_path / 'runtime' / 'experiments.json').read_text(encoding='utf-8'))
    assert registry_payload
    rows = evidence_store.list_for_tenant(tenant_id='tenant-2')
    assert len(rows) == 1
    assert rows[0].labels['product_id'] == 'product-2'



def _legacy_evidence_row(*, tenant_id: str, product_id: str, envelope) -> dict:
    explain = dict(envelope.explain or {})
    return {
        'tenant_id': tenant_id,
        'product_id': product_id,
        'owner': str(explain.get('owner') or ''),
        'world_state_patch': dict(envelope.world_state_patch),
        'candidate_actions': [
            {
                'action_type': item.action_type,
                'kind': item.kind,
                'confidence': item.confidence,
                'payload': dict(item.payload),
                'evidence': dict(item.evidence),
                'reason_codes': list(item.reason_codes),
                'blast_radius': item.blast_radius,
                'requires_approval': item.requires_approval,
                'owner': item.owner,
            }
            for item in envelope.candidate_actions
        ],
        'experiments': [
            {
                'experiment_id': item.experiment_id,
                'kind': item.kind,
                'hypothesis': item.hypothesis,
                'metric_primary': item.metric_primary,
                'metric_guardrails': list(item.metric_guardrails),
                'arms': [dict(arm) for arm in item.arms],
                'holdout_allocation': item.holdout_allocation,
                'max_daily_exposure': item.max_daily_exposure,
                'created_at': item.created_at,
                'metadata': dict(item.metadata),
            }
            for item in envelope.experiments
        ],
    }


def test_revenue_wiring_backfills_legacy_evidence_and_current_replay_is_compatible(tmp_path) -> None:
    root = tmp_path / 'runtime'
    root.mkdir(parents=True)
    service = RevenueAdvisoryService()
    snapshots, plans, variants = _inputs()
    envelope = service.build_envelope(
        tenant_id='tenant-legacy', product_id='product-legacy',
        snapshots=snapshots, plans=plans, paywall_variants=variants,
    )
    legacy_row = _legacy_evidence_row(
        tenant_id='tenant-legacy', product_id='product-legacy', envelope=envelope
    )
    legacy_path = root / 'evidence.jsonl'
    legacy_text = json.dumps(legacy_row, ensure_ascii=False, sort_keys=True) + '\n'
    legacy_path.write_text(legacy_text, encoding='utf-8')
    legacy_mtime = datetime.fromtimestamp(legacy_path.stat().st_mtime, tz=UTC)
    canonical = InMemoryEvidenceStore()

    wiring = build_revenue_advisory_store_wiring(root_dir=root, evidence_store=canonical)
    rows = canonical.list_for_tenant(tenant_id='tenant-legacy')
    assert len(rows) == 1
    migrated = rows[0]
    assert migrated.created_at == legacy_mtime
    assert migrated.source_type == 'revenue_advisory'
    assert migrated.labels['product_id'] == 'product-legacy'
    assert migrated.payload['mode'] == 'advisory_only'
    assert migrated.lineage['derived_fact'].startswith('revenue-advisory:')

    build_revenue_advisory_store_wiring(root_dir=root, evidence_store=canonical)
    assert canonical.list_for_tenant(tenant_id='tenant-legacy') == (migrated,)

    persist_revenue_advisory_envelope(
        wiring=wiring,
        tenant_id='tenant-legacy',
        product_id='product-legacy',
        envelope=envelope,
    )
    assert canonical.list_for_tenant(tenant_id='tenant-legacy') == (migrated,)
    assert legacy_path.read_text(encoding='utf-8') == legacy_text


def test_revenue_legacy_backfill_deduplicates_identical_historical_rows(tmp_path) -> None:
    root = tmp_path / 'runtime'
    root.mkdir(parents=True)
    service = RevenueAdvisoryService()
    snapshots, plans, variants = _inputs()
    envelope = service.build_envelope(
        tenant_id='tenant-dup', product_id='product-dup',
        snapshots=snapshots, plans=plans, paywall_variants=variants,
    )
    legacy_row = _legacy_evidence_row(tenant_id='tenant-dup', product_id='product-dup', envelope=envelope)
    line = json.dumps(legacy_row, ensure_ascii=False, sort_keys=True)
    (root / 'evidence.jsonl').write_text(f'{line}\n{line}\n', encoding='utf-8')
    canonical = InMemoryEvidenceStore()

    build_revenue_advisory_store_wiring(root_dir=root, evidence_store=canonical)

    assert len(canonical.list_for_tenant(tenant_id='tenant-dup')) == 1


def test_revenue_legacy_backfill_fails_closed_on_corrupt_json(tmp_path) -> None:
    root = tmp_path / 'runtime'
    root.mkdir(parents=True)
    legacy_path = root / 'evidence.jsonl'
    legacy_path.write_text('{broken-json\n', encoding='utf-8')

    with pytest.raises(ValueError, match='invalid JSON at line 1'):
        build_revenue_advisory_store_wiring(
            root_dir=root, evidence_store=InMemoryEvidenceStore()
        )



def test_revenue_legacy_backfill_rejects_conflicting_canonical_record(tmp_path) -> None:
    root = tmp_path / 'runtime'
    root.mkdir(parents=True)
    service = RevenueAdvisoryService()
    snapshots, plans, variants = _inputs()
    envelope = service.build_envelope(
        tenant_id='tenant-conflict', product_id='product-conflict',
        snapshots=snapshots, plans=plans, paywall_variants=variants,
    )
    legacy_row = _legacy_evidence_row(
        tenant_id='tenant-conflict', product_id='product-conflict', envelope=envelope
    )
    (root / 'evidence.jsonl').write_text(
        json.dumps(legacy_row, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8'
    )
    source = InMemoryEvidenceStore()
    build_revenue_advisory_store_wiring(root_dir=root, evidence_store=source)
    migrated = source.list_for_tenant(tenant_id='tenant-conflict')[0]

    conflicting = InMemoryEvidenceStore()
    conflicting.append(
        replace(migrated, payload={**dict(migrated.payload), 'mode': 'tampered'}).normalized_for_write()
    )

    with pytest.raises(ValueError, match='conflicts with canonical evidence at line 1'):
        build_revenue_advisory_store_wiring(root_dir=root, evidence_store=conflicting)
