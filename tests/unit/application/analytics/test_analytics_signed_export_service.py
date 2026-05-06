from __future__ import annotations

import json

from application.analytics.analytics_signed_export_service import AnalyticsSignedExportService
from observability.analytics_export_signature import AnalyticsExportSignatureService


def test_signed_export_writes_bundle_and_manifest(tmp_path):
    service = AnalyticsSignedExportService()
    result = service.export_signed_bundle(export_dir=str(tmp_path), export_id='exp-1', tenant_id='tenant-1', bundle={'dashboard': {'overall_state': 'healthy'}})
    bundle_payload = json.loads((tmp_path / 'exp-1.bundle.json').read_text(encoding='utf-8'))
    manifest_payload = json.loads((tmp_path / 'exp-1.manifest.json').read_text(encoding='utf-8'))
    secret = service.key_resolver.resolve_or_issue(tenant_id='tenant-1')[1]
    assert result['bundle_file'].endswith('exp-1.bundle.json')
    assert bundle_payload['dashboard']['overall_state'] == 'healthy'
    assert manifest_payload['tenant_id'] == 'tenant-1'
    assert AnalyticsExportSignatureService().verify_payload(payload=bundle_payload, secret=secret, signature_hex=manifest_payload['signature_hex']) is True
