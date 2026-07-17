from __future__ import annotations

from tests.integration.demand._canonical_issuer import (
    build_demand_os_service,
)


def test_demand_os_routes_through_canonical_decision_core():
    service = build_demand_os_service()

    result = service.process_raw_request(
        {
            "text": "premium service amsterdam",
            "channel": "website",
            "customer_id": "c1",
        }
    )

    assert result["decision"].trace["decision_path"] == "core.decision"
    assert result["delivery"] is not None
