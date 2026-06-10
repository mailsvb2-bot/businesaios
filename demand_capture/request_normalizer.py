from __future__ import annotations

from contracts.demand import ClientRequest


class RequestNormalizer:
    def normalize(self, request: ClientRequest) -> ClientRequest:
        cleaned = " ".join(request.text.split())
        return ClientRequest(
            request_id=request.request_id,
            text=cleaned.lower(),
            channel=request.channel.strip().lower(),
            created_at_ms=request.created_at_ms,
            customer_id=request.customer_id,
            session_id=request.session_id,
            location_hint=request.location_hint.strip().lower(),
            budget_hint=request.budget_hint.strip().lower(),
            urgency_hint=request.urgency_hint.strip().lower(),
            metadata=dict(request.metadata),
        )
