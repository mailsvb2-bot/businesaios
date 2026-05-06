from __future__ import annotations
from contracts.demand import ClientRequest

class RequestEnricher:
    def enrich(self, request: ClientRequest, *, origin: str, geo: str, time_window: str, contact: str) -> ClientRequest:
        metadata = dict(request.metadata)
        metadata.update({"origin": origin, "geo": geo, "time_window": time_window, "contact": contact})
        return ClientRequest(
            request_id=request.request_id,
            text=request.text,
            channel=request.channel,
            created_at_ms=request.created_at_ms,
            customer_id=request.customer_id,
            session_id=request.session_id,
            location_hint=request.location_hint or geo,
            budget_hint=request.budget_hint,
            urgency_hint=request.urgency_hint or time_window,
            metadata=metadata,
        )
