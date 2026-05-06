from __future__ import annotations

class ReviewStateFeed:
    def fetch(self, business_id: str) -> dict[str, object]:
        return {'_source': 'review', 'reputation_score': 0.8, 'quality_score': 0.78} | {"business_id": str(business_id)}
