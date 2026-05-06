from __future__ import annotations

from core.product.types import FeatureScore, RoadmapProposal


class RoadmapPriorityExplainer:
    def explain(self, proposal: RoadmapProposal, scores: list[FeatureScore]) -> list[str]:
        scores_by_feature = {score.feature_id: score for score in scores}
        lines: list[str] = []
        for item in proposal.items:
            score = scores_by_feature.get(item.feature_id)
            if score is None:
                continue
            lines.append(
                f"{item.feature_id}: bucket={item.bucket.value}, rank={item.priority_rank}, total={score.total_score:.4f}, value={score.value_score:.4f}, retention={score.retention_score:.4f}, complexity={score.complexity_score:.4f}, risk={score.risk_score:.4f}"
            )
        return lines
