from __future__ import annotations

from runtime.audit_log import RuntimeAuditLog
from runtime.boot.market_intelligence_boot import build_market_intelligence_runtime
from runtime.managed_runtime_plane import ManagedRuntimePlane
from runtime.market.market_trend_engine import MarketTrendEngine
from runtime.market.market_watch_service import MarketWatchService
from runtime.registry import RuntimeRegistry
from runtime.runtime_observability import RuntimeObservability
from runtime.service_names import RuntimeServiceName
from runtime.service_types import RuntimeServiceType


def _execute_action(action_type: str, payload: dict) -> dict:
    return {
        'ok': True,
        'executed': True,
        'action_type': action_type,
        'provider': payload.get('provider'),
        'source_family': payload.get('source_family'),
        'records': [{'external_id': '1', 'title': 'shoe', 'provider': payload.get('provider'), 'source_family': payload.get('source_family')}],
    }


def test_managed_runtime_plane_registers_market_intelligence_runtime_from_registry_plane() -> None:
    audit = RuntimeAuditLog()
    observability = RuntimeObservability(audit)
    service = MarketWatchService(trend_engine=MarketTrendEngine(), observability=observability)
    plane = ManagedRuntimePlane(observability=observability)
    registry = RuntimeRegistry()
    registry.begin_registration()
    registry.register(name=RuntimeServiceName.MARKET_WATCH, service=service, service_type=RuntimeServiceType.CORE, dependencies=())
    registry.register(name=RuntimeServiceName.MANAGED_RUNTIME_PLANE, service=plane, service_type=RuntimeServiceType.CORE, dependencies=())

    runtime = build_market_intelligence_runtime(
        execute_action=_execute_action,
        runtime_registry=registry,
        runtime_observability=observability,
    )

    assert plane.has_runtime(RuntimeServiceName.MARKET_INTELLIGENCE_RUNTIME) is True
    assert plane.runtime(RuntimeServiceName.MARKET_INTELLIGENCE_RUNTIME) is runtime
    names = audit.event_names()
    assert 'managed_runtime_registered' in names
    assert 'market_intelligence_runtime_attached_to_registry' in names


def test_managed_runtime_plane_can_drive_market_intelligence_runtime_lifecycle() -> None:
    audit = RuntimeAuditLog()
    observability = RuntimeObservability(audit)
    plane = ManagedRuntimePlane(observability=observability)
    _ = build_market_intelligence_runtime(
        execute_action=_execute_action,
        runtime_observability=observability,
        managed_runtime_plane=plane,
    )
    started = plane.start_all()
    assert RuntimeServiceName.MARKET_INTELLIGENCE_RUNTIME in started
    plane.request_stop_all(reason='plane_stop')
    reports = plane.join_all(timeout_seconds=1.0)
    assert RuntimeServiceName.MARKET_INTELLIGENCE_RUNTIME in reports
    names = audit.event_names()
    assert 'managed_runtime_started' in names
    assert 'managed_runtime_stop_requested' in names
    assert 'managed_runtime_joined' in names
