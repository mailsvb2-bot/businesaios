from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from execution.market_intelligence_loop import MarketIntelligenceLoop
from execution.market_intelligence_models import MarketIntelligenceIngestionRequest
from execution.market_intelligence_orchestration import MarketIntelligenceOrchestration, SyncSchedule
from execution.market_intelligence_provider_matrix import ACTION_TO_FAMILY
from execution.market_intelligence_schedule_lease import PersistentMarketIntelligenceScheduleLeaseStore
from execution.market_intelligence_scheduler_coordination import MarketIntelligenceSchedulerCoordination
from reliability.distributed_lock import DistributedLock
from reliability.leader_election import LeaderElection


CANON_MARKET_INTELLIGENCE_SCHEDULER_SERVICE = True


_DEFAULT_ACTION_BY_FAMILY = {family: action for action, family in ACTION_TO_FAMILY.items()}


@dataclass
class MarketIntelligenceSchedulerService:
    loop: MarketIntelligenceLoop
    orchestration: MarketIntelligenceOrchestration = field(default_factory=MarketIntelligenceOrchestration)
    lease_store: PersistentMarketIntelligenceScheduleLeaseStore = field(default_factory=PersistentMarketIntelligenceScheduleLeaseStore)
    lease_ttl_seconds: int = 300
    owner_id: str = field(default_factory=PersistentMarketIntelligenceScheduleLeaseStore().allocate_owner_id)
    distributed_lock: DistributedLock | None = None
    scheduler_leader_election: LeaderElection | None = None
    coordination: MarketIntelligenceSchedulerCoordination | None = None

    def __post_init__(self) -> None:
        if self.coordination is None and self.distributed_lock is not None:
            self.coordination = MarketIntelligenceSchedulerCoordination(
                owner_id=self.owner_id,
                distributed_lock=self.distributed_lock,
                scheduler_leader_election=self.scheduler_leader_election,
                schedule_ttl_seconds=int(self.lease_ttl_seconds),
            )

    def register_schedule(self, *, name: str, schedule: SyncSchedule) -> None:
        self.orchestration.register(name, schedule)

    def run_due(self, *, tenant_id: str = 'default', active_campaign_tags: tuple[str, ...] = ()) -> tuple[dict[str, Any], ...]:
        results: list[dict[str, Any]] = []
        leadership = self.coordination.campaign_or_heartbeat(tenant_id=tenant_id) if self.coordination is not None else None
        if leadership is not None and not leadership.is_leader:
            return ({
                'ok': True,
                'executed': False,
                'code': 'scheduler_not_leader',
                'tenant_id': tenant_id,
                'owner_id': self.owner_id,
            },)
        for run in self.orchestration.due_runs(active_campaign_tags=active_campaign_tags):
            lease_key = f"{tenant_id}:{run['name']}"
            distributed_lease = self.coordination.acquire_schedule_lease(tenant_id=tenant_id, schedule_name=str(run['name'])) if self.coordination is not None else None
            acquired = distributed_lease is not None
            if not acquired:
                acquired = self.lease_store.try_acquire(lease_key=lease_key, owner_id=self.owner_id, ttl_seconds=int(self.lease_ttl_seconds))
            if not acquired:
                results.append({
                    'ok': True,
                    'executed': False,
                    'code': 'schedule_lease_held',
                    'schedule_name': run['name'],
                    'tenant_id': tenant_id,
                })
                continue
            try:
                request = MarketIntelligenceIngestionRequest(
                    tenant_id=tenant_id,
                    source_family=str(run['source_family']),
                    provider=str(run['provider']),
                    action_type=_DEFAULT_ACTION_BY_FAMILY[str(run['source_family'])],
                    query=run.get('query'),
                    subject_url=run.get('subject_url'),
                    region=run.get('region'),
                    locale=run.get('locale'),
                    limit=int(run.get('limit') or 25),
                    metadata=dict(run.get('metadata') or {}),
                )
                result = self.loop.run(request)
                result = dict(result)
                result['schedule_name'] = run['name']
                result['scheduler_leadership'] = {
                    'is_leader': (leadership.is_leader if leadership is not None else True),
                    'fencing_token': (leadership.fencing_token if leadership is not None else None),
                }
                results.append(result)
                self.orchestration.mark_run(str(run['name']))
            finally:
                if self.coordination is not None:
                    self.coordination.release_schedule_lease(lease=distributed_lease)
                self.lease_store.release(lease_key=lease_key, owner_id=self.owner_id)
        return tuple(results)

    def snapshot(self) -> dict[str, Any]:
        return {
            'orchestration': self.orchestration.snapshot() if hasattr(self.orchestration, 'snapshot') else {},
            'lease_store': self.lease_store.snapshot(),
            'coordination': self.coordination.snapshot(tenant_id='tenant-default').__dict__ if self.coordination is not None else {},
            'owner_id': self.owner_id,
        }
