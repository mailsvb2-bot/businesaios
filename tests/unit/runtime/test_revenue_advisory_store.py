from __future__ import annotations

from pathlib import Path

from runtime.monetization import FileRevenueExperimentRegistry
from runtime.monetization import RevenueExperimentSurface
from runtime.monetization import build_revenue_advisory_store_wiring


def test_file_revenue_experiment_registry_roundtrip(tmp_path: Path) -> None:
    registry = FileRevenueExperimentRegistry(path=tmp_path / 'experiments.json')
    experiment = RevenueExperimentSurface(
        experiment_id='exp-1',
        kind='pricing',
        hypothesis='Lower friction increases conversion',
        metric_primary='conversion_rate',
        metric_guardrails=('refund_rate',),
        arms=({'arm_id': 'control', 'allocation': 0.5}, {'arm_id': 'treatment', 'allocation': 0.5}),
        holdout_allocation=0.1,
        max_daily_exposure=100,
        created_at='2026-04-09T00:00:00+00:00',
        metadata={'owner': 'runtime.monetization'},
    )

    registered = registry.put_if_absent(dedup_key='tenant-a:exp-1', experiment=experiment)
    fetched = registry.get('tenant-a:exp-1')

    assert registered.experiment.experiment_id == 'exp-1'
    assert fetched is not None
    assert fetched.experiment.metric_primary == 'conversion_rate'
    assert fetched.experiment.max_daily_exposure == 100


def test_build_revenue_advisory_store_wiring_uses_runtime_owner_root(tmp_path: Path) -> None:
    wiring = build_revenue_advisory_store_wiring(root_dir=tmp_path)

    wiring.audit_store.append({'kind': 'audit', 'value': 1})
    wiring.evidence_store.append({'kind': 'evidence', 'value': 2})
    wiring.telemetry_store.append({'kind': 'telemetry', 'value': 3})

    assert (tmp_path / 'audit.jsonl').exists()
    assert (tmp_path / 'evidence.jsonl').exists()
    assert (tmp_path / 'telemetry.jsonl').exists()
