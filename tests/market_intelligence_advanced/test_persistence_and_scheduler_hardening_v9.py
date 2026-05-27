from __future__ import annotations

from pathlib import Path

from execution.market_intelligence_compliance_boundary import MarketIntelligenceComplianceBoundary
from execution.market_intelligence_loop import MarketIntelligenceLoop
from execution.market_intelligence_models import MarketIntelligenceIngestionRequest
from execution.market_intelligence_observability_store import PersistentMarketIntelligenceObservabilityStore
from execution.market_intelligence_operator_control_plane import MarketIntelligenceOperatorControlPlane
from execution.market_intelligence_orchestration import MarketIntelligenceOrchestration, SyncSchedule
from execution.market_intelligence_schedule_lease import PersistentMarketIntelligenceScheduleLeaseStore
from execution.market_intelligence_scheduler_service import MarketIntelligenceSchedulerService
from runtime.boot.market_intelligence_boot import build_market_intelligence_runtime


def test_compliance_store_tracks_policy_audit(tmp_path: Path) -> None:
    store_path = tmp_path / 'compliance.json'
    boundary = MarketIntelligenceComplianceBoundary()
    boundary.store._path = store_path
    boundary.store._flush()
    boundary = MarketIntelligenceComplianceBoundary(store=boundary.store.__class__(store_path))
    boundary.upsert_provider_policy(provider='amazon', allow_access=True, risk_level='standard')
    boundary.upsert_provider_policy(provider='amazon', allow_access=False, risk_level='restricted')
    snap = boundary.store.snapshot()
    assert snap['policy_version'] == 2
    assert len(snap['policy_audit']) == 2
    assert snap['policy_audit'][-1]['current']['allow_access'] is False


def test_scheduler_lease_prevents_duplicate_run(tmp_path: Path) -> None:
    calls: list[str] = []

    def execute_action(action_type: str, payload: dict[str, object]) -> dict[str, object]:
        calls.append(action_type)
        return {'ok': True, 'executed': True, 'records': [{'external_id': '1', 'title': 'A', 'provider': payload['provider'], 'source_family': payload['source_family']}]}

    lease_store = PersistentMarketIntelligenceScheduleLeaseStore(tmp_path / 'lease.json')
    orchestration = MarketIntelligenceOrchestration(store=MarketIntelligenceOrchestration().store.__class__(tmp_path / 'schedule.json'))
    orchestration.register('amazon-marketplace', SyncSchedule(provider='amazon', source_family='marketplace', cadence_minutes=1, query='shoes'))
    loop = MarketIntelligenceLoop(execute_action=execute_action)
    scheduler_a = MarketIntelligenceSchedulerService(loop=loop, orchestration=orchestration, lease_store=lease_store, owner_id='owner-a')
    scheduler_b = MarketIntelligenceSchedulerService(loop=loop, orchestration=orchestration, lease_store=lease_store, owner_id='owner-b')
    assert lease_store.try_acquire(lease_key='tenant-a:amazon-marketplace', owner_id='owner-a', ttl_seconds=300) is True
    results = scheduler_b.run_due(tenant_id='tenant-a')
    assert results[0]['code'] == 'schedule_lease_held'
    assert calls == []


def test_loop_persists_anomalies_and_runs(tmp_path: Path) -> None:
    obs_store = PersistentMarketIntelligenceObservabilityStore(tmp_path / 'observability.json')

    def execute_action(action_type: str, payload: dict[str, object]) -> dict[str, object]:
        return {'ok': True, 'executed': True, 'records': []}

    loop = MarketIntelligenceLoop(execute_action=execute_action, observability_store=obs_store)
    result = loop.run(MarketIntelligenceIngestionRequest(tenant_id='tenant-a', source_family='marketplace', provider='amazon', action_type='sync_marketplace_catalog', query='x'))
    assert result['observability_snapshot']['anomalies']
    snap = obs_store.snapshot()
    assert snap['runs'][-1]['status'] == 'succeeded'
    assert snap['anomalies'][-1]['reason'] == 'empty_result'


def test_runtime_snapshot_exposes_persistent_surfaces(tmp_path: Path) -> None:
    runtime = build_market_intelligence_runtime(execute_action=lambda action_type, payload: {'ok': True, 'executed': True, 'records': []})
    snap = runtime.snapshot()
    assert 'scheduler' in snap
    assert 'operator' in snap
    assert 'compliance' in snap
    assert 'observability' in snap
