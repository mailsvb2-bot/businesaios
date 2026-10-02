from __future__ import annotations

import json

import pytest

from core.llm import (
    ContextBudget,
    ContextBudgetExceeded,
    ContextBuilder,
    ContextFact,
    ContextFreshnessViolation,
    ContextPrivacyViolation,
    ContextRequirement,
    ContextSource,
    LLMRequest,
    LLMResponse,
)
from core.llm.agent import LLMAgent, LLMAgentConfig, LLMTaskContext, TaskType


def test_context_builder_selects_only_required_information_with_provenance() -> None:
    builder = ContextBuilder()
    bundle = builder.build(
        task="offer.generate",
        requirements=[
            ContextRequirement(ContextSource.WORLD_MODEL, "business"),
            ContextRequirement(ContextSource.CONSTRAINT, "constraints"),
        ],
        world_model={
            "business": ContextFact(
                key="business",
                value={"category": "clinic"},
                source="world_model.business",
                evidence_ids=("ev-business",),
                critical=True,
            ),
            "unrequested": ContextFact(
                key="unrequested",
                value={"secret": "must-not-leak"},
                source="world_model.other",
            ),
        },
        constraints={
            "constraints": ContextFact(
                key="constraints",
                value={"cold_calls": False},
                source="constraint.owner",
                evidence_ids=("ev-constraint",),
            )
        },
        budget=ContextBudget(token_budget=200),
    )

    assert bundle.as_payload() == {
        "business": {"category": "clinic"},
        "constraints": {"cold_calls": False},
    }
    assert "unrequested" not in bundle.as_payload()
    assert bundle.provenance()["business"]["evidence_ids"] == ["ev-business"]


def test_context_builder_fails_closed_on_privacy_token_and_freshness_budgets() -> None:
    builder = ContextBuilder()
    requirement = [ContextRequirement(ContextSource.WORLD_MODEL, "business")]
    restricted = {
        "business": ContextFact(
            key="business",
            value={"sensitive": "value"},
            source="world_model.business",
            privacy_class="restricted",
        )
    }

    with pytest.raises(ContextPrivacyViolation):
        builder.build(
            task="offer.generate",
            requirements=requirement,
            world_model=restricted,
            budget=ContextBudget(
                token_budget=200,
                privacy_budget=frozenset({"public", "internal"}),
            ),
        )

    oversized = {
        "business": ContextFact(
            key="business",
            value={"text": "x" * 200},
            source="world_model.business",
        )
    }
    with pytest.raises(ContextBudgetExceeded):
        builder.build(
            task="offer.generate",
            requirements=requirement,
            world_model=oversized,
            budget=ContextBudget(token_budget=2),
        )

    stale = {
        "business": ContextFact(
            key="business",
            value={"category": "clinic"},
            source="world_model.business",
            observed_at=100.0,
        )
    }
    with pytest.raises(ContextFreshnessViolation):
        builder.build(
            task="offer.generate",
            requirements=requirement,
            world_model=stale,
            budget=ContextBudget(token_budget=200, max_age_seconds=60.0),
            now_s=200.0,
        )


def test_critical_context_requires_evidence() -> None:
    with pytest.raises(ValueError, match="critical context requires evidence_ids"):
        ContextFact(
            key="business",
            value={"category": "clinic"},
            source="world_model.business",
            critical=True,
        )


class _CaptureGateway:
    def __init__(self) -> None:
        self.request: LLMRequest | None = None

    def generate_sync(self, req: LLMRequest) -> LLMResponse:
        self.request = req
        return LLMResponse(content='{"ok": true}')


def test_llm_agent_uses_minimal_context_prompt_versions_and_provenance() -> None:
    gateway = _CaptureGateway()
    agent = LLMAgent(
        gateway,
        LLMAgentConfig(
            default_model="configured-model",
            model_profile_id="growth-profile",
        ),
    )
    context = LLMTaskContext(
        tenant_id="tenant-secret-not-for-prompt",
        user_id="user-secret-not-for-prompt",
        business={"category": "clinic"},
        offer={"name": "checkup"},
        audience={"segment": "adult"},
        campaign={"unused_for_offer": True},
        metrics={"unused_for_offer": True},
        constraints={"cold_calls": False},
        context_provenance={
            "business": "world_model.business",
            "offer": "world_model.offer",
            "audience": "world_model.audience",
            "constraints": "constraint.owner",
        },
        context_evidence_ids={"business": ("ev-business",)},
        context_critical_fields=("business",),
    )

    result = agent.run_task(TaskType.OFFER_GENERATE, context)

    assert gateway.request is not None
    request = gateway.request
    user_prompt = request.messages[1].content
    payload = json.loads(user_prompt.split("INPUT:\n", 1)[1])
    assert payload == {
        "business": {"category": "clinic"},
        "offer": {"name": "checkup"},
        "audience": {"segment": "adult"},
        "constraints": {"cold_calls": False},
    }
    assert "tenant-secret-not-for-prompt" not in user_prompt
    assert "user-secret-not-for-prompt" not in user_prompt
    assert "unused_for_offer" not in user_prompt
    assert request.prompt_versions == {
        "system": "growth.system.v1",
        "task": "offer.generate.v1",
    }
    assert request.model_profile_id == "growth-profile"
    assert request.metadata is not None
    assert request.metadata["preferred_model_profile_id"] == "growth-profile"
    assert (
        request.metadata["context_provenance"]["business"]["source"]
        == "world_model.business"
    )
    assert result.meta["prompt_versions"]["task"] == "offer.generate.v1"


def test_llm_agent_enforces_freshness_budget_on_real_request_path() -> None:
    gateway = _CaptureGateway()
    agent = LLMAgent(
        gateway,
        LLMAgentConfig(
            default_model="configured-model",
            context_max_age_seconds=60.0,
        ),
        clock=lambda: 200.0,
    )
    context = LLMTaskContext(
        tenant_id="tenant-a",
        business={"category": "clinic"},
        context_observed_at={"business": 100.0},
    )

    with pytest.raises(ContextFreshnessViolation):
        agent.run_task(TaskType.OFFER_GENERATE, context)

    assert gateway.request is None
