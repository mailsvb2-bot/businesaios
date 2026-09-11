from __future__ import annotations

from collections.abc import Sequence

from .contracts import (
    AgentBlueprint,
    ComparisonDesign,
    ComparisonEvidence,
    DiscoveryPolicy,
    EvidenceGrade,
    InterventionProof,
    InterventionSpend,
    MoneyStatus,
    ProcessBaseline,
    ProcessObservation,
    ROIReport,
)
from .discovery import aggregate_baseline


def _ratio_delta(before: int, after: int) -> float | None:
    if before <= 0:
        return None
    return round((before - after) / before, 4)


def _grade(*, baseline: ProcessBaseline, after: ProcessBaseline, comparison: ComparisonEvidence, policy: DiscoveryPolicy) -> EvidenceGrade:
    enough = (
        baseline.observation_count >= policy.min_observations
        and after.observation_count >= policy.min_observations
        and baseline.window_days >= policy.min_window_days
        and after.window_days >= policy.min_window_days
    )
    if not enough:
        return EvidenceGrade.INSUFFICIENT
    controlled_design = comparison.design in {
        ComparisonDesign.MATCHED_CONTROL,
        ComparisonDesign.HOLDOUT,
        ComparisonDesign.RANDOMIZED,
    }
    controlled_evidence = (
        controlled_design
        and comparison.validated_server_side
        and comparison.control_observation_count >= policy.min_observations
        and comparison.control_window_days >= policy.min_window_days
        and bool(comparison.evidence_refs)
    )
    if controlled_evidence:
        return EvidenceGrade.CONTROLLED
    if baseline.confidence >= 0.65 and after.confidence >= 0.65:
        return EvidenceGrade.MEASURED
    return EvidenceGrade.DIRECTIONAL


def _intervention_cost_30d(spend: InterventionSpend, after: ProcessBaseline) -> int | None:
    if not spend.currency or spend.ai_runtime_cost_minor is None:
        return None
    components = [round(spend.ai_runtime_cost_minor * 30 / max(1, after.window_days))]
    if spend.human_review_minutes:
        if spend.reviewer_cost_per_hour_minor is None:
            return None
        review_cost = round(spend.human_review_minutes * spend.reviewer_cost_per_hour_minor / 60)
        components.append(round(review_cost * 30 / max(1, after.window_days)))
    if spend.setup_cost_minor is not None:
        components.append(round(spend.setup_cost_minor * 30 / spend.setup_amortization_days))
    return sum(components)


def _validate_proof(*, blueprint: AgentBlueprint, baseline: ProcessBaseline, proof: InterventionProof) -> None:
    if blueprint.executable:
        raise ValueError("executable blueprint is an integrity violation")
    if baseline.tenant_id != blueprint.tenant_id:
        raise ValueError("blueprint and baseline cross tenant boundary")
    if baseline.business_id != blueprint.business_id or baseline.process_key != blueprint.process_key:
        raise ValueError("blueprint and baseline must refer to the same business/process")
    if not baseline.evidence_fingerprint or baseline.evidence_fingerprint != blueprint.baseline_fingerprint:
        raise ValueError("blueprint baseline fingerprint mismatch")
    if proof.tenant_id != blueprint.tenant_id or proof.business_id != blueprint.business_id:
        raise ValueError("intervention proof scope mismatch")
    if proof.blueprint_id != blueprint.blueprint_id:
        raise ValueError("intervention proof blueprint mismatch")
    if not proof.server_validated or not proof.execution_verified or not proof.evidence_refs:
        raise ValueError("server-validated executed intervention proof is required")
    if proof.started_at <= baseline.window_end:
        raise ValueError("intervention must start after the frozen baseline window")


