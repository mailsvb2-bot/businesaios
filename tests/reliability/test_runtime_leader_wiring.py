from __future__ import annotations

from datetime import timedelta

from reliability.distributed_lock import InMemoryDistributedLock, utc_now
from runtime.execution.reliability_runtime import RuntimeReliability
from reliability.execution_checkpoint_store import InMemoryExecutionCheckpointStore
from reliability.idempotency_store import InMemoryIdempotencyStore
from reliability.recovery_orchestrator import RecoveryOrchestrator
from reliability.outbox_store import InMemoryOutboxStore
from reliability.leader_election import LeaderElection


def _runtime_reliability() -> RuntimeReliability:
    lock = InMemoryDistributedLock()
    checkpoints = InMemoryExecutionCheckpointStore()
    idempotency = InMemoryIdempotencyStore()
    recovery = RecoveryOrchestrator(checkpoint_store=checkpoints, idempotency_store=idempotency, outbox_store=InMemoryOutboxStore())
    return RuntimeReliability(checkpoint_store=checkpoints, idempotency_store=idempotency, recovery_orchestrator=recovery, distributed_lock=lock, scheduler_leader_election=LeaderElection(lock_backend=lock, election_name='runtime-scheduler', default_ttl_seconds=5), recovery_leader_election=LeaderElection(lock_backend=lock, election_name='runtime-recovery', default_ttl_seconds=5))


def test_runtime_reliability_campaign_or_heartbeat_scheduler_leader() -> None:
    runtime = _runtime_reliability()
    now = utc_now()
    leader1 = runtime.campaign_or_heartbeat_scheduler_leader(tenant_id='tenant-a', owner_id='node-1', ttl_seconds=5, now=now)
    assert leader1 is not None
    leader2 = runtime.campaign_or_heartbeat_scheduler_leader(tenant_id='tenant-a', owner_id='node-1', ttl_seconds=5, now=now + timedelta(seconds=3))
    assert leader2 is not None
    assert leader2.fencing_token.value == leader1.fencing_token.value
    assert leader2.expires_at > leader1.expires_at
