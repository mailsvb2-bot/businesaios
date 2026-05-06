from __future__ import annotations

from entrypoints.api.analytics_models import AnalyticsSignedExportRequest
from entrypoints.api.analytics_signed_export_route_handlers import AnalyticsSignedExportRouteHandlers


class _EventStore:
    def __init__(self, events):
        self._events = list(events)

    def iter_events(self, *, tenant_id, start_ms, end_ms=None, event_type=None):
        for item in self._events:
            if str(item.get('tenant_id') or 'default') != str(tenant_id):
                continue
            yield dict(item)


def test_signed_export_route_handler_writes_bundle_and_manifest(tmp_path):
    handler = AnalyticsSignedExportRouteHandlers(
        event_store=_EventStore([
            {'tenant_id': 'tenant-1', 'event_type': 'offer_shown', 'user_id': 'u1', 'timestamp_ms': 1, 'payload': {}},
            {'tenant_id': 'tenant-1', 'event_type': 'offer_clicked', 'user_id': 'u1', 'timestamp_ms': 2, 'payload': {}},
            {'tenant_id': 'tenant-1', 'event_type': 'purchase_success', 'user_id': 'u1', 'timestamp_ms': 3, 'payload': {'amount': 20.0}},
        ]),
        manifest_chain_db_path=str(tmp_path / 'manifest_chain.sqlite3'),
        export_root=str(tmp_path / 'exports'),
    )
    result = handler.export_dashboard_bundle(
        AnalyticsSignedExportRequest(tenant_id='tenant-1', export_id='exp-1')
    )
    assert result['bundle_file'].endswith('exp-1.bundle.json')
    assert result['manifest_file'].endswith('exp-1.manifest.json')
    assert result['manifest_chain_sha256']
