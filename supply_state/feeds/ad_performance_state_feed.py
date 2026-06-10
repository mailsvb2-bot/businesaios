from __future__ import annotations


class AdPerformanceStateFeed:
    def fetch(self, business_id: str) -> dict[str, object]:
        return {'_source': 'ad_performance', 'service_fit': 0.65} | {"business_id": str(business_id)}
