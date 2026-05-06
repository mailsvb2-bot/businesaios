from __future__ import annotations

from runtime.inference.distributed.node_health_scoring import DistributedInferenceNodeHealthScoring
from runtime.inference.distributed.node_registry import DistributedInferenceNode


CANON_RUNTIME_DISTRIBUTED_NODE_SELECTION_POLICY = True


class DistributedInferenceNodeSelectionPolicy:
    def __init__(self, scoring: DistributedInferenceNodeHealthScoring | None = None) -> None:
        self._scoring = scoring or DistributedInferenceNodeHealthScoring()

    def choose_node(self, nodes: tuple[DistributedInferenceNode, ...]) -> DistributedInferenceNode | None:
        if not nodes:
            return None
        return sorted(nodes, key=self._scoring.score, reverse=True)[0]


DistributedInferenceNodeSelectionPolicy.select = DistributedInferenceNodeSelectionPolicy.choose_node
