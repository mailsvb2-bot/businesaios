from __future__ import annotations

"""Canonical runtime wiring for market-intelligence operational support.

This module deliberately reuses the shared runtime reliability contour rather
than inventing a separate coordination stack. It must not introduce any
planning or decision logic.
"""

from dataclasses import dataclass
from typing import Any

from reliability.distributed_lock import DistributedLock
from reliability.leader_election import LeaderElection
from runtime.executor_runtime_support import RuntimeExecutorRecoverySupport, build_executor_recovery_support


CANON_MARKET_INTELLIGENCE_RUNTIME_SUPPORT = True


@dataclass(frozen=True)
class MarketIntelligenceRuntimeSupport:
    distributed_lock: DistributedLock | None = None
    scheduler_leader_election: LeaderElection | None = None
    recovery_support: RuntimeExecutorRecoverySupport | None = None


def build_market_intelligence_runtime_support(
    *,
    runtime_infra: Any | None = None,
    recovery_support: RuntimeExecutorRecoverySupport | None = None,
    outbox: Any | None = None,
    distributed_lock: DistributedLock | None = None,
) -> MarketIntelligenceRuntimeSupport:
    if distributed_lock is not None and recovery_support is None and runtime_infra is None and outbox is None:
        return MarketIntelligenceRuntimeSupport(
            distributed_lock=distributed_lock,
            scheduler_leader_election=None,
            recovery_support=None,
        )

    resolved_recovery = recovery_support
    if resolved_recovery is None and (runtime_infra is not None or outbox is not None):
        resolved_recovery = build_executor_recovery_support(runtime_infra=runtime_infra, outbox=outbox)

    if resolved_recovery is not None:
        return MarketIntelligenceRuntimeSupport(
            distributed_lock=resolved_recovery.distributed_lock,
            scheduler_leader_election=resolved_recovery.scheduler_leader_election,
            recovery_support=resolved_recovery,
        )

    return MarketIntelligenceRuntimeSupport(
        distributed_lock=distributed_lock,
        scheduler_leader_election=None,
        recovery_support=None,
    )


__all__ = [
    'CANON_MARKET_INTELLIGENCE_RUNTIME_SUPPORT',
    'MarketIntelligenceRuntimeSupport',
    'build_market_intelligence_runtime_support',
]
