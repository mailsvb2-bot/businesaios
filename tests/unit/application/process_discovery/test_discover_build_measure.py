from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from application.process_discovery import (
    AutonomyStage,
    BuildRequest,
    ComparisonDesign,
    ComparisonEvidence,
    DiscoverBuildMeasureService,
    DiscoveryPolicy,
    EvidenceGrade,
    InterventionProof,
    InterventionSpend,
    MoneyStatus,
    ProcessObservation,
    decisioncore_advisory_payload,
)

BASE = datetime(2026, 8, 1, tzinfo=UTC)


def observation(
    *,
    day: int,
    process: str = "lead_followup",
    manual_minutes: int = 30,
    direct_loss_minor: int | None = 0,
    actor_cost_per_hour_minor: int | None = 60_000,
    currency: str | None = "RUB",
    automation_fit: float = 0.9,
    risk: float = 0.2,
    source: str = "crm",
    revenue_at_risk_minor: int | None = 0,
    evidence_id: str | None = None,
    tenant_id: str = "tenant-1",
) -> ProcessObservation:
    return ProcessObservation(
        tenant_id=tenant_id,
        business_id="business-1",
        process_key=process,
        occurred_at=BASE + timedelta(days=day),
        source=source,
        evidence_id=evidence_id or f"ev-{process}-{day}",
        manual_minutes=manual_minutes,
        actor_cost_per_hour_minor=actor_cost_per_hour_minor,
        direct_loss_minor=direct_loss_minor,
        revenue_at_risk_minor=revenue_at_risk_minor,
        currency=currency,
        automation_fit=automation_fit,
        operational_risk=risk,
    )


def policy() -> DiscoveryPolicy:
    return DiscoveryPolicy(
        min_observations=5,
        min_window_days=5,
        min_confidence=0.25,
        min_manual_minutes_per_30d=60,
        min_realized_loss_minor_per_30d=1,
        min_automation_fit=0.5,
        max_operational_risk=0.8,
        reference_observations=8,
        reference_window_days=7,
    )


def service() -> DiscoverBuildMeasureService:
    return DiscoverBuildMeasureService(policy())


def discovered():
    return service().discover([observation(day=index) for index in range(8)]).opportunities[0]


def proof(blueprint, *, day: int = 12) -> InterventionProof:
    return InterventionProof(
        tenant_id=blueprint.tenant_id,
        business_id=blueprint.business_id,
        blueprint_id=blueprint.blueprint_id,
        intervention_id="intervention-1",
        started_at=BASE + timedelta(days=day),
        server_validated=True,
        execution_verified=True,
        run_id="run-1",
        decision_id="decision-1",
        action_id="action-1",
        evidence_refs=("execution-proof-1",),
    )


def test_discover_finds_material_process_without_inventing_money() -> None:
    opportunity = discovered()
    assert opportunity.eligible is True
    assert opportunity.baseline.money_status is MoneyStatus.VERIFIED
    assert opportunity.baseline.realized_loss_minor_per_30d is not None
    assert opportunity.baseline.evidence_fingerprint


def test_duplicate_evidence_is_not_counted_twice() -> None:
    items = [observation(day=index) for index in range(8)]
    items.extend([items[0], items[1], items[1]])
    opportunity = service().discover(items).opportunities[0]
    assert opportunity.baseline.observation_count == 8
    assert len(opportunity.baseline.evidence_refs) == 8


def test_conflicting_duplicate_evidence_id_fails_closed() -> None:
    first = observation(day=0, evidence_id="same")
    conflicting = observation(day=1, evidence_id="same", manual_minutes=999)
    with pytest.raises(ValueError, match="conflicting"):
        service().discover([first, conflicting])


def test_discover_never_aggregates_mixed_currencies() -> None:
    observations = [observation(day=index, currency="RUB" if index % 2 == 0 else "USD") for index in range(8)]
    opportunity = service().discover(observations).opportunities[0]
    assert opportunity.baseline.money_status is MoneyStatus.MIXED_CURRENCY
    assert opportunity.baseline.realized_loss_minor_per_30d is None
    assert opportunity.baseline.currency is None


def test_discover_does_not_treat_revenue_at_risk_as_realized_loss() -> None:
    observations = [
        observation(day=index, manual_minutes=0, actor_cost_per_hour_minor=0, direct_loss_minor=0, revenue_at_risk_minor=1_000_000)
        for index in range(8)
    ]
    candidate = service().discover(observations).rejected_processes[0]
    assert candidate.baseline.realized_loss_minor_per_30d == 0
    assert candidate.baseline.revenue_at_risk_minor_per_30d is not None
    assert candidate.eligible is False


def test_partial_money_is_not_promoted_to_verified_total() -> None:
    observations = [observation(day=index) for index in range(8)]
    observations[3] = observation(day=3, actor_cost_per_hour_minor=None)
    candidate = service().discover(observations).opportunities[0]
    assert candidate.baseline.money_status is MoneyStatus.PARTIAL
    assert candidate.baseline.realized_loss_minor_per_30d is None


def test_build_is_observe_first_non_executable_and_stops_default_promotion_at_approval() -> None:
    opportunity = discovered()
    blueprint = service().build(
        opportunity,
        BuildRequest(
            owner_goal="Снизить время ручного follow-up",
            requested_capabilities=("communications_draft", "crm_read"),
            expected_coverage=0.7,
            setup_cost_minor=30_000,
            currency="RUB",
        ),
    )
    assert blueprint.initial_stage is AutonomyStage.OBSERVE
    assert blueprint.executable is False
    assert blueprint.promotion_path[-1] is AutonomyStage.APPROVAL
    assert AutonomyStage.SUPERVISED not in blueprint.promotion_path
    assert AutonomyStage.AUTONOMOUS not in blueprint.promotion_path


