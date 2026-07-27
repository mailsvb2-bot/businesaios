from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import core.policies.telegram.unified_policy as unified_mod
from core.policies.telegram.helpers import propose
from core.policies.telegram.retention_integration import apply_retention_constraints_to_state
from core.retention.decision_adapter_support import merge_inline_keyboards
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


def test_retention_integration_no_debug_and_existing_constraints() -> None:
    state = FakeState(price_constraints={"mode": "safe"})
    assert apply_retention_constraints_to_state(state=state) is state
    low_risk = RetentionEvaluation(
        tenant_id="t",
        day_key="d",
        day_index=1,
        hazard=0.1,
        readiness=0.8,
        suppressed=False,
        reason="x",
        candidates=(),
        debug={},
    )
    assert apply_retention_constraints_to_state(
        state=state,
        evaluation=low_risk,
    ) is state


def test_unified_invalid_ttl_bad_pricing_and_retention_constraint_rebuild(
    monkeypatch,
) -> None:
    evidence = RetentionEvaluation(
        tenant_id="tenant-a",
        day_key="d",
        day_index=1,
        hazard=0.9,
        readiness=0.5,
        suppressed=False,
        reason="none",
        candidates=(),
        debug={},
    )

    class Retention:
        def evaluate(self, _state):
            return evidence

        def propose_candidates(self, *, state, base, evaluation):
            assert state.price_constraints == {"max_band": "low"}
            return [base]

    monkeypatch.setattr(
        unified_mod,
        "handle",
        lambda ctx, **_kwargs: propose(
            "send_message@v1",
            {"text": "x", "constraints": ctx.state.price_constraints},
        ),
    )
    policy = unified_mod.UnifiedTelegramPolicyV3(
        gift_ttl_sec="bad",
        retention=Retention(),
    )
    state = FakeState(
        user={"pricing_suggestions": {"ok": "2", "bad": "x"}},
        session={},
    )
    out = policy.propose_many(state)
    assert out[0].payload["constraints"] == {"max_band": "low"}


def test_support_readers_decorators_and_keyboard_branches(monkeypatch) -> None:
    import core.retention.decision_adapter_support as support

    calls: list[str] = []
    monkeypatch.setattr(
        support,
        "log_exception_throttled",
        lambda *_args, **kwargs: calls.append(kwargs["key"]),
    )
    assert support.read_outbound_metrics(
        reader=lambda: {"qsize": 1},
        logger=None,
    ) == {"qsize": 1}
    assert support.read_outbound_metrics(
        reader=lambda: (_ for _ in ()).throw(RuntimeError()),
        logger=None,
    ) == {}

    class BadState:
        @property
        def economy(self):
            raise RuntimeError

    assert support.read_entitlements_from_state(
        state=SimpleNamespace(economy={"entitlements": {"x": 1}}),
        logger=None,
    ) == {"x": 1}
    assert support.read_entitlements_from_state(
        state=SimpleNamespace(economy=None),
        logger=None,
    ) is None
    assert support.read_entitlements_from_state(state=BadState(), logger=None) is None
    assert calls == ["retention.outbound_metrics", "retention.entitlements"]

    import core.retention.telemetry

    monkeypatch.setattr(
        core.retention.telemetry,
        "with_retention_telemetry",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError()),
    )
    throttled: list[str] = []
    monkeypatch.setattr(
        support,
        "exception_throttled",
        lambda *_args, **kwargs: throttled.append(kwargs["key"]),
    )
    payload = {"x": 1}
    assert support.decorate_retention_payload(
        payload=payload,
        user_id="u",
        key="k",
        msg="m",
    ) is payload
    assert throttled == ["k|u"]

    assert merge_inline_keyboards({"inline_keyboard": [[1]]}, None) == {
        "inline_keyboard": [[1]]
    }
    assert merge_inline_keyboards(None, {"inline_keyboard": [[2]]}) == {
        "inline_keyboard": [[2]]
    }
    assert merge_inline_keyboards(
        {"inline_keyboard": [[1]]},
        {"inline_keyboard": [[2]]},
    ) == {"inline_keyboard": [[1], [2]]}


def test_support_private_boundaries_and_offer_rejections(monkeypatch) -> None:
    import core.retention.decision_adapter_support as support

    assert support._max_band(SimpleNamespace(price_constraints=None)) is None
    assert (
        support._max_band(SimpleNamespace(price_constraints={"max_band": " low "}))
        == "low"
    )
    assert support._max_band(SimpleNamespace(price_constraints={"max_band": 1})) is None
    assert support._safe_mode_blocks(
        state=SimpleNamespace(price_constraints=None),
        arm="a",
    ) == (False, "")
    assert support._safe_mode_blocks(
        state=SimpleNamespace(price_constraints={"mode": "normal"}),
        arm="a",
    ) == (False, "")
    assert support._safe_mode_blocks(
        state=SimpleNamespace(
            price_constraints={"mode": "safe", "disallow_offer_prefixes": "x"}
        ),
        arm="a",
    ) == (False, "")
    assert support._safe_mode_blocks(
        state=SimpleNamespace(
            price_constraints={"mode": "safe", "disallow_offer_prefixes": [1, "x"]}
        ),
        arm="a",
    ) == (False, "")
    assert support._combined_text(base_text="", offer_text="offer") == "offer"
    assert support._combined_text(base_text="base", offer_text=" ") is None
    assert support._combined_text(base_text="x" * 4096, offer_text="y") is None

    evidence = evaluation(candidate())
    base = propose("send_message@v1", {"user_id": "u", "text": "base"})
    monkeypatch.setattr(support, "offer_allowed", lambda **_kwargs: False)
    assert support.build_offer_proposal(
        base=base,
        evaluation=evidence,
        candidate=candidate(),
        state=FakeState(),
        offer_engine=FakeOfferEngine(),
        cooldown_store=None,
        user_id="u",
    ) is None
    monkeypatch.setattr(support, "offer_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(
        support,
        "render_offer_step",
        lambda **_kwargs: ({"fallback_text": "", "reply_markup": None}, {}),
    )
    assert support.build_offer_proposal(
        base=base,
        evaluation=evidence,
        candidate=candidate(),
        state=FakeState(),
        offer_engine=FakeOfferEngine(),
        cooldown_store=None,
        user_id="u",
    ) is None
