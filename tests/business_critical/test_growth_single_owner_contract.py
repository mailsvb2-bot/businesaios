from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import get_args

import pytest

from contracts.world_model_semantics import WorldModelSemanticViewV1
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
from core.policies.telegram.handlers.growth_strategy import handle_growth_strategy
from core.ux.callbacks import (
    CB_GROWTH_ACCEPT_PREFIX,
    CB_GROWTH_BACKLOG,
    CB_GROWTH_GENERATE,
    CB_GROWTH_REJECT_PREFIX,
)
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
        business_id="business-a",
        decision_id="decision-observed",
        signals=GrowthSignalV1(
            tenant_id="business-a",
            top_channels=("whatsapp", "telegram"),
        ),
        goal=GrowthGoalV1(),
    )
    defaulted = _fallback_hypotheses(
        tenant_id="business-a",
        business_id="business-a",
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


@pytest.mark.lock
@pytest.mark.parametrize(
    ("callback_data", "expected_action"),
    (
        (CB_GROWTH_GENERATE, "growth_strategy_generate@v1"),
        (CB_GROWTH_BACKLOG, "growth_strategy_backlog@v1"),
        (f"{CB_GROWTH_ACCEPT_PREFIX}hyp-1", "growth_strategy_accept@v1"),
        (f"{CB_GROWTH_REJECT_PREFIX}hyp-1", "growth_strategy_reject@v1"),
    ),
)
def test_telegram_growth_actions_bind_explicit_world_model_business_scope(callback_data: str, expected_action: str) -> None:
    state = SimpleNamespace(
        tenant_id="tenant-a",
        meta={"correlation_key": "tg:chat-1:42"},
        world_model_semantics=WorldModelSemanticViewV1(
            state_id="state-1", tenant_id="tenant-a", business_id="business-a", generated_at_ms=1
        ),
    )
    ctx = SimpleNamespace(state=state, callback_data=callback_data, callback_query_id="cb-1")

    proposed = handle_growth_strategy(ctx, user_id="owner-1")

    assert proposed is not None
    assert proposed.action == expected_action
    assert proposed.payload["tenant_id"] == "tenant-a"
    assert proposed.payload["business_id"] == "business-a"
    if callback_data == CB_GROWTH_GENERATE:
        assert proposed.payload["idempotency_key"] == "tg:chat-1:42"


@pytest.mark.lock
@pytest.mark.parametrize("semantic_tenant", ("", "tenant-b"))
def test_telegram_growth_actions_fail_closed_without_matching_business_scope(semantic_tenant: str) -> None:
    semantics = (
        None
        if not semantic_tenant
        else WorldModelSemanticViewV1(
            state_id="state-1", tenant_id=semantic_tenant, business_id="business-a", generated_at_ms=1
        )
    )
    state = SimpleNamespace(tenant_id="tenant-a", meta={"correlation_key": "tg:chat-1:42"}, world_model_semantics=semantics)
    ctx = SimpleNamespace(state=state, callback_data=CB_GROWTH_GENERATE, callback_query_id="cb-1")

    proposed = handle_growth_strategy(ctx, user_id="owner-1")

    assert proposed is not None
    assert proposed.action == "send_message@v1"
    assert "выбери бизнес" in proposed.payload["text"].lower()
    assert "business_id" not in proposed.payload
