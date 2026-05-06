from __future__ import annotations

from dataclasses import dataclass

CANON_RUNTIME_SUPPORT_TRAINING_DISTRIBUTED_PACKAGE_OWNER = True
CANON_COMPAT_SHIM = True

class DDPRuntime:
    def wrap(self, model):
        return model

class DeepSpeedRuntime:
    def wrap(self, model):
        return model

@dataclass(frozen=True)
class DistributedState:
    world_size: int
    rank: int

class ElasticRecovery:
    def recover(self, active_ranks: list[int]) -> list[int]:
        return list(active_ranks)

class FSDPRuntime:
    def wrap(self, model):
        return model

class GradientSync:
    def sync(self, gradients) -> list:
        return list(gradients)

class NodeFailureRecovery:
    def recover(self, failed_nodes: list[str]) -> dict[str, list[str]]:
        return {"failed_nodes": list(failed_nodes)}

class ParameterSync:
    def sync(self, parameters) -> list:
        return list(parameters)

class RankTopology:
    def peers(self, world_size: int, rank: int) -> list[int]:
        return [idx for idx in range(world_size) if idx != rank]

class ShardedOptimizer:
    def step(self) -> None:
        return None

class TrainBarrier:
    def wait(self) -> None:
        return None

__all__ = [
    "DDPRuntime",
    "DeepSpeedRuntime",
    "DistributedState",
    "ElasticRecovery",
    "FSDPRuntime",
    "GradientSync",
    "NodeFailureRecovery",
    "ParameterSync",
    "RankTopology",
    "ShardedOptimizer",
    "TrainBarrier",
]
