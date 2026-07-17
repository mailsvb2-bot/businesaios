from __future__ import annotations

import pytest

from tests.integration.demand._canonical_issuer import (
    build_demand_os_service,
)


def test_record_outcome_requires_existing_request() -> None:
    service = build_demand_os_service()

    with pytest.raises(KeyError):
        service.record_outcome(
            request_id="missing",
            converted=True,
            revenue=10.0,
        )
