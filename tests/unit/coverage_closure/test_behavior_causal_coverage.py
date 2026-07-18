from __future__ import annotations

from types import SimpleNamespace

from core.behavior.complex4 import Complex4
from core.behavior.dirac_behavior import DiracBehaviorModel
from core.behavior.dirac_operators import apply_event_operator
from core.behavior.org_field import OrgField, aggregate_org_observables
from core.behavior_graph.event_mapping import map_event, map_events
from core.causal.evidence import from_events
from core.causal.evidence.from_events import build_daily_panel


def test_event_mapping_org_field_and_dirac_operator(monkeypatch) -> None:
    class BadString:
        def __str__(self) -> str:
            raise RuntimeError("broken")

    assert map_event([]) is None
    assert map_event({"tenant_id": "t", "user_id": "", "event_type": "x"}) is None
    assert map_event({"tenant_id": BadString(), "user_id": "u", "event_type": "x"}) is None
    mapped = map_event(
        {
            "tenant_id": " t ",
            "user_id": " u ",
            "type": " clicked ",
            "timestamp_ms": "bad",
            "payload": {
                "product_id": "p",
                "entity_type": "product_id",
                "entity_id": "p",
                "feature": "f",
            },
        }
    )
    assert mapped is not None
    assert mapped.timestamp_ms == 0
    assert mapped.entities == [("product_id", "p"), ("feature", "f")]
    ordered = map_events(
        [
            {"tenant_id": "t", "user_id": "u", "event_type": "b", "timestamp_ms": 2},
            {"tenant_id": "t", "user_id": "u", "event_type": "a", "timestamp_ms": 1, "payload": []},
            {"tenant_id": "", "user_id": "u", "event_type": "x"},
        ]
    )
    assert [item.event_type for item in ordered] == ["a", "b"]

    model = DiracBehaviorModel()
    assert aggregate_org_observables(model=model, field=OrgField.empty(), now_ms=1)["org_engagement"] == 0.0
    single = OrgField(
        psi_by_role={"champion": Complex4((1, 0, 0, 0), (0, 0, 0, 0))},
        anti_by_role={"champion": 0.2},
    )
    single_result = aggregate_org_observables(model=model, field=single, now_ms=10)
    assert 0.0 <= single_result["org_alignment"] <= 1.0
    multi = OrgField(
        psi_by_role={
            "decision_maker": Complex4((1, 0, 0, 0), (0, 0, 0, 0)),
            "unknown": Complex4((0, 1, 0, 0), (0, 0, 0, 0)),
        },
        anti_by_role={"decision_maker": 0.1, "unknown": 0.5},
    )
    multi_result = aggregate_org_observables(model=model, field=multi, now_ms=20)
    assert 0.0 <= multi_result["org_blocker_index"] <= 1.0

    psi = Complex4.zeros().renormalize()
    denied_ctx: dict[str, object] = {}
    monkeypatch.setattr("core.behavior.dirac_operators.is_operator_allowed", lambda **_kwargs: False)
    denied = apply_event_operator(psi=psi, anti=2.0, event={"event_type": "ui_click"}, context=denied_ctx)
    assert denied.psi == psi
    assert denied.anti == 1.0

    monkeypatch.setattr("core.behavior.dirac_operators.is_operator_allowed", lambda **_kwargs: True)
    actual = apply_event_operator(
        psi=psi,
        anti=0.2,
        event={"event_type": "ui_click", "payload": {"rage": 1}},
        context={"operator_overrides": {"event_scales": {"ui_click": 3.0}}},
    )
    assert 0.0 <= actual.anti <= 1.0
    closed = apply_event_operator(
        psi=actual.psi,
        anti=actual.anti,
        event={"event_type": "paywall_closed"},
        context={},
    )
    assert closed.anti >= actual.anti

    class BrokenCatalog:
        def scale_for(self, **_kwargs):
            raise RuntimeError("broken scale")

    monkeypatch.setattr(
        "core.behavior.dirac_operators.resolve_operator_params",
        lambda _ctx: {
            "catalog": BrokenCatalog(),
            "domain": "x",
            "event_scales": {"ui_click": "bad"},
            "phase_gain": 0.25,
            "k_tp": 0.08,
            "k_vp": 0.06,
            "k_it": 0.04,
            "anti_drain": 0.15,
        },
    )
    recovered = apply_event_operator(
        psi=psi,
        anti=0.0,
        event={"event_type": "ui_click"},
        context={},
    )
    assert recovered.psi.norm2() > 0.0


def test_causal_daily_panel_estimate_and_placebo(monkeypatch) -> None:
    assert build_daily_panel([], treatment_event_types=(), outcome_event_types=("sale",)).meta["reason"] == "empty_types"
    assert build_daily_panel(["bad", {"event_type": "sale"}], treatment_event_types=("ad",), outcome_event_types=("sale",)).meta["reason"] == "no_buckets"

    day = 86_400_000
    events = [
        {"timestamp_ms": day, "event_type": "ad"},
        {"timestamp_ms": day, "event_type": "sale", "payload": {"amount_minor": "bad"}},
        {"timestamp_ms": day, "event_type": "sale", "payload": {"amount": 20}},
        {"ts_ms": day * 2, "type": "sale", "payload": {}},
        {"time_ms": day * 3, "name": "ad"},
        {"created_at_ms": "bad", "event_type": "sale"},
    ]
    panel = build_daily_panel(
        events,
        treatment_event_types=("ad",),
        outcome_event_types=("sale",),
        max_days=2,
    )
    assert len(panel.rows) == 2
    assert panel.meta["y_kind"] == "count"
    assert panel.rows[-1].covariates["prev_y"] == 1.0

    captured: list[tuple[object, object]] = []
    monkeypatch.setattr(
        from_events,
        "estimate_causal_effect",
        lambda dataset, *, query: captured.append((dataset, query)) or SimpleNamespace(effect=1.0),
    )
    assert from_events.estimate_effect_from_daily_panel(from_events.DailyPanel([], {})) is None
    assert from_events.estimate_effect_from_daily_panel(panel).effect == 1.0
    assert from_events.placebo_shift_treatment(from_events.DailyPanel([], {})) is None
    assert from_events.placebo_shift_treatment(panel, shift_days=0).effect == 1.0
    assert from_events.placebo_shift_treatment(panel, shift_days=1).effect == 1.0
    assert from_events.placebo_shift_treatment(panel, shift_days=-1).effect == 1.0
    assert len(captured) == 4