def measure_outcome(
    *,
    blueprint: AgentBlueprint,
    baseline: ProcessBaseline,
    intervention: InterventionProof,
    after_observations: Sequence[ProcessObservation],
    spend: InterventionSpend,
    comparison: ComparisonEvidence | None = None,
    policy: DiscoveryPolicy | None = None,
) -> ROIReport:
    resolved_policy = policy or DiscoveryPolicy()
    comparison_evidence = comparison or ComparisonEvidence()
    _validate_proof(blueprint=blueprint, baseline=baseline, proof=intervention)
    if not after_observations:
        raise ValueError("after_observations are required")
    if any(item.tenant_id != blueprint.tenant_id for item in after_observations):
        raise ValueError("after observations cross tenant boundary")
    if any(item.business_id != blueprint.business_id for item in after_observations):
        raise ValueError("after observations cross business boundary")
    if any(item.process_key != blueprint.process_key for item in after_observations):
        raise ValueError("after observations cross process boundary")
    if any(item.occurred_at < intervention.started_at for item in after_observations):
        raise ValueError("after observations must occur after the verified intervention start")

    after = aggregate_baseline(after_observations, resolved_policy)
    grade = _grade(baseline=baseline, after=after, comparison=comparison_evidence, policy=resolved_policy)
    time_saved = baseline.manual_minutes_per_30d - after.manual_minutes_per_30d
    time_ratio = _ratio_delta(baseline.manual_minutes_per_30d, after.manual_minutes_per_30d)

    caveats: list[str] = []
    currency: str | None = None
    gross_savings: int | None = None
    intervention_cost: int | None = None
    net_benefit: int | None = None
    roi_ratio: float | None = None
    comparable_money = (
        baseline.money_status is MoneyStatus.VERIFIED
        and after.money_status is MoneyStatus.VERIFIED
        and baseline.currency is not None
        and baseline.currency == after.currency
        and spend.currency == baseline.currency
    )
    if comparable_money:
        currency = baseline.currency
        assert baseline.realized_loss_minor_per_30d is not None
        assert after.realized_loss_minor_per_30d is not None
        gross_savings = baseline.realized_loss_minor_per_30d - after.realized_loss_minor_per_30d
        intervention_cost = _intervention_cost_30d(spend, after)
        if intervention_cost is not None:
            net_benefit = gross_savings - intervention_cost
            if intervention_cost > 0:
                roi_ratio = round(net_benefit / intervention_cost, 4)
            elif net_benefit > 0:
                caveats.append("positive_benefit_with_zero_measured_intervention_cost")
        else:
            caveats.append("intervention_cost_incomplete")
    else:
        caveats.append("money_not_comparable_or_not_fully_verified")

    # This module can label server-validated controlled evidence but it is not a
    # statistical causal-inference owner. A future canonical Experimentation
    # estimator may issue a causal verdict; this module never fabricates one.
    causal_claim_allowed = False
    if grade is EvidenceGrade.CONTROLLED:
        caveats.append("controlled_evidence_present_but_causal_inference_requires_canonical_experiment_estimator")
    else:
        caveats.append("before_after_change_is_not_automatic_causal_proof")
    if grade is EvidenceGrade.INSUFFICIENT:
        caveats.append("measurement_window_or_sample_too_small")
    if after.revenue_at_risk_minor_per_30d is not None:
        caveats.append("revenue_at_risk_is_reported_separately_and_not_counted_as_realized_savings")

    return ROIReport(
        blueprint_id=blueprint.blueprint_id,
        intervention_id=intervention.intervention_id,
        process_key=baseline.process_key,
        design=comparison_evidence.design,
        evidence_grade=grade,
        baseline=baseline,
        after=after,
        manual_minutes_saved_per_30d=time_saved,
        manual_time_improvement_ratio=time_ratio,
        gross_savings_minor_per_30d=gross_savings,
        intervention_cost_minor_per_30d=intervention_cost,
        net_benefit_minor_per_30d=net_benefit,
        roi_ratio=roi_ratio,
        currency=currency,
        causal_claim_allowed=causal_claim_allowed,
        caveats=tuple(dict.fromkeys(caveats)),
        metadata={
            "source": "discover_build_measure",
            "blueprint_executable": False,
            "decision_owner": "DecisionCore",
            "baseline_fingerprint": baseline.evidence_fingerprint,
            "intervention_server_validated": True,
            "intervention_evidence_refs": tuple(intervention.evidence_refs),
            "comparison_evidence_server_validated": comparison_evidence.validated_server_side,
            "comparison_evidence_refs": tuple(comparison_evidence.evidence_refs),
        },
    )
