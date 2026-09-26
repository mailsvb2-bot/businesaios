from __future__ import annotations

from application.business_goal import BusinessGoalRegistry
from application.headless.models import GoalExecutionRequest
from execution.headless_boot import build_headless_runtime
from reliability.idempotency_store import InMemoryIdempotencyStore


def test_goal_bound_headless_closed_loop_uses_v2_and_preserves_goal_lineage(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    build_headless_runtime.cache_clear()
    runtime = build_headless_runtime(entrypoint="headless_sdk", root_dir=tmp_path)

    BusinessGoalRegistry(
        event_store=runtime.contract._event_store,
        idempotency_store=InMemoryIdempotencyStore(),
    ).create(
        tenant_id="tenant-phase6",
        business_id="business-phase6",
        goal_id="goal-profit",
        idempotency_key="goal-profit-create",
        goal_kind="profitability",
        metric="profit",
        baseline=100.0,
        target=120.0,
        deadline_at_ms=5000,
        priority=90,
        occurred_at_ms=1000,
    )

    report = runtime.contract.execute_once(
        GoalExecutionRequest(
            goal="increase profit",
            goal_id="goal-profit",
            tenant_id="tenant-phase6",
            business_id="business-phase6",
            max_steps=1,
        )
    )

    assert report.goal_id == "goal-profit"
    assert len(report.steps) == 1
    step = report.steps[0]
    intent = dict(step.feedback.get("action_intent") or {})
    outcome = dict(step.feedback.get("business_outcome") or {})
    assert intent["schema_version"] == 2
    assert intent["goal_id"] == "goal-profit"
    assert intent["business_id"] == "business-phase6"
    assert intent["requested_autonomy"] == "supervised"
    assert intent["deadline"] == 5000
    assert intent["decision_id"] == step.decision_id
    assert outcome["decision_id"] == step.decision_id
    assert outcome["intent_id"] == intent["intent_id"]

    records = runtime.evidence_store.list_for_tenant(tenant_id="tenant-phase6")
    closed_loop = [row for row in records if row.scope == "closed_loop"]
    assert closed_loop
    assert any(
        row.labels.get("goal_id") == "goal-profit"
        and dict(row.payload.get("action_intent") or {}).get("schema_version") == 2
        for row in closed_loop
    )

    events = list(
        runtime.contract._event_store.iter_events(
            tenant_id="tenant-phase6",
            start_ms=0,
        )
    )
    decisions = [
        event for event in events if event.get("event_type") == "decision.proposed"
    ]
    outcomes = [
        event for event in events if event.get("event_type") == "outcome.observed"
    ]
    assert decisions
    assert outcomes
    assert decisions[-1]["payload"]["decision"]["goal_id"] == "goal-profit"
    assert outcomes[-1]["payload"]["goal_id"] == "goal-profit"
