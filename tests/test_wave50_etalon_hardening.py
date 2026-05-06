from __future__ import annotations

import pytest

from kernel.decisioning.route_contract import CANONICAL_ROUTE, DecisionRoute, DecisionRouteViolation, canonical_runtime_route
from interfaces.ads._write_stage import raise_write_stage_disabled
from interfaces.messaging._shared.delivery_mapper import map_delivery_result
from interfaces.messaging._shared.outbound_sender import send_outbound
from interfaces.messaging._shared.provider_config import ProviderConfig
from runtime.messaging.outbound_message import OutboundMessage


def _msg() -> OutboundMessage:
    return OutboundMessage(decision_id="d1", correlation_id="c1", tenant_id="t1", user_id="u1", channel="email", text="hello", payload={"recipient": "x@example.com", "delivery_key": "k1"})


def test_canonical_runtime_route_builder() -> None:
    assert canonical_runtime_route() == CANONICAL_ROUTE
    assert canonical_runtime_route("DecisionCore", "RuntimeExecutor", "AdsApplyHandler") == "DecisionCore->RuntimeExecutor->AdsApplyHandler"


def test_route_validation_rejects_noncanonical_prefix() -> None:
    route = DecisionRoute(decision_id="d1", correlation_id="c1", issuer_id="businesaios-core", action="a1", route="OtherBrain->RuntimeExecutor")
    with pytest.raises(DecisionRouteViolation):
        route.validate()


def test_configured_noop_is_not_reported_as_delivered() -> None:
    raw = send_outbound(cfg=ProviderConfig(provider="email", env_prefix="EMAIL", mode="configured_noop", endpoint="", sender="", token_present=False), msg=_msg())
    result = map_delivery_result(msg=_msg(), raw=raw)
    assert raw["noop"] is True
    assert raw["delivered"] is False
    assert result.ok is False
    assert result.detail["execution_state"] == "not_sent"


def test_write_stage_disabled_message_is_honest() -> None:
    with pytest.raises(Exception) as excinfo:
        raise_write_stage_disabled(connector_name="GoogleAdsConnector", provider="google_ads", operation="create_or_update:campaign", payload={"name": "Test"})
    text = str(excinfo.value)
    assert "read_only" in text
    assert "payload_keys=['name']" in text
    assert "wire explicit provider-specific writer" in text
