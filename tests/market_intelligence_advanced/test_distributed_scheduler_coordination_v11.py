from __future__ import annotations

from execution.market_intelligence_loop import MarketIntelligenceLoop
from execution.market_intelligence_orchestration import MarketIntelligenceOrchestration, SyncSchedule
from execution.market_intelligence_scheduler_coordination import MarketIntelligenceSchedulerCoordination
from execution.market_intelligence_scheduler_service import MarketIntelligenceSchedulerService
from reliability.distributed_lock import InMemoryDistributedLock
from runtime.boot.market_intelligence_boot import build_market_intelligence_runtime


def test_scheduler_coordination_elects_single_leader_per_tenant() -> None:
    lock = InMemoryDistributedLock()
    a = MarketIntelligenceSchedulerCoordination(owner_id='a', distributed_lock=lock)
    b = MarketIntelligenceSchedulerCoordination(owner_id='b', distributed_lock=lock)
    report_a = a.campaign_or_heartbeat(tenant_id='tenant-a')
    report_b = b.campaign_or_heartbeat(tenant_id='tenant-a')
    assert report_a.is_leader is True
    assert report_b.is_leader is False


def test_scheduler_service_uses_distributed_coordination_without_second_path() -> None:
    calls: list[str] = []

    def execute_action(action_type: str, payload: dict[str, object]) -> dict[str, object]:
        calls.append(action_type)
        return {'ok': True, 'executed': True, 'records': [{'external_id': '1', 'title': 'A', 'provider': payload['provider'], 'source_family': payload['source_family']}]}

    lock = InMemoryDistributedLock()
    orchestration = MarketIntelligenceOrchestration()
    orchestration.register('amazon-marketplace', SyncSchedule(provider='amazon', source_family='marketplace', cadence_minutes=1, query='shoes'))
    loop = MarketIntelligenceLoop(execute_action=execute_action)
    scheduler_a = MarketIntelligenceSchedulerService(loop=loop, orchestration=orchestration, distributed_lock=lock, owner_id='owner-a')
    scheduler_b = MarketIntelligenceSchedulerService(loop=loop, orchestration=orchestration, distributed_lock=lock, owner_id='owner-b')

    result_a = scheduler_a.run_due(tenant_id='tenant-a')
    result_b = scheduler_b.run_due(tenant_id='tenant-a')

    assert result_a[0]['executed'] is True
    assert result_b[0]['code'] in {'scheduler_not_leader', 'schedule_lease_held'}
    assert calls == ['sync_marketplace_catalog']


def test_boot_builder_accepts_distributed_lock_injection() -> None:
    runtime = build_market_intelligence_runtime(
        execute_action=lambda action_type, payload: {'ok': True, 'executed': True, 'records': []},
        distributed_lock=InMemoryDistributedLock(),
    )
    snap = runtime.snapshot()
    assert 'coordination' in snap['scheduler']
