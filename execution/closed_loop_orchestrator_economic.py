from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from execution.economic_bundle_immutability import EconomicBundleImmutabilityValidator
from execution.economic_lineage_lock import EconomicLineageLockBuilder
from execution.economic_multi_backend_reconciliation import EconomicMultiBackendReconciliationBuilder
from execution.economic_replay_epoch_guard import EconomicReplayEpochGuard
from execution.economic_schema_migration_matrix import EconomicSchemaMigrationMatrix
from execution.economic_schema_validation import EconomicSchemaValidator
from execution.economic_scope_lineage import EconomicScopeLineageGuard
from execution.economic_segment_validation import EconomicSegmentValidator
from execution.economic_semantic_validation import EconomicSemanticValidator
from execution.economic_state_monotonicity import EconomicStateMonotonicityGuard
from execution.closed_loop_orchestrator_support import _safe_dict
from execution.economic_retention_policy import EconomicRetentionPolicy


def build_economic_store_mapping(*, economic_memory_store, roi_history_store, economic_policy_snapshot_store, economic_trace_store, economic_metrics_store) -> dict[str, object]:
    return {
        'memory_store': economic_memory_store,
        'roi_history_store': roi_history_store,
        'policy_snapshot_store': economic_policy_snapshot_store,
        'trace_store': economic_trace_store,
        'metrics_store': economic_metrics_store,
    }


def build_economic_audit_bundle(*, economic_audit_bundle_service, economic_memory_store, roi_history_store, economic_policy_snapshot_store, economic_trace_store, economic_metrics_store, economic_retention_policy: EconomicRetentionPolicy, economic_store_bundle, bundle_id: str, audit_summary: Mapping[str, Any] | None = None, scope_profile: Mapping[str, Any] | None = None, retention_policy: EconomicRetentionPolicy | None = None) -> dict[str, Any]:
    bundle = economic_audit_bundle_service.build_bundle(
        bundle_id=bundle_id,
        feedback_rows=[row.to_dict() for row in economic_memory_store.list_rows()],
        roi_rows=[row.to_dict() for row in roi_history_store.list_rows()],
        snapshot_rows=[row.to_dict() for row in economic_policy_snapshot_store.list_rows()],
        trace_rows=[row.to_dict() for row in economic_trace_store.list_rows()],
        metrics_rows=[row.to_dict() for row in economic_metrics_store.list_rows()],
        audit_summary=audit_summary,
        export_manifest=economic_audit_bundle_service.build_export_manifest(
            stores=build_economic_store_mapping(
                economic_memory_store=economic_memory_store,
                roi_history_store=roi_history_store,
                economic_policy_snapshot_store=economic_policy_snapshot_store,
                economic_trace_store=economic_trace_store,
                economic_metrics_store=economic_metrics_store,
            ),
            retention=(retention_policy or economic_retention_policy).to_dict(),
            node_id=(economic_store_bundle.node_id if economic_store_bundle is not None else 'local-primary'),
            scope=scope_profile,
            scope_lineage={'old_scope': dict(scope_profile or {}), 'new_scope': dict(scope_profile or {})},
        ),
        retention_policy=(retention_policy or economic_retention_policy),
        scope_profile=scope_profile,
    )
    return bundle.to_dict()


def write_economic_audit_bundle(*, economic_audit_bundle_service, economic_store_bundle, bundle_name: str, bundle: Mapping[str, Any]) -> dict[str, Any]:
    if economic_store_bundle is None:
        return {'bundle_kind': 'economic', 'bundle_name': str(bundle_name), 'path': ''}
    from execution.economic_audit_bundle import EconomicAuditBundle
    bundle_obj = EconomicAuditBundle(
        bundle_id=str(bundle.get('bundle_id') or bundle_name),
        payload=_safe_dict(bundle.get('payload')),
        digest=str(bundle.get('digest') or ''),
    )
    return economic_audit_bundle_service.write_bundle(
        bundle=bundle_obj,
        root_dir=economic_store_bundle.root_dir,
        bundle_name=bundle_name,
        catalog_path=economic_store_bundle.bundle_catalog_path,
    )


