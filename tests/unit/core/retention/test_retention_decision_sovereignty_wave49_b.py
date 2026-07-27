from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

import core.retention.arms as arms_mod
import core.retention.engine as engine_mod
import core.retention.pricing_flow as pricing_mod
import core.policies.telegram.unified_policy as unified_mod
from application.decision_policy.policy_stage import propose_action
from core.ai.action_ranking import rank_proposals, score_proposal
from core.policies.telegram.helpers import ProposedAction, normalize_proposed_action, propose
from core.policies.telegram.retention_integration import (
    apply_retention_constraints_to_state,
    merge_retention_plan,
)
from core.retention.arms import RetentionArmEvidence
from core.retention.bandit import choose_arm, update_arm
from core.retention.decision_adapter import RetentionDecisionAdapter
from core.retention.decision_adapter_support import (
    build_offer_proposal,
    merge_inline_keyboards,
)
from core.retention.engine import (
    RetentionEvaluation,
    RetentionOfferCandidate,
    materialize_candidate,
    neutral_decision,
)
from core.retention.pricing_flow import RetentionPriceEvidence
from runtime._internal.effects_actions.telegram.messaging_parts.tracking import (
    track_business_event,
)


class FakeStore:
    def __init__(self, events: list[dict[str, Any]] | None = None) -> None:
        self.events = list(events or [])
        self.updated: list[tuple[str, bool]] = []
        self.ensure_calls = 0
        self.feature_writes = 0
        self.bandits: dict[str, tuple[Any, Any]] = {}

    def iter_events(self, **kwargs: Any):
        del kwargs
        return iter(self.events)

    def latest_events(self, **kwargs: Any):
        event_type = kwargs.get("event_type")
        return [
            event
            for event in self.events
            if event_type is None or event.get("event_type") == event_type
        ]

    def bandit_get_arm(self, *, tenant_id: str, arm: str):
        del tenant_id
        return self.bandits.get(arm, (1, 1))

    def bandit_ensure_arm(self, **kwargs: Any) -> None:
        del kwargs
        self.ensure_calls += 1

    def bandit_update_arm(self, *, tenant_id: str, arm: str, success: bool, now_ms: int):
        del tenant_id, now_ms
        self.updated.append((arm, success))

    def upsert_user_features_daily(self, **kwargs: Any) -> None:
        del kwargs
        self.feature_writes += 1


@dataclass(frozen=True)
class FakeState:
    schema_version: int = 1
    user: dict[str, Any] = field(default_factory=dict)
    session: dict[str, Any] = field(default_factory=dict)
    product: dict[str, Any] = field(default_factory=dict)
    economy: dict[str, Any] = field(default_factory=dict)
    timestamp_ms: int = 1_000_000
    tenant_id: str = "tenant-a"
    user_id: str | None = "user-a"
    price_constraints: dict[str, Any] | None = None
    telegram_update: dict[str, Any] | None = field(
        default_factory=lambda: {"message": {"chat": {"id": 11}}}
    )


def candidate(
    ident: str = "c1",
    *,
    arm: str = "offer_30_14900",
    price: int = 14_900,
    profit: float = 1000.0,
) -> RetentionOfferCandidate:
    return RetentionOfferCandidate(
        candidate_id=ident,
        offer_arm=arm,
        offer_price_rub=price,
        expected_profit_delta_minor=profit,
        ope_wis=0.6,
        uplift=0.7,
        risk_penalty=0.1,
        propensity=0.5,
        debug={"source": "test"},
    )


def evaluation(*items: RetentionOfferCandidate, suppressed: bool = False) -> RetentionEvaluation:
    return RetentionEvaluation(
        tenant_id="tenant-a",
        day_key="2026-01-10",
        day_index=10,
        hazard=0.1,
        readiness=0.7,
        suppressed=suppressed,
        reason="suppressed" if suppressed else "candidates_ready",
        candidates=tuple(items),
        debug={"features": {"x": 1.0}, "no_second_brain": True},
    )


class FakeOfferEngine:
    def should_show_offer(self, **_kwargs: Any):
        return True, {"reason": "ok"}

    def render_offer(self, **kwargs: Any):
        return SimpleNamespace(
            text=f"Оффер за {kwargs['price_rub']} ₽",
            variant="a",
            price_rub=kwargs["price_rub"],
            meta={
                "reply_markup": {
                    "inline_keyboard": [[{"text": "Купить", "callback_data": "buy"}]]
                }
            },
        )


