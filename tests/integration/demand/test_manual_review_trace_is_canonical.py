from __future__ import annotations

from contracts.supply import BusinessSupplyProfile
from supply_directory.business_directory import BusinessDirectory
from tests.integration.demand._canonical_issuer import (
    build_demand_os_service,
)


def test_manual_review_trace_is_canonical_when_all_supply_blocked() -> None:
    directory = BusinessDirectory()
    directory.add_profile(
        BusinessSupplyProfile(
            business_id="biz-blocked",
            name="Blocked",
            service_categories=("general",),
            service_area_codes=("amsterdam",),
            price_band="mid",
            notification_channels=("email",),
            tags=(),
            active=False,
        )
    )
    service = build_demand_os_service(
        directory=directory,
        seed_defaults=False,
    )

    result = service.process_raw_request(
        {
            "text": "service amsterdam",
            "channel": "website",
            "customer_id": "c1",
        }
    )

    assert result["decision"].requires_manual_review is True
    assert result["decision"].trace["decision_path"] == "core.decision"
