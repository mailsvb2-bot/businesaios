from __future__ import annotations

from dataclasses import dataclass


CANON_RUNTIME_DISTRIBUTED_NODE_REGISTRY = True


@dataclass(frozen=True)
class DistributedInferenceNode:
    node_id: str
    region: str
    trust_score: float
    capacity_score: float
    healthy: bool = True


class DistributedInferenceNodeRegistry:
    def __init__(self) -> None:
        self._nodes: dict[str, DistributedInferenceNode] = {}

    def register(self, node: DistributedInferenceNode) -> None:
        self._nodes[node.node_id] = node

    def healthy_nodes(self) -> tuple[DistributedInferenceNode, ...]:
        return tuple(node for node in self._nodes.values() if node.healthy)
