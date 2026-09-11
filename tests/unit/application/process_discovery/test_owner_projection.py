from __future__ import annotations

from datetime import UTC, datetime, timedelta

from application.process_discovery import (
    BuildRequest,
    DiscoverBuildMeasureService,
    DiscoveryPolicy,
    InterventionProof,
    InterventionSpend,
    ProcessObservation,
    blueprint_card,
    opportunity_card,
    roi_card,
)


def observations(*, start_day: int, manual_minutes: int) -> list[ProcessObservation]:
    return [
        ProcessObservation(
            tenant_id="t1",
            business_id="b1",
            process_key="weekly_report",
            occurred_at=datetime(2026, 8, 1, tzinfo=UTC) + timedelta(days=start_day + index),
            source="task_history",
            evidence_id=f"report-{start_day}-{index}",
            manual_minutes=manual_minutes,
            actor_cost_per_hour_minor=50_000,
            direct_loss_minor=0,
            revenue_at_risk_minor=0,
            currency="RUB",
            automation_fit=0.95,
            operational_risk=0.05,
        )
        for index in range(6)
    ]


def test_owner_cards_keep_money_as_minor_units_and_expose_safety_state() -> None:
    service = DiscoverBuildMeasureService(
        DiscoveryPolicy(min_observations=5, min_window_days=5, min_confidence=0.2)
    )
    opportunity = service.discover(observations(start_day=0, manual_minutes=90)).opportunities[0]
    blueprint = service.build(opportunity, BuildRequest(owner_goal="Ускорить еженедельный отчёт"))
    result = service.measure(
        blueprint=blueprint,
        baseline=opportunity.baseline,
        intervention=InterventionProof(
            tenant_id="t1", business_id="b1", blueprint_id=blueprint.blueprint_id,
            intervention_id="int-report", started_at=datetime(2026, 8, 15, tzinfo=UTC),
            server_validated=True, execution_verified=True, evidence_refs=("exec-report",),
        ),
        after_observations=observations(start_day=20, manual_minutes=15),
        spend=InterventionSpend(ai_runtime_cost_minor=2_000, currency="RUB"),
    )

    opportunity_payload = opportunity_card(opportunity)
    blueprint_payload = blueprint_card(blueprint)
    roi_payload = roi_card(result)

    assert opportunity_payload["realized_loss_per_30d"]["currency"] == "RUB"
    assert isinstance(opportunity_payload["realized_loss_per_30d"]["amount_minor"], int)
    assert blueprint_payload["executable"] is False
    assert blueprint_payload["initial_stage"] == "observe"
    assert roi_payload["causal_claim_allowed"] is False
