from __future__ import annotations

class DemandDecisionInputBuilder:
    def build(self, *, request, intent, routing_preparation) -> dict[str, object]:
        return {
            "request_id": request.request_id,
            "customer_id": request.customer_id,
            "intent": intent,
            "routing_preparation": routing_preparation,
        }
