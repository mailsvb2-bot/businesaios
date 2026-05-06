from execution.economic_audit_bundle import EconomicAuditBundleService
from execution.economic_multi_backend_reconciliation import EconomicMultiBackendReconciliationBuilder
from execution.economic_scope_profile import EconomicScopeProfileResolver


def test_scope_profile_is_propagated_into_export_manifest_and_bundle() -> None:
    resolver = EconomicScopeProfileResolver(base_retention_policy={'max_feedback_rows': 25})
    profile = resolver.resolve(
        action={'tenant_id': 'tenant-a', 'business_id': 'biz-a', 'tenant_tier': 'pro'},
        execution_receipt={},
        economic_policy={},
    )
    service = EconomicAuditBundleService()
    manifest = service.build_export_manifest(
        stores={},
        retention=profile.retention_policy,
        scope=profile.to_dict(),
        node_id='node-a',
    )
    bundle = service.build_bundle(
        bundle_id='bundle-scope-1',
        feedback_rows=[{'event_id': 'evt-1'}],
        roi_rows=[],
        snapshot_rows=[],
        trace_rows=[],
        metrics_rows=[],
        export_manifest=manifest,
        retention_policy=profile.retention_policy,
        scope_profile=profile.to_dict(),
    ).to_dict()
    assert bundle['payload']['export_manifest']['scope']['tenant_id'] == 'tenant-a'
    assert bundle['payload']['metadata']['scope_profile']['profile_name'] == profile.profile_name


def test_reconciliation_reports_scope_mismatch_nodes() -> None:
    recon = EconomicMultiBackendReconciliationBuilder().build(
        feedback_rows=[{'event_id': 'evt-1'}],
        roi_rows=[],
        snapshot_rows=[],
        trace_rows=[],
        metrics_rows=[],
        bundle_payloads=[{'payload': {'feedback_rows': [{'event_id': 'evt-1'}], 'export_manifest': {'scope': {'tenant_id': 'tenant-a', 'business_id': 'biz-a'}}}}],
        node_payloads=[
            {'node_id': 'node-a', 'payload': {'feedback_rows': [{'event_id': 'evt-1'}], 'export_manifest': {'scope': {'tenant_id': 'tenant-a', 'business_id': 'biz-a'}}}},
            {'node_id': 'node-b', 'payload': {'feedback_rows': [{'event_id': 'evt-1'}], 'export_manifest': {'scope': {'tenant_id': 'tenant-z', 'business_id': 'biz-a'}}}},
        ],
        quorum_size=1,
    ).to_dict()
    assert recon['scope_mismatch_node_ids'] == ['node-b']
    assert recon['consistent'] is False
