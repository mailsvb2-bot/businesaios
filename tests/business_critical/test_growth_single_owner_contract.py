from __future__ import annotations

import inspect
from typing import get_args

import pytest

from core.actions.names import (
    ACTION_GROWTH_PROPOSAL_APPLY_V1,
    ACTION_GROWTH_PROPOSE_V1,
)
from core.growth.proposal_service import GrowthProposalService
from core.growth.strategy.contracts import (
    GROWTH_MESSAGING_CHANNELS,
    Channel,
    GrowthGoalV1,
    GrowthSignalV1,
)
from core.growth.strategy.llm_generator import _build_request
from core.growth.strategy.service import _fallback_hypotheses
from runtime.boot.actions_registry import all_actions
from runtime.actions import (
    ACTION_GROWTH_PROPOSAL_APPLY_V1 as RUNTIME_LEGACY_GROWTH_ALIAS,
)
from runtime.messaging.channel_types import ALL_CHANNELS


class FakeGateway:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def propose(self, **kwargs) -> None:
        self.requests.append(dict(kwargs))


@pytest.mark.lock
def test_legacy_growth_surface_only_forwards_to_canonical_owner() -> None:
    service = GrowthProposalService()
    low = service.build_proposals(
        tenant_id="business-a",
        user_id="owner-1",
        objective="grow qualified revenue",
        signals={"conversion_rate": 0.001, "roas": 9.0},
    )
    high = service.build_proposals(
        tenant_id="business-a",
        user_id="owner-1",
        objective="grow qualified revenue",
        signals={"conversion_rate": 0.9, "roas": 0.1},
    )

    assert len(low) == len(high) == 1
    assert low[0]["signals"] == {"conversion_rate": 0.001, "roas": 9.0}
    assert high[0]["signals"] == {"conversion_rate": 0.9, "roas": 0.1}

    gateway = FakeGateway()
    queued = service.queue(
        gateway=gateway,
        tenant_id="business-a",
        decision_id="legacy-decision",
        correlation_id="legacy-correlation",
        issuer_id="legacy-issuer",
        proposals=low,
    )

    assert queued == 1
    request = gateway.requests[-1]
    assert request["tenant_id"] == "business-a"
    assert request["action"] == ACTION_GROWTH_PROPOSE_V1
    assert request["action"] != ACTION_GROWTH_PROPOSAL_APPLY_V1
    assert request["payload"] == {
        "tenant_id": "business-a",
        "user_id": "owner-1",
        "objective": "grow qualified revenue",
        "signals": {"conversion_rate": 0.001, "roas": 9.0},
    }
    assert "decision_id" not in request["payload"]
    assert "correlation_id" not in request["payload"]
    assert ACTION_GROWTH_PROPOSE_V1 in all_actions()
    assert ACTION_GROWTH_PROPOSAL_APPLY_V1 not in all_actions()
    assert RUNTIME_LEGACY_GROWTH_ALIAS == ACTION_GROWTH_PROPOSE_V1


@pytest.mark.lock
def test_legacy_growth_forwarder_contains_no_threshold_decision_logic() -> None:
    source = inspect.getsource(GrowthProposalService)

    assert "conversion_rate" not in source
    assert "roas" not in source
    assert "ACTION_GROWTH_PROPOSAL_APPLY_V1" not in source


@pytest.mark.lock
def test_growth_channel_contract_covers_every_runtime_messenger() -> None:
    strategic_channels = set(get_args(Channel))

    assert set(ALL_CHANNELS).issubset(strategic_channels)
    assert set(ALL_CHANNELS).issubset(set(GROWTH_MESSAGING_CHANNELS))

    request = _build_request(
        tenant_id="business-a",
        goal=GrowthGoalV1(),
        signals=GrowthSignalV1(
            tenant_id="business-a",
            top_channels=("whatsapp", "instagram"),
        ),
        n=4,
        model="",
    )
    prompt = str(request.messages[0].content)
    assert "supported messaging channels" in prompt
    assert "Telegram is supported but not assumed" in prompt
    for channel in ALL_CHANNELS:
        assert channel in prompt


@pytest.mark.lock
def test_growth_fallback_uses_observed_messenger_and_preserves_telegram_default() -> None:
    observed = _fallback_hypotheses(
        tenant_id="business-a",
        decision_id="decision-observed",
        signals=GrowthSignalV1(
            tenant_id="business-a",
            top_channels=("whatsapp", "telegram"),
        ),
        goal=GrowthGoalV1(),
    )
    defaulted = _fallback_hypotheses(
        tenant_id="business-a",
        decision_id="decision-default",
        signals=GrowthSignalV1(tenant_id="business-a"),
        goal=GrowthGoalV1(),
    )

    assert observed[0].channel == "whatsapp"
    assert observed[1].channel == "whatsapp"
    assert observed[-1].channel == "whatsapp"
    assert observed[0].action_hints["type"] == "messaging_flow"
    assert observed[1].action_hints["type"] == "messaging_followup"

    assert defaulted[0].channel == "telegram"
    assert defaulted[1].channel == "telegram"
    assert defaulted[-1].channel == "telegram"
    assert defaulted[0].action_hints["type"] == "telegram_flow"
    assert defaulted[1].action_hints["type"] == "telegram_followup"
