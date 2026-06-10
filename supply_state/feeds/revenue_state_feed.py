from __future__ import annotations


class RevenueStateFeed:
    def fetch(self, business_id: str) -> dict[str, object]:
        return {'_source': 'revenue', 'margin_score': 0.6, 'ltv_score': 0.7} | {"business_id": str(business_id)}
