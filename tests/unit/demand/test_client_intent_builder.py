from __future__ import annotations

from demand_capture.demand_capture_service import DemandCaptureService
from intent.client_intent_builder import ClientIntentBuilder


def test_client_intent_builder_extracts_core_signals() -> None:
    request = DemandCaptureService().capture({"text": "urgent premium near me отзывы", "channel": "website", "customer_id": "c1"})
    intent = ClientIntentBuilder().build(request)
    assert intent.urgency == "high"
    assert intent.location_hint == 'local'
    assert intent.is_high_value is True
    assert intent.needs_trust is True
