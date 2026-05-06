from __future__ import annotations

class ResponseTimeFeed:
    def fetch(self, business_id: str) -> dict[str, object]:
        return {'_source': 'response_time', 'response_speed_score': 0.7, 'no_response_rate': 0.05} | {"business_id": str(business_id)}
