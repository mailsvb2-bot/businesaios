from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import core.retention.arms as arms_mod
from core.policies.telegram.helpers import propose
from core.policies.telegram.retention_integration import apply_retention_constraints_to_state
from core.retention.decision_adapter import RetentionDecisionAdapter
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


def test_adapter_evaluate_outbound_suppressed_and_error_paths(monkeypatch) -> None:
    logger = SimpleNamespace(warnings=[], warning=lambda *args: logger.warnings.append(args))
    adapter = RetentionDecisionAdapter(
        event_store=FakeStore(),
        tenant_id="tenant-a",
        logger=logger,
        prices={"p30": 100},
        outbound_metrics_reader=lambda: {"qsize": 2},
        offer_engine=FakeOfferEngine(),
    )
    captured: dict[str, Any] = {}

    def compute(**kwargs: Any):
        captured.update(kwargs)
        return evaluation(suppressed=True)

    monkeypatch.setattr(adapter._engine, "compute_evidence", compute)
    state = FakeState(user_id=None, session=None, economy={"entitlements": {"x": 1}})
    result = adapter.evaluate(state)
    assert result.suppressed
    assert captured["user_id"] == "anonymous"
    assert captured["outbound_telemetry"] == {"qsize": 2}
    assert adapter.propose_candidates(
        state=state,
        base={"action": "noop@v1"},
        evaluation=result,
    )[0].action == "noop@v1"

    monkeypatch.setattr(adapter._engine, "decide_offer", lambda **_kwargs: SimpleNamespace(ok=True))
    assert adapter.maybe_decide_offer(
        tenant_id="tenant-a", user_id="u", context={}
    ).ok is True
    monkeypatch.setattr(
        adapter._engine,
        "decide_offer",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert adapter.maybe_decide_offer(tenant_id="t", user_id="u", context={}) is None
    assert logger.warnings


def test_tracking_boundaries_delivery_and_warning() -> None:
    from runtime._internal.effects_actions.telegram.messaging_parts.tracking import (
        emit_warning,
        track_delivery,
    )

    track_delivery(
        SimpleNamespace(event_log=None),
        user_id="u",
        decision_id="d",
        correlation_id="c",
        channel="x",
        text="t",
        ok=True,
        meta={},
    )
    emit_warning(None, user_id="u", decision_id="d", correlation_id="c", reason="x")

    class Log:
        def __init__(self, fail: bool = False) -> None:
            self.events: list[dict[str, Any]] = []
            self.fail = fail

        def emit(self, **kwargs: Any) -> None:
            if self.fail:
                self.fail = False
                raise RuntimeError("first")
            self.events.append(kwargs)

    log = Log()
    owner = SimpleNamespace(event_log=log)
    track_delivery(
        owner,
        user_id="u",
        decision_id="d",
        correlation_id="c",
        channel="x",
        text="t",
        ok=True,
        meta={"a": 1},
    )
    assert log.events[0]["event_type"] == "message_sent"
    emit_warning(log, user_id="", decision_id="", correlation_id="", reason="r", error=ValueError())
    assert log.events[-1]["event_type"] == "messaging_effect_warning"
    track_business_event(
        owner,
        user_id="u",
        decision_id="d",
        correlation_id="c",
        track_event_type=None,
        track_payload=None,
    )

    failing = SimpleNamespace(event_log=Log(fail=True))
    track_business_event(
        failing,
        user_id="u",
        decision_id="d",
        correlation_id="c",
        track_event_type="x",
        track_payload={},
    )
    assert failing.event_log.events[-1]["event_type"] == "messaging_effect_warning"


def test_final_branch_closure(monkeypatch) -> None:
    import core.ai.action_ranking as ranking_mod
    import core.policies.telegram.helpers as helpers
    import core.retention.decision_adapter_support as support

    monkeypatch.setattr(
        ranking_mod,
        "score_proposal",
        lambda **_kwargs: (_ for _ in ()).throw(OverflowError()),
    )
    assert ranking_mod.rank_proposals([propose("noop@v1", {})]) == []

    assert helpers.propose_message(
        user_id="u", text="x", track_event_type="event", track_payload={}
    ).payload["track_event_type"] == "event"

    class BrokenRng:
        def __init__(self, _seed: int) -> None:
            pass

        def betavariate(self, *_args: Any) -> float:
            raise RuntimeError

    monkeypatch.setattr(helpers.random, "Random", BrokenRng)
    result = helpers.choose_marketing_variant(
        user_id="u",
        step_key="s",
        bandit={"a": {}, "b": {}},
    )
    assert result in {"a", "b"}

    assert apply_retention_constraints_to_state(
        state=FakeState(),
        evaluation=SimpleNamespace(debug="not-a-dict"),
    ) == FakeState()

    assert support.build_offer_proposal(
        base=propose("send_message@v1", {"text": "x"}),
        evaluation=RetentionEvaluation("", "d", 1, .1, .8, False, "x", (candidate(),), {}),
        candidate=candidate(),
        state=FakeState(tenant_id="default"),
        offer_engine=FakeOfferEngine(),
        cooldown_store=None,
        user_id="u",
    ) is None


def test_arm_remaining_timestamp_window_and_catalog_branches(monkeypatch) -> None:
    now = 10_000
    recent = FakeStore(
        [
            {
                "event_type": "offer_shown",
                "payload": {"arm": "offer_30_14900", "day_index": 999},
                "timestamp_ms": now - 1,
            }
        ]
    )
    assert arms_mod.arm_already_shown_in_window(
        recent,
        tenant_id="t",
        user_id="u",
        arm="offer_30_14900",
        window_day_from=1,
        window_day_to=2,
        now_ms=now,
    )
    malformed = FakeStore(
        [
            {
                "event_type": "offer_shown",
                "payload": {"arm": "offer_30_14900", "day_index": "bad"},
                "timestamp_ms": "bad",
            }
        ]
    )
    assert not arms_mod.arm_already_shown_in_window(
        malformed,
        tenant_id="t",
        user_id="u",
        arm="offer_30_14900",
        window_day_from=1,
        window_day_to=2,
        now_ms=now,
        logger=None,
    )
    store = FakeStore([{"event_type": "offer_outcome", "payload": {"arm": "a", "success": None}}])
    assert arms_mod.score_arm_candidates_event_sourced(
        store,
        tenant_id="t",
        user_id="u",
        arms=[("a", 1)],
        now_ms=now,
    )[0].source == "bandit_state"

    monkeypatch.setattr(arms_mod, "is_allowed_arm", lambda arm: arm != "blocked")
    policy = SimpleNamespace(
        offer_30_arm="blocked",
        offer_bundle_arm="bundle",
        offer_90_arm="ninety",
        default_candidate_weight=1,
    )
    built, _ = arms_mod.build_candidates(day_index=0, policy=policy)
    assert built == []
    monkeypatch.setattr(arms_mod, "ladder_base_price_for_arm", lambda *_args, **_kwargs: None)
    assert arms_mod.base_price_for_arm("offer_bundle_14_30", {"bundle_14_30": 333}) == 333
