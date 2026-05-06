from pathlib import Path

from execution.economic_audit_bundle import EconomicAuditBundleService
from observability.economic_metrics_store import JsonlEconomicMetricsStore


def test_economic_audit_bundle_exports_and_imports_metrics_rows(tmp_path: Path) -> None:
    metrics_store = JsonlEconomicMetricsStore(tmp_path / 'metrics.jsonl')
    metrics_store.upsert_payload({'snapshot_id': 'snap-1', 'counters': {'economic.budget_guard.total': 2.0}})

    service = EconomicAuditBundleService()
    bundle = service.build_bundle(
        bundle_id='bundle-1',
        feedback_rows=(),
        roi_rows=(),
        snapshot_rows=(),
        trace_rows=(),
        metrics_rows=[row.to_dict() for row in metrics_store.list_rows()],
        audit_summary={'restart_resume_consistent': True},
    )
    path = tmp_path / 'bundle.json'
    service.export_json(bundle=bundle, path=path)
    imported = service.import_json(path=path)
    assert imported.bundle_id == 'bundle-1'
    assert imported.payload['metrics_rows'][0]['snapshot_id'] == 'snap-1'
    assert imported.payload['audit_summary']['restart_resume_consistent'] is True
