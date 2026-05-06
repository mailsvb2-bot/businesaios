from __future__ import annotations

from runtime.audit_log import RuntimeAuditLog
from runtime.boot.market_intelligence_boot import build_market_intelligence_runtime
from runtime.market.market_watch_service import MarketWatchService
from runtime.market.market_trend_engine import MarketTrendEngine
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


def _registry_with_market_watch() -> tuple[RuntimeRegistry, RuntimeObservability, MarketWatchService]:
    audit = RuntimeAuditLog()
    observability = RuntimeObservability(audit)
    service = MarketWatchService(trend_engine=MarketTrendEngine(), observability=observability)
    registry = RuntimeRegistry()
    registry.begin_registration()
    registry.register(
        name=RuntimeServiceName.MARKET_WATCH,
        service=service,
        service_type=RuntimeServiceType.CORE,
        dependencies=(),
    )
    return registry, observability, service


def test_market_intelligence_runtime_attaches_to_runtime_registry_market_watch() -> None:
    registry, observability, service = _registry_with_market_watch()
    runtime = build_market_intelligence_runtime(
        execute_action=_execute_action,
        runtime_registry=registry,
        runtime_observability=observability,
    )
    snap = runtime.snapshot()
    assert snap['attachment_report']['attached'] is True
    assert service.managed_runtime is runtime
    assert 'market_intelligence_runtime_attached_to_registry' in observability.audit_log.event_names()


def test_market_intelligence_supervisor_records_lifecycle_audit_events() -> None:
    registry, observability, _ = _registry_with_market_watch()
    runtime = build_market_intelligence_runtime(
        execute_action=_execute_action,
        runtime_registry=registry,
        runtime_observability=observability,
    )
    runtime.start()
    runtime.request_stop(reason='test_stop')
    report = runtime.join(timeout_seconds=1.0)
    names = observability.audit_log.event_names()
    assert 'market_intelligence_supervisor_started' in names
    assert 'market_intelligence_supervisor_stop_requested' in names
    assert 'market_intelligence_supervisor_joined' in names
    assert report.stop_reason == 'test_stop'
