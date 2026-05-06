from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from core.math.advanced_models import (
    Bid,
    allocate_single_slot_vcg,
    max_flow_edmonds_karp,
    one_step_graph_score,
    solve_capacity_transport,
)

@dataclass(frozen=True)
class MatchMathSummary:
    graph_scores: dict[str, float]
    auction_price_by_business: dict[str, float]
    max_routable_flow: float
    transport_total_cost: float

class MathAwareMatchRouter:
    def score_graph(
        self,
        *,
        node_features: Mapping[str, Sequence[float]],
        adjacency: Mapping[str, Sequence[str]],
    ) -> dict[str, float]:
        if not node_features:
            return {}
        return one_step_graph_score(node_features=node_features, adjacency=adjacency)

    def auction_prices(self, candidates: Sequence[object]) -> dict[str, float]:
        if len(candidates) < 2:
            return {}
        ordered = sorted(
            [c for c in candidates if hasattr(c, "business_id") and hasattr(c, "score")],
            key=lambda item: float(getattr(item, "score", 0.0)),
            reverse=True,
        )
        out: dict[str, float] = {}
        for left, right in zip(ordered, ordered[1:]):
            outcome = allocate_single_slot_vcg([
                Bid(str(getattr(left, "business_id", "")), float(getattr(left, "score", 0.0))),
                Bid(str(getattr(right, "business_id", "")), float(getattr(right, "score", 0.0))),
            ])
            out[outcome.winner_id] = float(outcome.charged_price)
        return out

    def transport_summary(
        self,
        *,
        cost_matrix: Sequence[Sequence[float]],
        supply: Sequence[float],
        demand: Sequence[float],
    ) -> float:
        return float(solve_capacity_transport(cost_matrix, supply, demand).total_cost)

    def max_routable_flow(self, *, graph: dict[str, dict[str, float]], source: str, sink: str) -> float:
        flow, _ = max_flow_edmonds_karp(graph, source, sink)
        return float(flow)

    def summarize(
        self,
        *,
        candidates: Sequence[object],
        node_features: Mapping[str, Sequence[float]],
        adjacency: Mapping[str, Sequence[str]],
        capacity_graph: dict[str, dict[str, float]] | None = None,
    ) -> MatchMathSummary:
        graph_scores = self.score_graph(node_features=node_features, adjacency=adjacency)
        auction = self.auction_prices(candidates)
        max_flow = 0.0
        if capacity_graph:
            max_flow = self.max_routable_flow(graph=capacity_graph, source="source", sink="sink")
        return MatchMathSummary(
            graph_scores=graph_scores,
            auction_price_by_business=auction,
            max_routable_flow=max_flow,
            transport_total_cost=0.0,
        )
