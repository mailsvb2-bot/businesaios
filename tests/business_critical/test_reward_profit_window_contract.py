from __future__ import annotations

import time

import pytest

from core.ads.rl.reward import RewardComputer, RewardWindow
from core.events.event_types import (
    ADS_ATTRIBUTION_MATURITY_SNAPSHOT,
    PURCHASE_SUCCESS,
)
from core.governance.evaluators.profit_metrics import (
    ProfitMetricsService,
    _to_utc_dt,
)

DAY_MS = 24 * 60 * 60 * 1000


class FakeStore:
    def __init__(self, events: list[dict]) -> None:
        self.events = list(events)

    def latest_events(
        self,
        *,
        tenant_id: str,
        event_types=None,
        event_type=None,
        limit: int = 20000,
    ) -> list[dict]:
        allowed = {
            str(value)
            for value in tuple(event_types or ())
            if str(value)
        }
        if event_type:
            allowed.add(str(event_type))
        rows = [
            dict(event)
            for event in self.events
            if str(event.get("tenant_id") or "") == str(tenant_id)
            and (
                not allowed
                or str(event.get("event_type") or "") in allowed
            )
        ]
        return rows[: int(limit)]


def _event(
    *,
    event_type: str,
    timestamp_ms: int | str,
    payload: dict,
    decision_id: str = "",
) -> dict:
    return {
        "tenant_id": "business-a",
        "event_type": event_type,
        "timestamp_ms": timestamp_ms,
        "decision_id": decision_id,
        "payload": dict(payload),
    }


@pytest.mark.lock
def test_epoch_milliseconds_are_not_treated_as_seconds() -> None:
    now_ms = int(time.time() * 1000)

    parsed_int = _to_utc_dt(now_ms)
    parsed_string = _to_utc_dt(str(now_ms))

    assert parsed_int is not None
    assert parsed_string is not None
    assert abs(int(parsed_int.timestamp() * 1000) - now_ms) <= 1
    assert abs(int(parsed_string.timestamp() * 1000) - now_ms) <= 1


@pytest.mark.lock
def test_reward_uses_disjoint_profit_windows_around_executed_decision() -> None:
    now_ms = int(time.time() * 1000)
    anchor_ms = now_ms - 4 * DAY_MS
    post_end_ms = anchor_ms + 3 * DAY_MS
    events = [
        _event(
            event_type=ADS_ATTRIBUTION_MATURITY_SNAPSHOT,
            timestamp_ms=str(anchor_ms),
            decision_id="ads-decision-1",
            payload={
                "decision_id": "ads-decision-1",
                "created_ms": str(anchor_ms),
                "mature_after_ms": anchor_ms + DAY_MS,
            },
        ),
        _event(
            event_type=PURCHASE_SUCCESS,
            timestamp_ms=str(anchor_ms - 2 * DAY_MS),
            payload={"amount": 100},
        ),
        _event(
            event_type="ads_metrics_imported",
            timestamp_ms=anchor_ms - DAY_MS,
            payload={"metrics": {"spend": 10}},
        ),
        _event(
            event_type=PURCHASE_SUCCESS,
            timestamp_ms=anchor_ms + DAY_MS,
            payload={"amount": 130},
        ),
        _event(
            event_type="ads_metrics_imported",
            timestamp_ms=anchor_ms + 2 * DAY_MS,
            payload={"metrics": {"spend": 20}},
        ),
        # End is exclusive: this future-window event must not affect reward.
        _event(
            event_type=PURCHASE_SUCCESS,
            timestamp_ms=post_end_ms,
            payload={"amount": 999},
        ),
    ]
    metrics = ProfitMetricsService(event_store=FakeStore(events))

    transition = RewardComputer(
        profit_metrics=metrics,
        window=RewardWindow(pre_days=3, post_days=3),
    ).transition_for_decision(
        tenant_id="business-a",
        decision_id="ads-decision-1",
        lookback_days=14,
    )

    assert transition is not None
    assert transition.reward_minor == 2_000
    assert transition.state == {
        "revenue_minor": 13_000,
        "ads_spend_minor": 2_000,
        "profit_minor": 11_000,
        "lookback_days": 14,
    }
    assert transition.meta["reward_pre_minor"] == 9_000
    assert transition.meta["reward_post_minor"] == 11_000
    assert transition.meta["reward_anchor_ms"] == anchor_ms
    assert transition.meta["reward_pre_start_ms"] == anchor_ms - 3 * DAY_MS
    assert transition.meta["reward_post_end_ms"] == post_end_ms
    assert transition.meta["reward_source"] == "canonical_profit_windows"


@pytest.mark.lock
def test_reward_fails_closed_until_post_window_is_complete() -> None:
    now_ms = int(time.time() * 1000)
    anchor_ms = now_ms - DAY_MS
    store = FakeStore(
        [
            _event(
                event_type=ADS_ATTRIBUTION_MATURITY_SNAPSHOT,
                timestamp_ms=anchor_ms,
                decision_id="ads-decision-immature",
                payload={
                    "decision_id": "ads-decision-immature",
                    "created_ms": anchor_ms,
                    "mature_after_ms": anchor_ms + DAY_MS,
                },
            )
        ]
    )

    transition = RewardComputer(
        profit_metrics=ProfitMetricsService(event_store=store),
        window=RewardWindow(pre_days=3, post_days=3),
    ).transition_for_decision(
        tenant_id="business-a",
        decision_id="ads-decision-immature",
        lookback_days=14,
    )

    assert transition is None
