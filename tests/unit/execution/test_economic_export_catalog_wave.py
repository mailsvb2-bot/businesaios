from pathlib import Path

from execution.economic_audit_bundle import EconomicAuditBundleService
from execution.economic_multi_backend_reconciliation import EconomicMultiBackendReconciliationBuilder
from execution.economic_store_wiring import EconomicStoreWiring


def test_economic_audit_bundle_write_register_restore_and_manifest(tmp_path: Path) -> None:
    bundle = EconomicStoreWiring(root_dir=tmp_path).build()
    bundle.memory_store.upsert_payload({'event_id': 'evt-1', 'channel': 'ads'})
    bundle.roi_history_store.upsert_payload({'event_id': 'evt-1', 'channel': 'ads'})
    bundle.policy_snapshot_store.append_payload({'snapshot_id': 'snap-1', 'channel': 'ads'})
    bundle.trace_store.append_from_results(
        trace_id='trace-1',
        action_type='launch_campaign',
        budget_guard_result={'allowed': True, 'metadata': {'channel': 'ads'}, 'spend_limits': {'requested_budget': 10.0, 'approved_budget': 8.0}},
        revenue_verification_result={'verified': True, 'revenue_amount': 12.0},
        planning_signals={'channel': 'ads', 'requested_budget': 10.0, 'approved_budget': 8.0},
    )
    bundle.metrics_store.upsert_payload({'snapshot_id': 'evt-1', 'counters': {'economic.budget_guard.total': 1.0}})

    service = EconomicAuditBundleService()
    audit_bundle = service.build_bundle(
        bundle_id='evt-1',
        feedback_rows=[row.to_dict() for row in bundle.memory_store.list_rows()],
        roi_rows=[row.to_dict() for row in bundle.roi_history_store.list_rows()],
        snapshot_rows=[row.to_dict() for row in bundle.policy_snapshot_store.list_rows()],
        trace_rows=[row.to_dict() for row in bundle.trace_store.list_rows()],
        metrics_rows=[row.to_dict() for row in bundle.metrics_store.list_rows()],
        export_manifest=service.build_export_manifest(stores={
            'memory_store': bundle.memory_store,
            'roi_history_store': bundle.roi_history_store,
            'policy_snapshot_store': bundle.policy_snapshot_store,
            'trace_store': bundle.trace_store,
            'metrics_store': bundle.metrics_store,
        }),
    )
    entry = service.write_bundle(
        bundle=audit_bundle,
        root_dir=bundle.root_dir,
        bundle_name='evt-1',
        catalog_path=bundle.bundle_catalog_path,
    )
    restored = service.restore_bundle(bundle_path=entry['path'])
    assert restored['bundle_id'] == 'evt-1'
    assert restored['payload']['export_manifest']['memory_store']['row_count'] == 1
    assert Path(entry['path']).exists()
    assert Path(entry['catalog_path']).exists()


def test_economic_multi_backend_reconciliation_matches_written_bundle(tmp_path: Path) -> None:
    service = EconomicAuditBundleService()
    bundle = service.build_bundle(
        bundle_id='evt-2',
        feedback_rows=[{'event_id': 'evt-2', 'channel': 'seo'}],
        roi_rows=[{'event_id': 'evt-2', 'channel': 'seo'}],
        snapshot_rows=[{'snapshot_id': 'snap-2'}],
        trace_rows=[{'trace_id': 'trace-2'}],
        metrics_rows=[{'snapshot_id': 'evt-2'}],
    ).to_dict()
    recon = EconomicMultiBackendReconciliationBuilder().build(
        feedback_rows=[{'event_id': 'evt-2', 'channel': 'seo'}],
        roi_rows=[{'event_id': 'evt-2', 'channel': 'seo'}],
        snapshot_rows=[{'snapshot_id': 'snap-2'}],
        trace_rows=[{'trace_id': 'trace-2'}],
        metrics_rows=[{'snapshot_id': 'evt-2'}],
        bundle_payloads=[bundle],
    ).to_dict()
    assert recon['consistent'] is True
    assert recon['bundle_count'] == 1
    assert recon['missing_feedback_event_ids'] == []
