from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import core.policies.telegram.unified_policy as unified_mod
from application.decision_policy.policy_stage import propose_action
from core.ai.action_ranking import rank_proposals, score_proposal
from core.policies.telegram.helpers import ProposedAction, normalize_proposed_action, propose
from core.retention.engine import RetentionEvaluation, RetentionOfferCandidate


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


def test_canonical_ranking_uses_ephemeral_metadata_and_strips_it() -> None:
    base = propose("send_message@v1", {"user_id": "u", "text": "base"})
    offer = propose(
        "send_message@v1",
        {"user_id": "u", "text": "offer"},
        ranking={"expected_profit_delta_minor": 1000.0, "risk_penalty": 0.1},
    )
    ranked = rank_proposals([base, offer])
    assert ranked[0].payload["text"] == "offer"
    assert "ranking" not in ranked[0].payload
    score, _ = score_proposal(
        action="x",
        payload={},
        ranking={"expected_profit_delta_minor": float("nan")},
    )
    assert score == 0.0

    class Policy:
        allow_rank_fallback = True

        def propose_many(self, _state):
            return [base, offer]

        def propose(self, _state):
            return base

    class Trace:
        def __init__(self) -> None:
            self.steps = []

        def try_add_step(self, **kwargs: Any) -> None:
            self.steps.append(kwargs)

    selected = propose_action(policy=Policy(), state=object(), trace=Trace())
    assert selected.payload["text"] == "offer"
    assert selected.ranking == {}


def test_normalize_mapping_never_leaks_ranking_into_payload() -> None:
    normalized = normalize_proposed_action(
        {"action": "send_message@v1", "text": "x", "ranking": {"risk_penalty": 9}}
    )
    assert normalized.payload == {"text": "x"}


def test_unified_policy_propose_many_preserves_base_and_exposes_retention(
    monkeypatch,
) -> None:
    evidence = evaluation(candidate())

    class FakeRetention:
        def __init__(self) -> None:
            self.states: list[Any] = []

        def evaluate(self, state: Any):
            self.states.append(state)
            return evidence

        def propose_candidates(
            self,
            *,
            state: Any,
            base: ProposedAction,
            evaluation: Any,
        ):
            self.states.append(state)
            assert evaluation is evidence
            return [
                base,
                propose(
                    "send_message@v1",
                    {"user_id": "user-a", "text": "offer"},
                    ranking={"expected_profit_delta_minor": 1},
                ),
            ]

    monkeypatch.setattr(
        unified_mod,
        "handle",
        lambda ctx, **_kwargs: propose(
            "send_message@v1",
            {
                "user_id": "user-a",
                "text": "base",
                "constraints": ctx.state.price_constraints,
            },
        ),
    )
    retention = FakeRetention()
    policy = unified_mod.UnifiedTelegramPolicyV3(retention=retention)
    state = FakeState(user={"roles": []}, session={"text": "hello"})
    direct = policy.propose(state)
    assert direct.payload["text"] == "base"
    many = policy.propose_many(state)
    assert [item.payload["text"] for item in many] == ["base", "offer"]
    assert many[0].payload["constraints"] is None
    assert len(retention.states) == 2


def test_unified_skips_retention_for_admin_domain_or_no_update(monkeypatch) -> None:
    class FailingRetention:
        def evaluate(self, _state):
            raise AssertionError("retention must not run")

    monkeypatch.setattr(
        unified_mod,
        "handle",
        lambda *_args, **_kwargs: propose("noop@v1", {}),
    )
    admin = unified_mod.UnifiedTelegramPolicyV3(
        retention=FailingRetention(),
        admin_user_ids=("user-a",),
    )
    assert len(admin.propose_many(FakeState())) == 1
    no_update = FakeState(telegram_update=None)
    assert (
        len(
            unified_mod.UnifiedTelegramPolicyV3(
                retention=FailingRetention()
            ).propose_many(no_update)
        )
        == 1
    )

    class Sales:
        def propose(self, _state):
            return propose("noop@v1", {"domain": "sales"})

    policy = unified_mod.UnifiedTelegramPolicyV3(retention=FailingRetention())
    policy._sales = Sales()
    out = policy.propose_many(FakeState(product={"domain": "sales"}))
    assert out[0].payload["domain"] == "sales"
