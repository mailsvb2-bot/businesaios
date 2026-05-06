from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Mapping, Protocol, Sequence
import json


CANON_DISTRIBUTED_EXECUTION_PLANE = True


@dataclass(frozen=True)
class QueueSlice:
    shard_id: int
    depth: int
    oldest_age_seconds: int
    hot_partition: bool = False


@dataclass(frozen=True)
class ShardAssignment:
    shard_id: int
    region: str
    owner_id: str
    routing_epoch: int


@dataclass(frozen=True)
class GlobalGovernorVerdict:
    allowed: bool
    allocated_limit: int
    backpressure_delay_seconds: int
    reason: str


@dataclass(frozen=True)
class LeaseFence:
    resource_key: str
    owner_id: str
    fencing_token: int


@dataclass(frozen=True)
class DistributedExecutionPlan:
    queue_name: str
    shard: ShardAssignment
    tenant_id: str
    claim_limit: int
    backpressure_delay_seconds: int
    recovery_mode: str
    rebalance_required: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ShardMapPort(Protocol):
    def locate(self, *, queue_name: str, tenant_id: str, routing_key: str) -> ShardAssignment: ...


class GlobalGovernorPort(Protocol):
    def evaluate(self, *, queue_name: str, slices: Sequence[QueueSlice], desired_claims: int) -> GlobalGovernorVerdict: ...


class LeaseFencingPort(Protocol):
    def acquire(self, *, resource_key: str, owner_id: str, ttl_seconds: int) -> LeaseFence | None: ...
    def validate(self, *, resource_key: str, owner_id: str, fencing_token: int) -> bool: ...
    def release(self, *, resource_key: str, owner_id: str, fencing_token: int) -> None: ...


class ReplayRecoveryPort(Protocol):
    def classify(self, *, queue_name: str, tenant_id: str, shard_id: int) -> str: ...


class DistributedExecutionPlanner:
    def __init__(
        self,
        *,
        shard_map: ShardMapPort,
        governor: GlobalGovernorPort,
        replay_recovery: ReplayRecoveryPort,
    ) -> None:
        self._shard_map = shard_map
        self._governor = governor
        self._replay_recovery = replay_recovery

    def build_plan(
        self,
        *,
        queue_name: str,
        tenant_id: str,
        routing_key: str,
        slices: Sequence[QueueSlice],
        desired_claims: int,
    ) -> DistributedExecutionPlan:
        shard = self._shard_map.locate(queue_name=queue_name, tenant_id=tenant_id, routing_key=routing_key)
        verdict = self._governor.evaluate(queue_name=queue_name, slices=slices, desired_claims=desired_claims)
        claim_limit = 0 if not verdict.allowed else min(max(0, int(desired_claims)), max(0, int(verdict.allocated_limit)))
        rebalance_required = any(item.shard_id == shard.shard_id and item.hot_partition for item in slices)
        return DistributedExecutionPlan(
            queue_name=queue_name,
            shard=shard,
            tenant_id=str(tenant_id),
            claim_limit=claim_limit,
            backpressure_delay_seconds=max(0, int(verdict.backpressure_delay_seconds)),
            recovery_mode=self._replay_recovery.classify(queue_name=queue_name, tenant_id=tenant_id, shard_id=shard.shard_id),
            rebalance_required=rebalance_required,
            metadata={"governor_reason": verdict.reason},
        )


class HashRingShardMap:
    def __init__(self, *, regions: Sequence[str], shards_per_region: int = 128, owner_prefix: str = "worker") -> None:
        if not regions:
            raise ValueError("regions are required")
        self._regions = tuple(str(item).strip() for item in regions if str(item).strip())
        if not self._regions:
            raise ValueError("regions are required")
        self._shards_per_region = max(1, int(shards_per_region))
        self._owner_prefix = str(owner_prefix).strip() or "worker"

    def locate(self, *, queue_name: str, tenant_id: str, routing_key: str) -> ShardAssignment:
        material = json.dumps(
            {"queue": queue_name, "tenant": tenant_id, "routing_key": routing_key},
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = sha256(material.encode("utf-8")).hexdigest()
        index = int(digest[:16], 16)
        region_index = index % len(self._regions)
        region = self._regions[region_index]
        local_shard = (index // len(self._regions)) % self._shards_per_region
        shard_id = region_index * self._shards_per_region + local_shard
        routing_epoch = int(digest[16:24], 16)
        return ShardAssignment(
            shard_id=shard_id,
            region=region,
            owner_id=f"{self._owner_prefix}:{region}:{shard_id}",
            routing_epoch=routing_epoch,
        )


__all__ = [
    "CANON_DISTRIBUTED_EXECUTION_PLANE",
    "DistributedExecutionPlan",
    "DistributedExecutionPlanner",
    "GlobalGovernorPort",
    "GlobalGovernorVerdict",
    "HashRingShardMap",
    "LeaseFence",
    "LeaseFencingPort",
    "QueueSlice",
    "ReplayRecoveryPort",
    "ShardAssignment",
    "ShardMapPort",
]
