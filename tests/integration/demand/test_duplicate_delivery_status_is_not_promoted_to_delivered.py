from __future__ import annotations

from contracts.matching.delivery_outcome import DeliveryOutcome
from lead_outcomes import LeadOutcomeRegistry
from tests.integration.demand._canonical_issuer import (
    build_demand_os_service,
)


class DuplicateDispatcher:
    def dispatch(self, *, request, decision):
        return DeliveryOutcome(
            request_id=request.request_id,
            business_id=decision.selected_business_id or "biz-1",
            delivery_status="duplicate",
            channel="crm",
            detail="duplicate",
            delivered_at_ms=None,
        )


def test_duplicate_delivery_status_is_preserved() -> None:
    registry = LeadOutcomeRegistry()
    service = build_demand_os_service(
        dispatcher=DuplicateDispatcher(),
        registry=registry,
    )

    result = service.process_raw_request(
        {
            "request_id": "r-dup",
            "text": "premium service amsterdam",
            "channel": "website",
            "customer_id": "c1",
        }
    )

    assert result["delivery"] is not None
    assert result["delivery"].delivery_status == "duplicate"
    assert registry.require("r-dup")["status"] == "duplicate"
