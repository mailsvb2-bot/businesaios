from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.web.components.queue_remediation_audit_card import QueueRemediationAuditCard
from app.web.pages.queue_history import QueueHistoryPage


@dataclass(frozen=True)
class _Exec:
    hook_code: str = 'refresh_health_sample'
    executed: bool = True
    reason: str = 'health_sample_refreshed'
    category: str = 'verification'
    metadata: dict[str, object] = None  # type: ignore[assignment]
    executed_at: datetime = datetime(2026, 1, 1, 0, 0, 0)

    def __post_init__(self):
        if self.metadata is None:
            object.__setattr__(self, 'metadata', {'safe_action': True})


@dataclass(frozen=True)
class _Route:
    action: str = 'execute_remediation_hook'
    source: str = 'control_plane'
    actor_id: str = 'operator-1'
    request_id: str = 'req-1'
    status: str = 'executed'
    metadata: dict[str, object] = None  # type: ignore[assignment]
    recorded_at: datetime = datetime(2026, 1, 1, 0, 1, 0)

    def __post_init__(self):
        if self.metadata is None:
            object.__setattr__(self, 'metadata', {'hook_code': 'refresh_health_sample'})


def test_queue_remediation_audit_card_builds_rows() -> None:
    payload = QueueRemediationAuditCard().build_from_audit(
        tenant_id='tenant-a',
        queue_name='ops',
        executions=(_Exec(),),
        route_history=(_Route(),),
    )
    assert payload['kind'] == 'queue_remediation_audit_card'
    assert payload['payload']['row_count'] == 2
    assert payload['payload']['route_event_count'] == 1


def test_queue_history_page_includes_remediation_audit() -> None:
    page = QueueHistoryPage().build_runtime_view(
        tenant_id='tenant-a',
        queue_name='ops',
        windows=(),
        alerts=(),
        remediation_executions=(_Exec(),),
        remediation_route_history=(_Route(),),
    )
    assert page['payload']['queue_remediation_audit']['payload']['row_count'] == 2
