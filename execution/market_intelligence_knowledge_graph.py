from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping


CANON_MARKET_INTELLIGENCE_KNOWLEDGE_GRAPH = True


@dataclass(frozen=True)
class KnowledgeEdge:
    src_id: str
    dst_id: str
    relation: str
    weight: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            'src_id': self.src_id,
            'dst_id': self.dst_id,
            'relation': self.relation,
            'weight': max(0.0, float(self.weight)),
            'metadata': dict(self.metadata),
        }


class KnowledgeGraphLayer:
    def build_edges(self, rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...]) -> tuple[KnowledgeEdge, ...]:
        edges: list[KnowledgeEdge] = []
        for row in rows:
            product_id = str(row.get('product_id') or row.get('entity_id') or row.get('id') or '').strip()
            competitor_id = str(row.get('competitor_id') or row.get('seller_id') or '').strip()
            offer_id = str(row.get('offer_id') or row.get('campaign_id') or '').strip()
            complaint_id = str(row.get('complaint_id') or row.get('review_id') or '').strip()
            feature_id = str(row.get('feature_id') or row.get('feature_slug') or '').strip()
            creative_id = str(row.get('creative_id') or row.get('ad_id') or '').strip()
            if product_id and competitor_id:
                edges.append(KnowledgeEdge(src_id=product_id, dst_id=competitor_id, relation='competes_with'))
            if competitor_id and creative_id:
                edges.append(KnowledgeEdge(src_id=competitor_id, dst_id=creative_id, relation='uses_creative'))
            if creative_id and offer_id:
                edges.append(KnowledgeEdge(src_id=creative_id, dst_id=offer_id, relation='renders_offer'))
            if offer_id and complaint_id:
                edges.append(KnowledgeEdge(src_id=offer_id, dst_id=complaint_id, relation='triggered_complaint'))
            if complaint_id and feature_id:
                edges.append(KnowledgeEdge(src_id=complaint_id, dst_id=feature_id, relation='mentions_feature'))
        return tuple(edges)


__all__ = ['CANON_MARKET_INTELLIGENCE_KNOWLEDGE_GRAPH', 'KnowledgeEdge', 'KnowledgeGraphLayer']
