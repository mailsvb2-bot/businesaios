from __future__ import annotations

from application.analytics.analytics_manifest_chain_store import SqliteAnalyticsManifestChainStore
from application.analytics.analytics_signed_export_chain_service import AnalyticsSignedExportChainService


def test_manifest_chain_links_previous_export(tmp_path):
    with SqliteAnalyticsManifestChainStore(str(tmp_path / 'manifest_chain.db')) as chain_store:
        service = AnalyticsSignedExportChainService(manifest_chain_store=chain_store)
        first = service.export_signed_bundle(export_dir=str(tmp_path), export_id='exp-1', tenant_id='tenant-1', bundle={'dashboard': {'overall_state': 'healthy'}})
        second = service.export_signed_bundle(export_dir=str(tmp_path), export_id='exp-2', tenant_id='tenant-1', bundle={'dashboard': {'overall_state': 'warning'}})
    assert first['manifest_chain_sha256']
    assert second['manifest_chain_sha256']
    assert second['previous_manifest_sha256'] is not None
