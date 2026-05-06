from __future__ import annotations

from compliance.economic_forensics_service import EconomicForensicsService
from compliance.economic_forensics_store import InMemoryEconomicForensicsStore


def test_economic_forensics_service_exports_integrity_bundle() -> None:
    store = InMemoryEconomicForensicsStore()
    service = EconomicForensicsService(store=store)
    service.record_event(
        event_type='economic_bundle_exported',
        severity='info',
        artifact_id='a1',
        artifact_digest='d1',
        scope={'tenant_id': 'tenant-a', 'business_id': 'biz-a'},
        schema_version='2',
        payload={'status': 'ok'},
        tags=('economic', 'forensics'),
    )
    bundle = service.export_bundle(bundle_id='forensics-bundle')
    assert bundle.event_count == 1
    assert bundle.integrity_sha256
    assert bundle.events[0]['event_type'] == 'economic_bundle_exported'
