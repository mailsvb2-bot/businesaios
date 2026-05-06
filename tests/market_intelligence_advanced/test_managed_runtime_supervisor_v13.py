from __future__ import annotations

from execution.market_intelligence_orchestration import SyncSchedule
from runtime.audit_log import RuntimeAuditLog
from runtime.boot.market_intelligence_boot import build_market_intelligence_runtime
from runtime.market.market_trend_engine import MarketTrendEngine
from runtime.market.market_watch_service import MarketWatchService
from runtime.runtime_observability import RuntimeObservability


def _execute_action(action_type: str, payload: dict):
    return {
        'ok': True,
        'executed': True,
        'provider': payload.get('provider'),
        'source_family': payload.get('source_family'),
        'records': [{'external_id': 'x1', 'title': 'Demo title', 'provider': payload.get('provider'), 'source_family': payload.get('source_family'), 'observed_at': '2026-04-08T00:00:00+00:00'}],
        'summary': {'action_type': action_type},
    }


def test_managed_runtime_supervisor_pulses_without_second_brain_path() -> None:
    runtime = build_market_intelligence_runtime(
        execute_action=_execute_action,
        schedules={
            'amazon-marketplace': SyncSchedule(provider='amazon', source_family='marketplace', cadence_minutes=1, query='shoes')
        },
    )
    results = runtime.pulse_once()
    assert results
    assert results[0]['provider'] == 'amazon'
    snapshot = runtime.snapshot()
    assert 'supervisor' in snapshot


def test_market_watch_service_can_attach_and_drive_managed_runtime() -> None:
    runtime = build_market_intelligence_runtime(
        execute_action=_execute_action,
        schedules={
            'amazon-marketplace': SyncSchedule(provider='amazon', source_family='marketplace', cadence_minutes=1, query='shoes')
        },
    )
    service = MarketWatchService(
        trend_engine=MarketTrendEngine(),
        observability=RuntimeObservability(audit_log=RuntimeAuditLog()),
    )
    service.attach_market_intelligence_runtime(runtime)
    pulse_results = service.pulse_managed_runtime_once()
    assert pulse_results
    snap = service.managed_runtime_snapshot()
    assert snap['attached'] is True
