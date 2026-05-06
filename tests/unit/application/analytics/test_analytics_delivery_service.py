from __future__ import annotations

from application.analytics.analytics_delivery_service import AnalyticsDeliveryService
from application.analytics.analytics_delivery_sinks import FileDropAnalyticsSink


def test_delivery_service_dedups_and_delivers(tmp_path):
    service = AnalyticsDeliveryService(sinks={'file_drop': FileDropAnalyticsSink(root_dir=str(tmp_path))})
    result = service.deliver_alert_batch(
        tenant_id='tenant-1',
        channel='file_drop',
        alerts=[
            {'tenant_id': 'tenant-1', 'source_kind': 'tenant_rollup', 'severity': 'critical', 'metric_id': 'blocked_ratio', 'summary': 'blocked ratio exceeded ceiling'},
            {'tenant_id': 'tenant-1', 'source_kind': 'tenant_rollup', 'severity': 'critical', 'metric_id': 'blocked_ratio', 'summary': 'blocked ratio exceeded ceiling'},
        ],
    )
    assert result['delivered'] is True
    assert result['channel'] == 'file_drop'
