from __future__ import annotations

import json
from pathlib import Path

from application.analytics.analytics_signed_export_service import AnalyticsSignedExportService
from observability.analytics_export_signature import AnalyticsExportSignatureService


def test_signed_export_writes_bundle_and_manifest(tmp_path: Path) -> None:
    service = AnalyticsSignedExportService(export_root=tmp_path)
    result = service.export_signed_bundle(
        export_dir='signed',
        export_id='exp-1',
        tenant_id='tenant-1',
        bundle={'dashboard': {'overall_state': 'healthy'}},
    )
    bundle_file = Path(result['bundle_file'])
    manifest_file = Path(result['manifest_file'])
    assert bundle_file.is_relative_to(tmp_path.resolve())
    assert manifest_file.is_relative_to(tmp_path.resolve())
    bundle_payload = json.loads(bundle_file.read_text(encoding='utf-8'))
    manifest_payload = json.loads(manifest_file.read_text(encoding='utf-8'))
    secret = service.key_resolver.resolve_or_issue(tenant_id='tenant-1')[1]
    assert result['bundle_file'].endswith('exp-1.bundle.json')
    assert bundle_payload['dashboard']['overall_state'] == 'healthy'
    assert manifest_payload['tenant_id'] == 'tenant-1'
    assert AnalyticsExportSignatureService().verify_payload(
        payload=bundle_payload,
        secret=secret,
        signature_hex=manifest_payload['signature_hex'],
    ) is True
