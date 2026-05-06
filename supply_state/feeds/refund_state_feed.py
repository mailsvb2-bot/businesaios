from __future__ import annotations

class RefundStateFeed:
    def fetch(self, business_id: str) -> dict[str, object]:
        return {'_source': 'refund', 'refund_risk': 0.12} | {"business_id": str(business_id)}
