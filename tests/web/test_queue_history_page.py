from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.web.components.queue_alert_history_card import QueueAlertHistoryCard
from app.web.components.queue_rollup_timeline_card import QueueRollupTimelineCard
from app.web.pages.queue_history import QueueHistoryPage
from app.web.routes import Routes
from runtime.queue.queue_alerts import QueueAlert
from runtime.queue.queue_metrics_rollup_sqlite import QueueHealthWindowSummary


@dataclass(frozen=True)
class _Window:
    tenant_id: str = 'tenant-a'
    queue_name: str = 'primary'
    window_start: datetime = datetime(2026, 1, 1, 0, 0, 0)
    window_end: datetime = datetime(2026, 1, 1, 0, 5, 0)
    samples: int = 3
    latest_status: str = 'critical'
    latest_ok: bool = False
    max_pending_jobs: int = 20
    max_active_claims: int = 2
    max_dead_letter_jobs: int = 1
    total_alert_count: int = 4
    total_critical_alert_count: int = 2


def test_queue_rollup_timeline_card_builds_rows() -> None:
    payload = QueueRollupTimelineCard().build_from_window_summaries(tenant_id='tenant-a', queue_name='primary', windows=(_Window(),))
    assert payload['kind'] == 'queue_rollup_timeline_card'
    assert payload['payload']['critical_windows'] == 1
    assert payload['payload']['rows'][0]['max_pending_jobs'] == 20


def test_queue_alert_history_card_builds_rows() -> None:
    alert = QueueAlert(
        tenant_id='tenant-a',
        queue_name='primary',
        code='leadership_stale',
        severity='critical',
        message='Queue leadership appears stale',
        created_at=datetime(2026, 1, 1, 0, 0, 0),
    )
    payload = QueueAlertHistoryCard().build_from_alerts(tenant_id='tenant-a', queue_name='primary', alerts=(alert,))
    assert payload['kind'] == 'queue_alert_history_card'
    assert payload['payload']['critical_count'] == 1


def test_queue_history_page_builds_runtime_view() -> None:
    alert = QueueAlert(
        tenant_id='tenant-a',
        queue_name='primary',
        code='leadership_stale',
        severity='critical',
        message='Queue leadership appears stale',
        created_at=datetime(2026, 1, 1, 0, 0, 0),
    )
    page = QueueHistoryPage().build_runtime_view(tenant_id='tenant-a', queue_name='primary', windows=(_Window(),), alerts=(alert,))
    assert page['kind'] == 'queue_history_page'
    assert page['payload']['queue_timeline']['payload']['window_count'] == 1
    assert page['payload']['queue_alert_history']['payload']['alert_count'] == 1


def test_queue_history_route_is_present() -> None:
    payload = Routes().build_default(tenant_id='tenant-a')
    paths = {row['path'] for row in payload['payload']['routes']}
    assert '/web/queue-history' in paths
