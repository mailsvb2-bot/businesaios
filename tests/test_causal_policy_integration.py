from __future__ import annotations

import time

from core.ai.causal_guardrails import assess_causal_evidence
from core.causal.evidence.from_events import (
    build_daily_panel,
    estimate_effect_from_daily_panel,
    placebo_shift_treatment,
)


def _ev(day_index: int, event_type: str, payload: dict | None = None):
    ts_ms = int(day_index * 24 * 3600 * 1000) +123
    return {"event_type": event_type, "timestamp_ms": ts_ms, "payload": dict(payload or {})}


def test_build_daily_panel_basic_counts():
    # 10 days, treatment on days 5..9, outcomes increase by 1.
    events = []
    for d in range(10):
        if d >= 5:
            events.append(_ev(d, "pricing_change_applied"))
        # outcomes
        n = 2 if d < 5 else 3
        for _ in range(n):
            events.append(_ev(d, "payment_captured"))

    panel = build_daily_panel(
        events,
        treatment_event_types=("pricing_change_applied",),
        outcome_event_types=("payment_captured",),
        max_days=60,
    )
    assert panel.rows
    assert panel.meta.get("n_days") == 10

    est = estimate_effect_from_daily_panel(panel, method="diff_in_means")
    assert est is not None


def test_placebo_shift_runs():
    events = []
    for d in range(20):
        if d in (10, 11):
            events.append(_ev(d, "ads_apply_executed@v1"))
        # constant outcomes
        events.append(_ev(d, "payment_succeeded"))

    panel = build_daily_panel(
        events,
        treatment_event_types=("ads_apply_executed@v1",),
        outcome_event_types=("payment_succeeded",),
        max_days=60,
    )
    est = estimate_effect_from_daily_panel(panel, method="dr")
    plc = placebo_shift_treatment(panel, shift_days=1, method="dr")
    assert est is not None
    assert plc is not None


def test_guardrails_insufficient_data():
    d = assess_causal_evidence({"effect": -1.0, "ci_low": -2.0, "ci_high": -0.5, "n_days": 7}, min_n_days=14)
    assert d.ok is True
    assert d.level in {"info", "warn"}
    assert "causal_guardrail" in d.constraints
