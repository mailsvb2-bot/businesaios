from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from application.decision_policy.policy_stage import propose_action
from core.ai.action_ranking import rank_proposals, score_proposal
from core.policies.telegram.helpers import normalize_proposed_action, propose
from core.retention.engine import RetentionEvaluation, RetentionOfferCandidate
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


def test_tracking_emits_offer_and_original_base_event() -> None:
    class Log:
        def __init__(self) -> None:
            self.events: list[dict[str, Any]] = []

        def emit(self, **kwargs: Any) -> None:
            self.events.append(kwargs)

    owner = SimpleNamespace(event_log=Log())
    track_business_event(
        owner,
        user_id="u",
        decision_id="d",
        correlation_id="c",
        track_event_type="offer_shown",
        track_payload={
            "offer": "a",
            "additional_track_events": [
                {"event_type": "base_shown", "payload": {"base": True}},
                None,
                {"event_type": "", "payload": {}},
            ],
        },
    )
    assert [event["event_type"] for event in owner.event_log.events] == [
        "offer_shown",
        "base_shown",
    ]


def test_policy_stage_fallbacks_and_materialization_paths() -> None:
    class Trace:
        def __init__(self) -> None:
            self.steps: list[dict[str, Any]] = []

        def try_add_step(self, **kwargs: Any) -> None:
            self.steps.append(kwargs)

    base = propose("noop@v1", {"x": 1})

    class Plain:
        def propose(self, _state):
            return base

    assert propose_action(policy=Plain(), state=None, trace=Trace()) is base

    class Empty:
        allow_rank_fallback = True

        def propose_many(self, _state):
            return []

        def propose(self, _state):
            return base

    trace = Trace()
    assert propose_action(policy=Empty(), state=None, trace=trace) is base
    assert trace.steps[-1]["output"]["reason"] == "empty_candidates"

    class Broken(Empty):
        def propose_many(self, _state):
            raise LookupError("boom")

    assert propose_action(policy=Broken(), state=None, trace=Trace()) is base

    class Locked(Broken):
        allow_rank_fallback = False

    with pytest.raises(RuntimeError, match="DECISION_POLICY_STAGE_FAILED"):
        propose_action(policy=Locked(), state=None, trace=Trace())

    class Unrankable(Empty):
        def propose_many(self, _state):
            return [{"payload": {"x": 1}}]

    assert propose_action(policy=Unrankable(), state=None, trace=Trace()) is base

    class MappingPolicy:
        def propose_many(self, _state):
            return [
                {"action": "noop@v1", "payload": {"x": 1}, "ranking": {"uplift": 1}}
            ]

    mapped = propose_action(policy=MappingPolicy(), state=None, trace=Trace())
    assert mapped.action == "noop@v1" and mapped.payload == {"x": 1}

    class OddProposal:
        def __init__(self, impossible: str) -> None:
            self.impossible = impossible

    odd = OddProposal("x")
    odd.action = "noop@v1"
    odd.payload = {"x": 1}
    odd.ranking = {"uplift": 2}

    class OddPolicy:
        def propose_many(self, _state):
            return [odd]

    materialized = propose_action(policy=OddPolicy(), state=None, trace=Trace())
    assert materialized.action == "noop@v1"


def test_action_ranking_mapping_shapes_invalid_values_and_stable_ties() -> None:
    proposals = [
        {"action": "a", "payload": {"text": "first"}, "ranking": {"uplift": 1}},
        {"action": "b", "text": "second", "ranking": {"uplift": 1}},
        {"payload": {}},
        object(),
        {"action": "bad", "ranking": {"uplift": object()}},
    ]
    ranked = rank_proposals(proposals)
    assert [item.action for item in ranked[:2]] == ["a", "b"]
    assert ranked[1].payload == {"text": "second"}
    assert all(item.action != "" for item in ranked)
    score, _ = score_proposal(
        action="x",
        payload={
            "expected_profit_delta_minor": "bad",
            "ope_wis": 1,
            "uplift": 2,
            "risk_penalty": float("inf"),
        },
    )
    assert score == 1200.0


def test_helpers_normalization_messages_variants_and_legacy_prices(monkeypatch) -> None:
    from core.policies.telegram import helpers

    original = propose("noop@v1", {"x": 1})
    assert normalize_proposed_action(original) is original
    with pytest.raises(TypeError):
        normalize_proposed_action(object())
    with pytest.raises(ValueError):
        normalize_proposed_action({"payload": {}})
    assert normalize_proposed_action(
        {"action": "noop@v1", "payload": {"x": 2}, "extra": 3}
    ).payload == {"x": 2}

    message = helpers.propose_message(
        user_id="u",
        text="hello",
        reply_markup={"inline_keyboard": []},
        callback_query_id=" cb ",
        track_event_type=" shown ",
        track_payload={"x": 1},
    )
    assert message.payload["callback_query_id"] == "cb"
    assert message.payload["track_event_type"] == "shown"
    plain = helpers.propose_message(user_id="", text="x")
    assert plain.payload == {"user_id": "anonymous", "text": "x"}

    first = helpers.choose_marketing_variant(user_id="u", step_key="s", seed="1")
    assert first in {"a", "b"}
    assert helpers.choose_marketing_variant(
        user_id="u",
        step_key="s",
        seed="1",
        bandit={"a": {"alpha": "bad"}, "b": {}},
    ) == first
    selected = helpers.choose_marketing_variant(
        user_id="u",
        step_key="s",
        seed="1",
        bandit={
            "a": {"alpha": 10, "beta": 1},
            "b": {"alpha": 1, "beta": 10},
        },
    )
    assert selected in {"a", "b"}

    import core.plans

    monkeypatch.setattr(
        core.plans,
        "active_plans",
        lambda: [
            {"title": "A", "price": 123},
            {"title": "", "price": 10},
            {"title": "B", "price": "bad"},
        ],
    )
    assert helpers.build_legacy_prices(default_price_rub=4900) == {"A": 123}
    monkeypatch.setattr(core.plans, "active_plans", lambda: [])
    assert helpers.build_legacy_prices(default_price_rub=4900) == {
        "Полный доступ": 4900
    }
    monkeypatch.setattr(
        core.plans,
        "active_plans",
        lambda: (_ for _ in ()).throw(RuntimeError()),
    )
    assert helpers.build_legacy_prices(default_price_rub=1) == {"Полный доступ": 1}
