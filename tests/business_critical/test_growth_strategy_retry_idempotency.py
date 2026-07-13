from __future__ import annotations

from collections.abc import Iterable

import pytest

from core.growth.strategy import service as service_module
from core.growth.strategy.contracts import GrowthHypothesisV1
from core.growth.strategy.event_types import (
    GROWTH_HYPOTHESIS_CREATED,
    GROWTH_STRATEGY_GENERATED,
)
from core.growth.strategy.service import GrowthStrategyService


class StrictDuplicateEventStore:
    """Small SQLite-like event store: duplicate primary keys raise."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def append_event(self, event: dict, *, commit: bool = True) -> None:
        event_id = str(event.get("event_id") or "")
        if any(str(item.get("event_id") or "") == event_id for item in self.events):
            raise RuntimeError("duplicate event_id")
        self.events.append(dict(event))

    def _matching(
        self,
        *,
        tenant_id: str,
        event_type: str | None = None,
        event_types: Iterable[str] | None = None,
        user_id: str | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
    ) -> list[dict]:
        types = {
            str(item)
            for item in (event_types or ())
            if str(item)
        }
        if event_type:
            types.add(str(event_type))
        rows = []
        for event in self.events:
            if str(event.get("tenant_id") or "") != str(tenant_id):
                continue
            if types and str(event.get("event_type") or "") not in types:
                continue
            if user_id is not None and str(event.get("user_id") or "") != str(user_id):
                continue
            timestamp_ms = int(event.get("timestamp_ms") or 0)
            if start_ms is not None and timestamp_ms < int(start_ms):
                continue
            if end_ms is not None and timestamp_ms >= int(end_ms):
                continue
            rows.append(dict(event))
        return sorted(rows, key=lambda item: (int(item.get("timestamp_ms") or 0), str(item.get("event_id") or "")))

    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int = 0,
        end_ms: int | None = None,
        event_type: str | None = None,
        event_types: Iterable[str] | None = None,
        user_id: str | None = None,
        limit: int | None = None,
    ):
        rows = self._matching(
            tenant_id=tenant_id,
            event_type=event_type,
            event_types=event_types,
            user_id=user_id,
            start_ms=start_ms,
            end_ms=end_ms,
        )
        return iter(rows[: int(limit)] if limit is not None else rows)

    def latest_events(
        self,
        *,
        tenant_id: str,
        user_id: str | None = None,
        event_type: str | None = None,
        event_types: Iterable[str] | None = None,
        limit: int = 100,
    ) -> list[dict]:
        rows = self._matching(
            tenant_id=tenant_id,
            event_type=event_type,
            event_types=event_types,
            user_id=user_id,
        )
        return list(reversed(rows[-int(limit) :]))

    def latest_event(self, **kwargs):
        rows = self.latest_events(limit=1, **kwargs)
        return rows[0] if rows else None

    def commit(self) -> None:
        return None


def _hypothesis(title: str) -> GrowthHypothesisV1:
    return GrowthHypothesisV1(
        title=title,
        mechanism="Проверяем одну бизнес-гипотезу",
        expected_impact="Рост прибыли",
        effort="low",
        risk="low",
        metric="profit_minor",
        horizon_days=14,
    )


@pytest.mark.lock
def test_completed_growth_decision_is_resumed_without_second_llm_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    store = StrictDuplicateEventStore()
    calls = 0

    def fake_generate(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return (_hypothesis(f"Гипотеза {calls}"),)

    monkeypatch.setattr(service_module, "generate_hypotheses", fake_generate)
    service = GrowthStrategyService(event_store=store, llm=object())

    first_plan, first_proof = service.generate_backlog_with_proof(
        tenant_id="business-a",
        user_id="owner-1",
        decision_id="decision-growth-1",
        correlation_id="correlation-growth-1",
    )
    second_plan, second_proof = service.generate_backlog_with_proof(
        tenant_id="business-a",
        user_id="owner-1",
        decision_id="decision-growth-1",
        correlation_id="correlation-growth-1",
    )

    assert calls == 1
    assert first_proof == second_proof
    assert first_plan.top_hypotheses == second_plan.top_hypotheses
    assert first_plan.top_hypotheses[0].title == "Гипотеза 1"
    assert len({str(event["event_id"]) for event in store.events}) == len(store.events)
    assert sum(event["event_type"] == GROWTH_STRATEGY_GENERATED for event in store.events) == 1


@pytest.mark.lock
def test_partial_growth_write_resumes_original_durable_hypothesis_without_duplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    store = StrictDuplicateEventStore()
    generation_calls = 0
    completion_calls = 0
    real_append_completion = service_module.append_strategy_generated

    def fake_generate(*_args, **_kwargs):
        nonlocal generation_calls
        generation_calls += 1
        title = "Первоначальная гипотеза" if generation_calls == 1 else "Другая гипотеза на retry"
        return (_hypothesis(title),)

    def fail_completion_once(*args, **kwargs):
        nonlocal completion_calls
        completion_calls += 1
        if completion_calls == 1:
            raise RuntimeError("simulated crash before completion proof")
        return real_append_completion(*args, **kwargs)

    monkeypatch.setattr(service_module, "generate_hypotheses", fake_generate)
    monkeypatch.setattr(service_module, "append_strategy_generated", fail_completion_once)
    service = GrowthStrategyService(event_store=store, llm=object())

    with pytest.raises(RuntimeError, match="simulated crash"):
        service.generate_backlog_with_proof(
            tenant_id="business-a",
            user_id="owner-1",
            decision_id="decision-growth-partial",
            correlation_id="correlation-growth-partial",
        )

    assert sum(event["event_type"] == GROWTH_HYPOTHESIS_CREATED for event in store.events) == 1
    assert sum(event["event_type"] == GROWTH_STRATEGY_GENERATED for event in store.events) == 0

    plan, completion_event_id = service.generate_backlog_with_proof(
        tenant_id="business-a",
        user_id="owner-1",
        decision_id="decision-growth-partial",
        correlation_id="correlation-growth-partial",
    )

    assert generation_calls == 2
    assert completion_event_id
    assert plan.top_hypotheses[0].title == "Первоначальная гипотеза"
    assert sum(event["event_type"] == GROWTH_HYPOTHESIS_CREATED for event in store.events) == 1
    assert sum(event["event_type"] == GROWTH_STRATEGY_GENERATED for event in store.events) == 1
    assert len({str(event["event_id"]) for event in store.events}) == len(store.events)
