from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from .contracts import AgentBlueprint, AutomationOpportunity, AutonomyStage, BuildRequest

# Promotion stops at the existing approval boundary. Anything beyond approval is
# a DecisionCore/policy decision and must not be promised by a blueprint template.
DEFAULT_PROMOTION_PATH = (
    AutonomyStage.OBSERVE,
    AutonomyStage.RECOMMEND,
    AutonomyStage.DRAFT,
    AutonomyStage.APPROVAL,
)

DEFAULT_FORBIDDEN_SIDE_EFFECTS = (
    "external_write_without_canonical_approval",
    "budget_change_without_canonical_approval",
    "payment_without_canonical_approval",
    "credential_change",
    "policy_mutation",
    "direct_provider_execution",
)


def _blueprint_id(opportunity: AutomationOpportunity, request: BuildRequest, success_metrics: tuple[str, ...]) -> str:
    payload = {
        "opportunity_id": opportunity.opportunity_id,
        "baseline_fingerprint": opportunity.baseline.evidence_fingerprint,
        "owner_goal": request.owner_goal.strip(),
        "requested_capabilities": sorted({str(value).strip() for value in request.requested_capabilities if str(value).strip()}),
        "expected_coverage": round(float(request.expected_coverage), 6),
        "setup_cost_minor": request.setup_cost_minor,
        "currency": request.currency,
        "success_metrics": list(success_metrics),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"bp_{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:20]}"


def build_blueprint(
    opportunity: AutomationOpportunity,
    request: BuildRequest,
    *,
    built_at: datetime | None = None,
) -> AgentBlueprint:
    if not opportunity.eligible:
        raise ValueError("cannot build from an ineligible opportunity")
    baseline = opportunity.baseline
    if not baseline.evidence_fingerprint:
        raise ValueError("baseline fingerprint is required")
    if request.setup_cost_minor is not None and baseline.currency and request.currency != baseline.currency:
        raise ValueError("setup cost currency must match the opportunity currency")

    success_metrics = tuple(request.success_metrics) or (
        "manual_minutes_per_30d",
        "verified_realized_loss_minor_per_30d",
        "human_review_minutes",
        "intervention_cost_minor_per_30d",
        "net_benefit_minor_per_30d",
    )
    resolved_built_at = built_at or datetime.now(UTC)
    if resolved_built_at.tzinfo is None:
        raise ValueError("built_at must be timezone-aware")
    requested = tuple(sorted({str(value).strip() for value in request.requested_capabilities if str(value).strip()}))
    return AgentBlueprint(
        blueprint_id=_blueprint_id(opportunity, request, success_metrics),
        tenant_id=baseline.tenant_id,
        business_id=baseline.business_id,
        process_key=baseline.process_key,
        opportunity_id=opportunity.opportunity_id,
        baseline_fingerprint=baseline.evidence_fingerprint,
        built_at=resolved_built_at,
        owner_goal=request.owner_goal.strip(),
        initial_stage=AutonomyStage.OBSERVE,
        promotion_path=DEFAULT_PROMOTION_PATH,
        requested_capabilities=requested,
        forbidden_side_effects=DEFAULT_FORBIDDEN_SIDE_EFFECTS,
        expected_coverage=float(request.expected_coverage),
        setup_cost_minor=request.setup_cost_minor,
        currency=request.currency or baseline.currency,
        success_metrics=success_metrics,
        rollback_conditions=(
            "policy_guard_blocks_required_action",
            "operational_risk_exceeds_discovery_baseline",
            "verified_net_benefit_turns_negative_after_measurement",
            "human_review_load_exceeds_saved_manual_time",
            "evidence_integrity_degrades",
        ),
        executable=False,
        metadata={
            "source": "discover_build_measure",
            "priority_score": opportunity.priority_score,
            "baseline_confidence": baseline.confidence,
            "baseline_money_status": baseline.money_status.value,
            "decision_owner": "DecisionCore",
            "execution_authority": "existing_canonical_action_center_only",
            "browser_authority": False,
            "second_brain": False,
        },
    )


def decisioncore_advisory_payload(blueprint: AgentBlueprint) -> dict[str, object]:
    if blueprint.executable:
        raise ValueError("executable blueprint cannot be projected into advisory DecisionCore input")
    return {
        "business_id": blueprint.business_id,
        "objective": blueprint.owner_goal,
        "metadata": {
            "source": "discover_build_measure",
            "blueprint_id": blueprint.blueprint_id,
            "opportunity_id": blueprint.opportunity_id,
            "baseline_fingerprint": blueprint.baseline_fingerprint,
            "process_key": blueprint.process_key,
            "requested_stage": blueprint.initial_stage.value,
            "executable": False,
            "owner_workspace": True,
        },
    }
