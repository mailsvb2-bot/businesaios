from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.finance.strategic.builders.board_summary_builder import BoardSummaryBuilder
from core.finance.strategic.explainers.allocation_explainer import AllocationExplainer
from core.finance.strategic.explainers.liquidity_risk_explainer import LiquidityRiskExplainer
from core.finance.strategic.explainers.scenario_decision_explainer import ScenarioDecisionExplainer
from core.finance.strategic.services.strategic_finance_payload import min_liquidity_tail
from core.finance.strategic.services.strategic_finance_trace import build_trace_bundle
from core.finance.strategic.types import DecisionTrace, FinancialInput


@dataclass(frozen=True)
class StrategicFinanceArtifacts:
    advisory: Any
    scenario_explanation: str
    allocation_explanation: str
    liquidity_explanation: str
    board_summary: dict[str, Any]
    trace_bundle: dict[str, Any]



def build_artifacts(
    *,
    finance_input: FinancialInput,
    forecast,
    liquidity_path,
    runway_months,
    scenarios,
    advisory_policy,
    scenario_explainer: ScenarioDecisionExplainer,
    allocation_explainer: AllocationExplainer,
    liquidity_explainer: LiquidityRiskExplainer,
    board_summary_builder: BoardSummaryBuilder,
    assumption_records,
    pre_guard_codes,
) -> StrategicFinanceArtifacts:
    advisory = advisory_policy.build_advice(
        finance_input=finance_input,
        forecast=forecast,
        runway_months=runway_months,
        scenarios=scenarios,
        pre_guard_codes=tuple(pre_guard_codes),
    )
    selected = next(item for item in scenarios if item.name == advisory.selected_scenario)
    scenario_explanation = scenario_explainer.explain(
        selected,
        score=advisory.scenario_scores[selected.name],
        rationale=advisory.evidence_trail,
    )
    allocation_explanation = allocation_explainer.explain(
        advisory.channel_allocation,
        advisory.allocation_rationale,
    )
    liquidity_explanation = liquidity_explainer.explain(
        min_liquidity_tail(liquidity_path),
        min_liquidity_tail(()),
        bias=advisory.liquidity_mode,
    )
    board_summary = board_summary_builder.build(
        annual_plan={
            "revenue_head": forecast.revenue[0],
            "cost_head": forecast.costs[0],
            "cashflow_head": forecast.cashflow[0],
        },
        runway_months=runway_months,
        top_risks=sorted(advisory.rejection_reasons)[:3],
        selected_scenario=selected.name,
        decision_reason=scenario_explanation,
    )
    trace_bundle = build_trace_bundle(
        finance_input=finance_input,
        forecast_version=forecast.assumptions_version,
        advisory=advisory,
    )
    return StrategicFinanceArtifacts(
        advisory=advisory,
        scenario_explanation=scenario_explanation,
        allocation_explanation=allocation_explanation,
        liquidity_explanation=liquidity_explanation,
        board_summary=board_summary,
        trace_bundle=trace_bundle,
    )


def build_decision_trace(*, decision, finance_input: FinancialInput, objective: str) -> DecisionTrace:
    return DecisionTrace(
        decision_id=decision.forecast_version,
        objective=objective,
        selected_scenario=decision.selected_scenario,
        selected_allocation=decision.channel_allocation,
        guard_codes=decision.guard_codes,
        metadata={
            "tenant_id": finance_input.tenant_id,
            "correlation_id": finance_input.correlation_id,
            "source_snapshot_id": finance_input.metadata.get("economics_snapshot_id"),
            "advisory_only": True,
        },
    )
