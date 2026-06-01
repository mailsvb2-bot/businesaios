from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from runtime.business_autonomy.distributed_state import FileRegionRouteState
from runtime.execution.distributed_execution_plane import (
    DistributedExecutionPlanner,
    GlobalGovernorVerdict,
    HashRingShardMap,
    QueueSlice,
    ReplayRecoveryPort,
)
from runtime.execution.region_ownership_plane import RegionOwnershipPlane, RegionRoute


@dataclass(frozen=True)
class StaticReplayRecovery:
    def classify(self, *, queue_name: str, tenant_id: str, shard_id: int) -> str:
        if "critical" in str(queue_name):
            return "replay_then_resume"
        return "resume_only"


@dataclass(frozen=True)
class FleetPressureGovernor:
    base_limit: int = 32
    hot_partition_penalty: int = 8
    global_depth_limit: int = 10000

    def evaluate(self, *, queue_name: str, slices: Sequence[QueueSlice], desired_claims: int) -> GlobalGovernorVerdict:
        total_depth = sum(max(0, int(item.depth)) for item in slices)
        hot = any(bool(item.hot_partition) for item in slices)
        if total_depth >= self.global_depth_limit:
            return GlobalGovernorVerdict(False, 0, 5, "global_backpressure")
        allocated = max(1, min(int(desired_claims), self.base_limit - (self.hot_partition_penalty if hot else 0)))
        delay = 2 if hot else 0
        return GlobalGovernorVerdict(True, allocated, delay, "hot_partition" if hot else "steady")


@dataclass(frozen=True)
class BusinessAutonomyExecutionRuntime:
    planner: DistributedExecutionPlanner
    region_plane: RegionOwnershipPlane


def build_execution_runtime(*, route_state: FileRegionRouteState) -> BusinessAutonomyExecutionRuntime:
    planner = DistributedExecutionPlanner(
        shard_map=HashRingShardMap(regions=("eu-west-1", "us-east-1"), shards_per_region=64, owner_prefix="business-autonomy"),
        governor=FleetPressureGovernor(),
        replay_recovery=StaticReplayRecovery(),
    )
    region_plane = RegionOwnershipPlane(state=route_state)
    return BusinessAutonomyExecutionRuntime(planner=planner, region_plane=region_plane)


def ensure_business_route(*, route_state: FileRegionRouteState, tenant_id: str, business_id: str, primary_region: str, failover_region: str) -> RegionRoute:
    existing = route_state.read_route(tenant_id=tenant_id, business_id=business_id)
    if existing is not None:
        return existing
    route = RegionRoute(
        tenant_id=tenant_id,
        business_id=business_id,
        primary_region=primary_region,
        failover_region=failover_region,
        routing_epoch=0,
        ownership_token=1,
    )
    route_state.compare_and_swap_route(tenant_id=tenant_id, business_id=business_id, expected_epoch=None, route=route)
    return route_state.read_route(tenant_id=tenant_id, business_id=business_id) or route


__all__ = [
    "BusinessAutonomyExecutionRuntime",
    "FleetPressureGovernor",
    "StaticReplayRecovery",
    "build_execution_runtime",
    "ensure_business_route",
]