def test_blueprint_identity_binds_cost_metrics_and_frozen_baseline() -> None:
    opportunity = discovered()
    first = service().build(
        opportunity,
        BuildRequest(owner_goal="Goal", setup_cost_minor=100, currency="RUB", success_metrics=("m1",)),
    )
    second = service().build(
        opportunity,
        BuildRequest(owner_goal="Goal", setup_cost_minor=999_999, currency="RUB", success_metrics=("m2",)),
    )
    assert first.blueprint_id != second.blueprint_id
    assert first.baseline_fingerprint == opportunity.baseline.evidence_fingerprint


def test_corrected_evidence_changes_opportunity_identity() -> None:
    original = [observation(day=index) for index in range(8)]
    corrected = [observation(day=index) for index in range(8)]
    corrected[4] = observation(day=4, manual_minutes=99)
    first = service().discover(original).opportunities[0]
    second = service().discover(corrected).opportunities[0]
    assert first.baseline.window_start == second.baseline.window_start
    assert first.baseline.window_end == second.baseline.window_end
    assert first.opportunity_id != second.opportunity_id


def test_decisioncore_projection_is_advisory_and_objective_is_string() -> None:
    blueprint = service().build(discovered(), BuildRequest(owner_goal="Снизить ручной follow-up"))
    payload = decisioncore_advisory_payload(blueprint)
    assert payload["objective"] == "Снизить ручной follow-up"
    assert isinstance(payload["objective"], str)
    assert payload["metadata"]["executable"] is False
    assert "action" not in payload


def test_measure_requires_verified_intervention_and_post_intervention_evidence() -> None:
    before = [observation(day=index, manual_minutes=60, direct_loss_minor=10_000) for index in range(8)]
    opportunity = service().discover(before).opportunities[0]
    blueprint = service().build(opportunity, BuildRequest(owner_goal="Автоматизировать follow-up"))
    after = [observation(day=20 + index, manual_minutes=10, direct_loss_minor=1_000) for index in range(8)]
    report = service().measure(
        blueprint=blueprint,
        baseline=opportunity.baseline,
        intervention=proof(blueprint),
        after_observations=after,
        spend=InterventionSpend(ai_runtime_cost_minor=8_000, currency="RUB"),
    )
    assert report.manual_minutes_saved_per_30d > 0
    assert report.intervention_id == "intervention-1"
    assert report.causal_claim_allowed is False


def test_after_evidence_predating_intervention_is_rejected() -> None:
    opportunity = discovered()
    blueprint = service().build(opportunity, BuildRequest(owner_goal="Automate"))
    after = [observation(day=8 + index) for index in range(8)]
    with pytest.raises(ValueError, match="after the verified intervention"):
        service().measure(
            blueprint=blueprint,
            baseline=opportunity.baseline,
            intervention=proof(blueprint, day=12),
            after_observations=after,
            spend=InterventionSpend(ai_runtime_cost_minor=1_000, currency="RUB"),
        )


def test_foreign_baseline_tenant_is_rejected() -> None:
    opportunity = discovered()
    blueprint = service().build(opportunity, BuildRequest(owner_goal="Automate"))
    foreign_baseline = replace(opportunity.baseline, tenant_id="foreign")
    after = [observation(day=20 + index) for index in range(8)]
    with pytest.raises(ValueError, match="tenant"):
        service().measure(
            blueprint=blueprint,
            baseline=foreign_baseline,
            intervention=proof(blueprint),
            after_observations=after,
            spend=InterventionSpend(ai_runtime_cost_minor=1_000, currency="RUB"),
        )


def test_tampered_executable_blueprint_is_rejected_not_masked() -> None:
    opportunity = discovered()
    blueprint = replace(service().build(opportunity, BuildRequest(owner_goal="Automate")), executable=True)
    with pytest.raises(ValueError, match="integrity"):
        service().measure(
            blueprint=blueprint,
            baseline=opportunity.baseline,
            intervention=proof(blueprint),
            after_observations=[observation(day=20 + index) for index in range(8)],
            spend=InterventionSpend(ai_runtime_cost_minor=1_000, currency="RUB"),
        )


def test_controlled_evidence_does_not_let_this_module_claim_causality() -> None:
    opportunity = discovered()
    blueprint = service().build(opportunity, BuildRequest(owner_goal="Automate"))
    report = service().measure(
        blueprint=blueprint,
        baseline=opportunity.baseline,
        intervention=proof(blueprint),
        after_observations=[observation(day=20 + index, manual_minutes=5) for index in range(8)],
        spend=InterventionSpend(ai_runtime_cost_minor=1_000, currency="RUB"),
        comparison=ComparisonEvidence(
            design=ComparisonDesign.RANDOMIZED,
            validated_server_side=True,
            control_observation_count=8,
            control_window_days=8,
            evidence_refs=("experiment-proof-1",),
        ),
    )
    assert report.evidence_grade is EvidenceGrade.CONTROLLED
    assert report.causal_claim_allowed is False
    assert "canonical_experiment_estimator" in " ".join(report.caveats)
