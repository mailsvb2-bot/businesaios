from __future__ import annotations

class LeadPipelineStateFeed:
    def fetch(self, business_id: str) -> dict[str, object]:
        return {'_source': 'lead_pipeline', 'conversion_score': 0.55} | {"business_id": str(business_id)}
