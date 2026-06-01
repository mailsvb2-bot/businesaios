from __future__ import annotations

from typing import Mapping, Sequence


def one_step_graph_score(
    node_features: Mapping[str, Sequence[float]],
    adjacency: Mapping[str, Sequence[str]],
    self_weight: float = 0.6,
    neighbor_weight: float = 0.4,
) -> dict[str, float]:
    if not node_features:
        raise ValueError("node_features must be non-empty")
    result: dict[str, float] = {}
    for node, feats in node_features.items():
        self_score = sum(float(x) for x in feats)
        neighbors = adjacency.get(node, [])
        neighbor_score = 0.0
        if neighbors:
            neighbor_score = sum(
                sum(float(x) for x in node_features.get(nb, (0.0,)))
                for nb in neighbors
            ) / len(neighbors)
        result[node] = self_weight * self_score + neighbor_weight * neighbor_score
    return result
