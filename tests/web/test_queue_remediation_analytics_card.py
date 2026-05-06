from __future__ import annotations

from app.web.components.queue_remediation_analytics_card import QueueRemediationAnalyticsCard
from app.web.pages.queue_history import QueueHistoryPage


def test_queue_remediation_analytics_card_and_page():
    card = QueueRemediationAnalyticsCard().build(
        {
            'tenant_id': 'tenant-a',
            'queue_name': 'queue-a',
            'analytics': {'execution_count': 3, 'route_event_count': 5},
        }
    )
    assert card['kind'] == 'queue_remediation_analytics_card'
    assert card['payload']['has_activity'] is True

    page = QueueHistoryPage().build_runtime_view(
        tenant_id='tenant-a',
        queue_name='queue-a',
        windows=(),
        alerts=(),
        remediation_analytics={'execution_count': 3, 'route_event_count': 5},
    )
    assert page['payload']['queue_remediation_analytics']['kind'] == 'queue_remediation_analytics_card'
