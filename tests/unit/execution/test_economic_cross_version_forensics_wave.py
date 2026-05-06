from __future__ import annotations

from pathlib import Path

import pytest

from compliance.economic_forensics_service import EconomicForensicsService
from compliance.economic_forensics_store import InMemoryEconomicForensicsStore
from execution.economic_audit_bundle import EconomicAuditBundleService
from execution.economic_bundle_quarantine_store import InMemoryEconomicBundleQuarantineStore
from execution.economic_schema_migration_matrix import EconomicSchemaMigrationMatrix


def _scope() -> dict[str, str]:
    return {
        'tenant_id': 'tenant-a',
        'business_id': 'biz-a',
        'tenant_tier': 'standard',
        'business_tier': 'standard',
        'profile_name': 'standard',
    }


def test_schema_migration_matrix_allows_forward_compatibility_path() -> None:
    verdict = EconomicSchemaMigrationMatrix().validate(
        bundle_payload={'export_manifest': {'bundle_schema_version': '1'}},
    )
    assert verdict.supported is True
    assert verdict.migration_required is True
    assert verdict.allowed_path == ('1', '2')


def test_schema_migration_matrix_denies_unknown_future_version() -> None:
    verdict = EconomicSchemaMigrationMatrix().validate(
        bundle_payload={'export_manifest': {'bundle_schema_version': '3'}},
    )
    assert verdict.supported is False
    assert verdict.reason == 'economic_schema_downgrade_forbidden'


def test_audit_bundle_service_records_forensics_on_export_and_validated_import(tmp_path: Path) -> None:
    forensics_store = InMemoryEconomicForensicsStore()
    quarantine = InMemoryEconomicBundleQuarantineStore()
    service = EconomicAuditBundleService(
        quarantine_sink=quarantine,
        forensics_service=EconomicForensicsService(store=forensics_store),
    )
    scope = _scope()
    manifest = service.build_export_manifest(stores={}, node_id='node-a', scope=scope, scope_lineage={'old_scope': scope, 'new_scope': scope})
    bundle = service.build_bundle(
        bundle_id='evt-1',
        feedback_rows=[{'event_id': 'evt-1', 'verified': True, 'realized_revenue': 10.0}],
        roi_rows=[],
        snapshot_rows=[{'snapshot_id': 'snap-1'}],
        trace_rows=[{'trace_id': 'trace-1', 'event_id': 'evt-1'}],
        metrics_rows=[{'snapshot_id': 'snap-1'}],
        export_manifest=manifest,
        scope_profile=scope,
    )
    path = tmp_path / 'bundle.json'
    service.export_json(bundle=bundle, path=path)
    service.restore_bundle(bundle_path=path, strict_validation=True, expected_scope=scope, expected_profile_name='standard')
    event_types = [row.event_type for row in forensics_store.list_rows()]
    assert 'economic_bundle_exported' in event_types
    assert 'economic_bundle_import_validated' in event_types


def test_audit_bundle_service_records_forensics_on_invalid_import(tmp_path: Path) -> None:
    forensics_store = InMemoryEconomicForensicsStore()
    quarantine = InMemoryEconomicBundleQuarantineStore()
    service = EconomicAuditBundleService(
        quarantine_sink=quarantine,
        forensics_service=EconomicForensicsService(store=forensics_store),
    )
    scope = _scope()
    manifest = service.build_export_manifest(stores={}, node_id='node-a', scope=scope, scope_lineage={'old_scope': scope, 'new_scope': scope})
    bundle = service.build_bundle(
        bundle_id='evt-1',
        feedback_rows=[{'event_id': 'evt-1', 'verified': True, 'realized_revenue': 10.0}],
        roi_rows=[],
        snapshot_rows=[{'snapshot_id': 'snap-1'}],
        trace_rows=[{'trace_id': 'trace-1', 'event_id': 'evt-1'}],
        metrics_rows=[{'snapshot_id': 'snap-1'}],
        export_manifest=manifest,
        scope_profile=scope,
    )
    path = tmp_path / 'bundle.json'
    service.export_json(bundle=bundle, path=path)
    raw = path.read_text(encoding='utf-8').replace('"bundle_schema_version":"2"', '"bundle_schema_version":"3"')
    path.write_text(raw, encoding='utf-8')

    with pytest.raises(ValueError, match='economic bundle validation failed'):
        service.restore_bundle(bundle_path=path, strict_validation=True, expected_scope=scope, expected_profile_name='standard')
    event_types = [row.event_type for row in forensics_store.list_rows()]
    assert 'economic_bundle_validation_failed' in event_types