def build_economic_bundle_reconciliation(*, economic_audit_bundle_service, economic_multi_backend_reconciliation: EconomicMultiBackendReconciliationBuilder, economic_forensics_service, economic_store_bundle, economic_memory_store, roi_history_store, economic_policy_snapshot_store, economic_trace_store, economic_metrics_store, bundle: Mapping[str, Any], bundle_entry: Mapping[str, Any] | None = None) -> dict[str, Any]:
    bundle_payloads = [bundle]
    entry = _safe_dict(bundle_entry)
    bundle_path = str(entry.get('path') or '').strip()
    expected_scope = _safe_dict(_safe_dict(_safe_dict(bundle).get('payload')).get('export_manifest')).get('scope') if _safe_dict(bundle).get('payload') else _safe_dict(_safe_dict(bundle).get('export_manifest')).get('scope')
    expected_profile_name = str(_safe_dict(expected_scope).get('profile_name') or '').strip() or None
    import_validation = {'valid': True, 'issues': [], 'source': 'in_memory_bundle'}
    if bundle_path:
        try:
            restored_bundle = economic_audit_bundle_service.restore_bundle(
                bundle_path=bundle_path,
                strict_validation=True,
                expected_scope=_safe_dict(expected_scope),
                expected_profile_name=expected_profile_name,
                require_bundle_segment=False,
            )
            restored_payload = _safe_dict(restored_bundle.get('payload')) or _safe_dict(restored_bundle)
            schema_verdict = EconomicSchemaValidator().validate(payload=restored_payload)
            migration_verdict = EconomicSchemaMigrationMatrix().validate(bundle_payload=restored_payload)
            segment_verdict = EconomicSegmentValidator().validate(payload=restored_payload)
            semantic_verdict = EconomicSemanticValidator().validate(payload=restored_payload)
            scope_lineage_verdict = EconomicScopeLineageGuard().validate(
                current_scope=_safe_dict(expected_scope),
                incoming_scope=_safe_dict(_safe_dict(restored_payload.get('export_manifest')).get('scope')),
                declared_lineage=_safe_dict(_safe_dict(restored_payload.get('export_manifest')).get('scope_lineage')),
            )
            replay_epoch_verdict = EconomicReplayEpochGuard().validate(current_state={}, incoming_payload=restored_payload)
            monotonicity_verdict = EconomicStateMonotonicityGuard().validate(current_state={}, incoming_payload=restored_payload)
            lineage_lock_verdict = EconomicLineageLockBuilder().validate(manifest=_safe_dict(restored_payload.get('export_manifest')), expected_scope=_safe_dict(expected_scope))
            immutability_verdict = EconomicBundleImmutabilityValidator().validate(bundle=restored_bundle)
            if not migration_verdict.supported:
                raise ValueError(migration_verdict.reason)
            if not monotonicity_verdict.valid:
                raise ValueError(monotonicity_verdict.reason)
            if not lineage_lock_verdict.valid:
                raise ValueError(lineage_lock_verdict.reason)
            if not immutability_verdict.valid:
                raise ValueError(immutability_verdict.reason)
            bundle_payloads = [restored_bundle]
            import_validation = {
                'valid': True,
                'issues': [],
                'source': 'bundle_restore',
                'status': 'valid',
                'schema': schema_verdict.to_dict(),
                'migration': migration_verdict.to_dict(),
                'segments': segment_verdict.to_dict(),
                'semantic': semantic_verdict.to_dict(),
                'scope_lineage': scope_lineage_verdict.to_dict(),
                'replay_epoch': replay_epoch_verdict.to_dict(),
                'monotonicity': monotonicity_verdict.to_dict(),
                'lineage_lock': lineage_lock_verdict.to_dict(),
                'immutability': immutability_verdict.to_dict(),
            }
        except Exception as exc:
            import_validation = {'valid': False, 'issues': [str(exc)], 'source': 'bundle_restore', 'status': 'invalid'}
    node_payloads = []
    if bundle_payloads:
        restored_payload = _safe_dict(_safe_dict(bundle_payloads[0]).get('payload')) or _safe_dict(bundle_payloads[0])
        local_payload = {
            'feedback_rows': [row.to_dict() for row in economic_memory_store.list_rows()],
            'roi_rows': [row.to_dict() for row in roi_history_store.list_rows()],
            'snapshot_rows': [row.to_dict() for row in economic_policy_snapshot_store.list_rows()],
            'trace_rows': [row.to_dict() for row in economic_trace_store.list_rows()],
            'metrics_rows': [row.to_dict() for row in economic_metrics_store.list_rows()],
            'export_manifest': _safe_dict(_safe_dict(bundle_payloads[0].get('payload')).get('export_manifest') or _safe_dict(bundle_payloads[0]).get('export_manifest')),
            'metadata': {'import_validation_status': 'valid'},
        }
        local_node_id = economic_store_bundle.node_id if economic_store_bundle is not None else 'local-primary'
        node_payloads = [
            {'node_id': local_node_id, 'payload': local_payload},
            {'node_id': 'bundle-restore', 'payload': {**restored_payload, 'metadata': {**_safe_dict(restored_payload.get('metadata')), 'import_validation_status': import_validation.get('status', 'valid' if import_validation.get('valid') else 'invalid')}}},
        ]
    reconciliation = economic_multi_backend_reconciliation.build(
        feedback_rows=[row.to_dict() for row in economic_memory_store.list_rows()],
        roi_rows=[row.to_dict() for row in roi_history_store.list_rows()],
        snapshot_rows=[row.to_dict() for row in economic_policy_snapshot_store.list_rows()],
        trace_rows=[row.to_dict() for row in economic_trace_store.list_rows()],
        metrics_rows=[row.to_dict() for row in economic_metrics_store.list_rows()],
        bundle_payloads=bundle_payloads,
        node_payloads=node_payloads,
        quorum_size=2,
    ).to_dict()
    reconciliation['import_validation'] = import_validation
    restored_manifest = _safe_dict(_safe_dict(bundle_payloads[0].get('payload')).get('export_manifest') or _safe_dict(bundle_payloads[0]).get('export_manifest')) if bundle_payloads else {}
    economic_forensics_service.record_event(
        event_type='economic_reconciliation_completed',
        severity='info' if reconciliation.get('consistent') else 'warning',
        artifact_id=str(_safe_dict(bundle).get('bundle_id') or _safe_dict(_safe_dict(bundle).get('payload')).get('bundle_id') or ''),
        artifact_digest=str(_safe_dict(bundle).get('digest') or ''),
        scope=_safe_dict(restored_manifest.get('scope')),
        schema_version=str(restored_manifest.get('bundle_schema_version') or ''),
        payload={'consistent': bool(reconciliation.get('consistent')), 'quorum_failure_segments': list(_safe_dict(reconciliation.get('metadata')).get('quorum_failure_segments') or ())},
        tags=('economic', 'reconciliation', 'forensics'),
    )
    return reconciliation


