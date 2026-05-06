from __future__ import annotations

from reliability.outbox_store import InMemoryOutboxStore
from runtime.boot.market_intelligence_boot import build_market_intelligence_runtime
from runtime.executor_runtime_support import build_executor_recovery_support
from runtime.market_intelligence_runtime_support import build_market_intelligence_runtime_support


def test_market_intelligence_runtime_support_reuses_executor_recovery_support() -> None:
    recovery = build_executor_recovery_support(runtime_infra=None, outbox=InMemoryOutboxStore())
    support = build_market_intelligence_runtime_support(recovery_support=recovery)
    assert support.distributed_lock is recovery.distributed_lock
    assert support.scheduler_leader_election is recovery.scheduler_leader_election
    assert support.recovery_support is recovery


def test_market_intelligence_boot_reuses_shared_runtime_scheduler_leader_election() -> None:
    recovery = build_executor_recovery_support(runtime_infra=None, outbox=InMemoryOutboxStore())
    runtime = build_market_intelligence_runtime(
        execute_action=lambda action_type, payload: {'ok': True, 'executed': True, 'records': []},
        recovery_support=recovery,
    )
    assert runtime.scheduler.distributed_lock is recovery.distributed_lock
    assert runtime.scheduler.scheduler_leader_election is recovery.scheduler_leader_election
    assert runtime.scheduler.coordination is not None
