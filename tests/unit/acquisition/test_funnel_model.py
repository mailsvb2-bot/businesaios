from __future__ import annotations

from acquisition.funnel_model import FunnelModel, FunnelStage


def test_funnel_model_summarizes_conversion_cycle_and_touchpoints() -> None:
    model = FunnelModel()
    snapshot = model.summarize(
        (
            FunnelStage(name="visit_to_lead", conversion_rate=0.2, avg_stage_days=2.0, touchpoints=1),
            FunnelStage(name="lead_to_call", conversion_rate=0.5, avg_stage_days=3.0, touchpoints=2),
            FunnelStage(name="call_to_sale", conversion_rate=0.25, avg_stage_days=5.0, touchpoints=3),
        )
    )
    assert snapshot.stage_count == 3
    assert snapshot.overall_conversion_rate == 0.025
    assert snapshot.avg_cycle_days == 10.0
    assert snapshot.touchpoints_per_customer == 6
    assert snapshot.stage_dropoffs == (("visit_to_lead", 0.8), ("lead_to_call", 0.5), ("call_to_sale", 0.75))


def test_funnel_model_required_entries_for_target_customers() -> None:
    snapshot = FunnelModel().summarize((FunnelStage(name="s1", conversion_rate=0.5), FunnelStage(name="s2", conversion_rate=0.2)))
    assert snapshot.overall_conversion_rate == 0.1
    assert snapshot.required_entries_for_customers(10) == 100
    assert snapshot.expected_customers_from_entries(250) == 25


def test_funnel_model_returns_zero_snapshot_for_empty_funnel() -> None:
    snapshot = FunnelModel().summarize(())
    assert snapshot.stage_count == 0
    assert snapshot.overall_conversion_rate == 0.0
    assert snapshot.avg_cycle_days == 0.0
    assert snapshot.touchpoints_per_customer == 0
    assert snapshot.stage_dropoffs == ()
    assert snapshot.required_entries_for_customers(10) == 0
    assert snapshot.expected_customers_from_entries(100) == 0


def test_funnel_model_normalizes_invalid_values_without_crashing() -> None:
    snapshot = FunnelModel().summarize((FunnelStage(name="bad", conversion_rate=2.0, avg_stage_days=-4.0, touchpoints=0),))
    assert snapshot.stage_count == 1
    assert snapshot.overall_conversion_rate == 1.0
    assert snapshot.avg_cycle_days == 0.0
    assert snapshot.touchpoints_per_customer == 1
    assert snapshot.stage_dropoffs == (("bad", 0.0),)