def build_cross_run_economic_audit(*, cross_run_economic_audit, economic_memory_store, roi_history_store, economic_policy_snapshot_store) -> dict[str, Any]:
    feedback_rows = tuple(row.to_dict() for row in getattr(economic_memory_store, 'list_rows', lambda: ())())
    roi_rows = tuple(row.to_dict() for row in getattr(roi_history_store, 'list_rows', lambda: ())())
    snapshot_rows = tuple(row.to_dict() for row in getattr(economic_policy_snapshot_store, 'list_rows', lambda: ())())
    return cross_run_economic_audit.build(feedback_rows=feedback_rows, roi_rows=roi_rows, snapshot_rows=snapshot_rows).to_dict()


def extract_economic_payload(*, action: Mapping[str, Any], execution_receipt: Mapping[str, Any], verification: Mapping[str, Any], persisted_payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    for source in (action, execution_receipt, verification, persisted_payload):
        source_payload = _safe_dict(source)
        economic = _safe_dict(source_payload.get("economic_safety"))
        if economic:
            return _safe_dict(economic.get("budget_guard")), _safe_dict(economic.get("revenue_verification"))
        if source_payload.get("budget_guard") or source_payload.get("revenue_verification"):
            return _safe_dict(source_payload.get("budget_guard")), _safe_dict(source_payload.get("revenue_verification"))
    return {}, {}
