from __future__ import annotations

from pathlib import Path

from execution.market_intelligence_compliance_boundary import MarketIntelligenceComplianceBoundary
from execution.market_intelligence_operator_control_plane import MarketIntelligenceOperatorControlPlane
from execution.market_intelligence_orchestration import MarketIntelligenceOrchestration, SyncSchedule
from execution.market_intelligence_scheduler_service import MarketIntelligenceSchedulerService
from execution.market_intelligence_models import MarketIntelligenceIngestionRequest
from execution.market_intelligence_loop import MarketIntelligenceLoop
from runtime.boot.market_intelligence_boot import build_market_intelligence_runtime


def test_operator_control_plane_persists_reviews(tmp_path: Path) -> None:
    store_path = tmp_path / 'mi_operator_store.json'
    plane = MarketIntelligenceOperatorControlPlane()
    plane.store._path = store_path
    plane.store._flush()
    review_id = plane.enqueue_review(
        tenant_id='tenant-a',
        provider='amazon',
        source_family='marketplace',
        external_id='sku-1',
        reason='low_quality_result',
        payload={'score': 0.2},
    )
    reloaded = MarketIntelligenceOperatorControlPlane(store=plane.store.__class__(store_path))
    open_reviews = reloaded.open_reviews(tenant_id='tenant-a')
    assert review_id == open_reviews[0]['review_id']
    assert open_reviews[0]['reason'] == 'low_quality_result'


def test_compliance_boundary_reads_persisted_policy(tmp_path: Path) -> None:
    store_path = tmp_path / 'mi_compliance_store.json'
    boundary = MarketIntelligenceComplianceBoundary()
    boundary.store._path = store_path
    boundary.store._flush()
    boundary = MarketIntelligenceComplianceBoundary(store=boundary.store.__class__(store_path))
    boundary.upsert_provider_policy(provider='amazon', allow_access=False, risk_level='restricted', retention_days=7)
    policy = boundary.policy_for('amazon')
    assert policy.allow_access is False
    assert policy.risk_level == 'restricted'
    assert policy.retention_days == 7


def test_scheduler_service_runs_due_schedule() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def execute_action(action_type: str, payload: dict[str, object]) -> dict[str, object]:
        calls.append((action_type, dict(payload)))
        return {
            'ok': True,
            'executed': True,
            'provider': payload['provider'],
            'source_family': payload['source_family'],
            'records': [{'external_id': '1', 'title': 'A', 'provider': payload['provider'], 'source_family': payload['source_family']}],
        }

    loop = MarketIntelligenceLoop(execute_action=execute_action)
    orchestration = MarketIntelligenceOrchestration(store=MarketIntelligenceOrchestration().store.__class__())
    scheduler = MarketIntelligenceSchedulerService(loop=loop, orchestration=orchestration)
    scheduler.register_schedule(
        name='amazon-marketplace',
        schedule=SyncSchedule(provider='amazon', source_family='marketplace', cadence_minutes=1, query='shoes'),
    )
    results = scheduler.run_due(tenant_id='tenant-a')
    assert len(results) == 1
    assert calls[0][0] == 'sync_marketplace_catalog'
    assert calls[0][1]['provider'] == 'amazon'
    assert results[0]['schedule_name'] == 'amazon-marketplace'


def test_boot_builder_exposes_loop_and_scheduler() -> None:
    runtime = build_market_intelligence_runtime(execute_action=lambda action_type, payload: {'ok': True, 'executed': True, 'records': []})
    assert runtime.loop is not None
    assert runtime.scheduler is not None