class FakeCooldown:
    def __init__(self) -> None:
        self.marks = 0

    def get_last_shown_ms(self, **_kwargs: Any):
        return None

    def mark_shown_now(self, **_kwargs: Any) -> None:
        self.marks += 1


def test_offer_candidate_is_one_complete_message_and_no_prewrite() -> None:
    cooldown = FakeCooldown()
    base = propose(
        "send_message@v1",
        {
            "user_id": "user-a",
            "text": "Базовый ответ",
            "reply_markup": {"inline_keyboard": [[{"text": "Меню", "callback_data": "menu"}]]},
            "track_event_type": "base_shown",
            "track_payload": {"base": True},
        },
    )
    result = build_offer_proposal(
        base=base,
        evaluation=evaluation(candidate()),
        candidate=candidate(),
        state=FakeState(),
        offer_engine=FakeOfferEngine(),
        cooldown_store=cooldown,
        user_id="user-a",
    )
    assert result is not None and result.action == "send_message@v1"
    assert result.payload["text"] == "Базовый ответ\n\nОффер за 14900 ₽"
    assert len(result.payload["reply_markup"]["inline_keyboard"]) == 2
    assert result.payload["track_event_type"] == "offer_shown"
    assert result.payload["track_payload"]["additional_track_events"][0]["event_type"] == "base_shown"
    assert result.ranking["expected_profit_delta_minor"] == 1000.0
    assert cooldown.marks == 0


def test_offer_candidate_respects_action_type_safe_mode_length_and_keyboard() -> None:
    evidence = evaluation(candidate())
    state = FakeState(price_constraints={"mode": "safe", "disallow_offer_prefixes": ["offer_"]})
    assert build_offer_proposal(
        base=propose("noop@v1", {}),
        evaluation=evidence,
        candidate=candidate(),
        state=state,
        offer_engine=FakeOfferEngine(),
        cooldown_store=None,
        user_id="u",
    ) is None
    assert build_offer_proposal(
        base=propose("send_message@v1", {"user_id": "u", "text": "x"}),
        evaluation=evidence,
        candidate=candidate(),
        state=state,
        offer_engine=FakeOfferEngine(),
        cooldown_store=None,
        user_id="u",
    ) is None
    assert merge_inline_keyboards(None, None) is None
    assert merge_inline_keyboards({"keyboard": []}, {"inline_keyboard": []}) == {"inline_keyboard": []}


def test_adapter_exposes_base_and_candidates_but_compat_plan_is_telemetry(monkeypatch) -> None:
    adapter = RetentionDecisionAdapter(
        event_store=FakeStore(),
        tenant_id="tenant-a",
        offer_engine=FakeOfferEngine(),
        offer_cooldown_store=FakeCooldown(),
    )
    evidence = evaluation(candidate())
    monkeypatch.setattr(adapter, "evaluate", lambda _state: evidence)
    proposals = adapter.propose_candidates(
        state=FakeState(),
        base=propose("send_message@v1", {"user_id": "user-a", "text": "base"}),
        evaluation=evidence,
    )
    assert len(proposals) == 2 and proposals[0].ranking == {}
    monkeypatch.setattr(adapter._engine, "compute_evidence", lambda **_kwargs: evidence)
    plan = adapter.compute_plan(FakeState())
    assert [step["action"] for step in plan.steps] == ["track_event@v1"]
    assert all(step["action"] != "send_marketing_offer@v1" for step in plan.steps)


def test_constraints_and_legacy_plan_never_create_execute_plan() -> None:
    state = FakeState()
    high_risk = RetentionEvaluation(
        tenant_id="tenant-a",
        day_key="d",
        day_index=1,
        hazard=0.9,
        readiness=0.5,
        suppressed=False,
        reason="no_candidates",
        candidates=(),
        debug={},
    )
    constrained = apply_retention_constraints_to_state(state=state, evaluation=high_risk)
    assert constrained.price_constraints == {"max_band": "low"}
    base = {"action": "send_message@v1", "user_id": "u", "text": "x"}
    merged = merge_retention_plan(base=base, plan=SimpleNamespace(steps=[{"action": "x"}]), user_id="u")
    assert merged.action == "send_message@v1"
