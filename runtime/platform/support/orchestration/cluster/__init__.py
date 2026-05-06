from __future__ import annotations

"""Canonical orchestration cluster surface with compat alias submodules."""

class Autoscaling:
    def desired_workers(self, queue_size: int, max_workers: int) -> int:
        return min(max_workers, max(1, queue_size))

class CapacityPlanner:
    def plan(self, required_workers: int) -> dict[str, int]:
        return {"required_workers": required_workers}

class ClusterRuntime:
    def nodes(self) -> list[str]:
        return []

class CostScheduler:
    def schedule(self, jobs, max_cost: float):
        return list(jobs) if max_cost >= 0 else []

class GPUAllocator:
    def allocate(self, available: int, requested: int) -> int:
        return min(available, requested)

class MemoryGuard:
    def within_limit(self, used_mb: int, limit_mb: int) -> bool:
        return used_mb <= limit_mb

class NodeRegistry:
    def __init__(self) -> None:
        self._nodes: dict[str, dict] = {}

    def register(self, node_id: str, payload: dict) -> None:
        self._nodes[node_id] = dict(payload)

class PlacementPolicy:
    def place(self, nodes: list[str], workers: int) -> list[str]:
        return nodes[:workers]

class SpotRecovery:
    def recover(self, interrupted_nodes: list[str]) -> dict[str, list[str]]:
        return {"interrupted_nodes": list(interrupted_nodes)}

class WorkerRegistry:
    def __init__(self) -> None:
        self._workers: dict[str, dict] = {}

    def register(self, worker_id: str, payload: dict) -> None:
        self._workers[worker_id] = dict(payload)

_ALIAS_EXPORTS = {
    "autoscaling": "Autoscaling",
    "capacity_planner": "CapacityPlanner",
    "cluster_runtime": "ClusterRuntime",
    "cost_scheduler": "CostScheduler",
    "gpu_allocator": "GPUAllocator",
    "memory_guard": "MemoryGuard",
    "node_registry": "NodeRegistry",
    "placement_policy": "PlacementPolicy",
    "spot_recovery": "SpotRecovery",
    "worker_registry": "WorkerRegistry",
}

__all__ = [
    "Autoscaling",
    "CapacityPlanner",
    "ClusterRuntime",
    "CostScheduler",
    "GPUAllocator",
    "MemoryGuard",
    "NodeRegistry",
    "PlacementPolicy",
    "SpotRecovery",
    "WorkerRegistry",
] + list(_ALIAS_EXPORTS)
