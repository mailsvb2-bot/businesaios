from __future__ import annotations

from app.web.components.queue_remediation_hooks_card import QueueRemediationHooksCard
from app.web.pages.queue_ops import QueueOpsPage
from app.web.routes import Routes
from runtime.queue.queue_remediation_hooks import QueueRemediationHook


def test_queue_remediation_hooks_card_builds_operator_actions():
    card = QueueRemediationHooksCard()
    payload = card.build_from_hooks(
        tenant_id='tenant-a',
        queue_name='ops',
        hooks=(
            QueueRemediationHook(
                tenant_id='tenant-a',
                queue_name='ops',
                code='run_janitor_tick',
                label='Run janitor tick',
                description='Reclaim expired claims.',
                severity='critical',
            ),
        ),
    )
    assert payload['kind'] == 'queue_remediation_hooks_card'
    assert payload['payload']['hook_count'] == 1
    assert payload['payload']['critical_count'] == 1


def test_queue_ops_page_carries_remediation_hooks():
    page = QueueOpsPage()
    payload = page.build_runtime_view(
        tenant_id='tenant-a',
        reports=(),
        alerts=(),
        remediation_hooks=(
            QueueRemediationHook(
                tenant_id='tenant-a',
                queue_name='',
                code='refresh_health_sample',
                label='Refresh queue health',
                description='Take a fresh sample.',
                severity='warning',
            ),
        ),
    )
    assert payload['kind'] == 'queue_ops_page'
    assert payload['payload']['queue_remediation_hooks']['kind'] == 'queue_remediation_hooks_card'
    assert payload['payload']['queue_remediation_hooks']['payload']['hook_count'] == 1


def test_queue_routes_keep_queue_ops_surface():
    built = Routes().build_default(tenant_id='tenant-a')
    paths = {row['path'] for row in built['payload']['routes']}
    assert '/web/queue-ops' in paths
