from tests.integration.demand._canonical_issuer import (
    build_demand_os_service,
)


def test_outcome_timestamp_is_monotonic_and_not_before_delivery() -> None:
    service = build_demand_os_service()

    result = service.process_raw_request(
        {
            "customer_id": "cust-1",
            "text": "need therapist",
            "channel": "telegram",
            "created_at_ms": 1000,
        }
    )
    request_id = result["request"].request_id
    seeded = service._outcomes.require(request_id)

    assert int(seeded["outcome_updated_at_ms"]) >= int(
        seeded["created_at_ms"]
    )

    service.record_outcome(
        request_id=request_id,
        converted=True,
        revenue=50.0,
    )
    updated = service._outcomes.require(request_id)

    assert int(updated["outcome_updated_at_ms"]) > int(
        seeded["outcome_updated_at_ms"]
    )
