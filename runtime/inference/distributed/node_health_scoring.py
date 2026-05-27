from __future__ import annotations

from runtime.inference.distributed.node_registry import DistributedInferenceNode

CANON_RUNTIME_DISTRIBUTED_NODE_HEALTH_SCORING = True


class DistributedInferenceNodeHealthScoring:
    """Deterministic node scoring for distributed inference."""

    def score(self, node: DistributedInferenceNode) -> float:
        if not node.healthy:
            return 0.0
        trust = max(0.0, min(1.0, float(node.trust_score)))
        capacity = max(0.0, min(1.0, float(node.capacity_score)))
        return round((trust * 0.65) + (capacity * 0.35), 6)
