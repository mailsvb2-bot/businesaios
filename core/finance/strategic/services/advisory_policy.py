from __future__ import annotations

from decimal import Decimal

from config.strategic_finance_advisory_policy import (
    DEFAULT_STRATEGIC_FINANCE_ADVISORY_POLICY,
    StrategicFinanceAdvisoryPolicyDefaults,
)
from core.finance.strategic.allocation.allocation_constraints import AllocationConstraints
from core.finance.strategic.allocation.channel_allocator import ChannelAllocator
from core.finance.strategic.builders.blended_vs_segmented_cac_builder import BlendedVsSegmentedCACBuilder
from core.finance.strategic.builders.cohort_ltv_builder import CohortLTVBuilder
from core.finance.strategic.decimal_utils import q2
from core.finance.strategic.guards.runway_floor_guard import RunwayFloorGuard
from core.finance.strategic.scenarios.downside_tree import DownsideTreeEvaluator
from core.finance.strategic.scenarios.scenario_comparator import ScenarioComparator
from core.finance.strategic.scenarios.scenario_dimensions import EnterpriseScenarioInputs
from core.finance.strategic.scenarios.scenario_feasibility_checker import ScenarioFeasibilityChecker
from core.finance.strategic.scenarios.scenario_ranker import ScenarioRanker
from core.finance.strategic.types import FinancialInput, ForecastSnapshot, Scenario
from core.finance.strategic.services.advisory_policy_types import StrategicFinanceAdvice



class StrategicFinanceAdvisoryPolicy:
    """Domain-local advisory policy.

    This is intentionally *not* a second platform DecisionCore. It ranks
    finance scenarios and allocation suggestions inside the strategic-finance
    bounded context, then returns an advisory payload for the host
    core.ai.decision_core to incorporate into the single platform decision.
    """

    def __init__(self, policy: StrategicFinanceAdvisoryPolicyDefaults = DEFAULT_STRATEGIC_FINANCE_ADVISORY_POLICY) -> None:
        self._policy = policy
        self._feasibility = ScenarioFeasibilityChecker()
        self._ltv_builder = CohortLTVBuilder()
        self._cac_builder = BlendedVsSegmentedCACBuilder()
        self._channel_allocator = ChannelAllocator()
        self._constraints = AllocationConstraints(
            min_cash_buffer=self._policy.zero_cash_buffer,
            max_channel_share=self._policy.max_channel_share,
        )
        self._runway_guard = RunwayFloorGuard()
        self._ranker = ScenarioRanker()
        self._comparator = ScenarioComparator()
        self._enterprise_inputs = EnterpriseScenarioInputs()
        self._downside_tree = DownsideTreeEvaluator(self._enterprise_inputs)

    @property
    def objective(self) -> str:
        return self._policy.objective

    def build_advice(
        self,
        finance_input: FinancialInput,
        forecast: ForecastSnapshot,
        runway_months: Decimal,
        scenarios: tuple[Scenario, ...],
        pre_guard_codes: tuple[str, ...],
    ) -> StrategicFinanceAdvice:
        ltv = self._ltv_builder.build(finance_input)
        cac_summary = self._cac_builder.build(finance_input)
        segmented = cac_summary['segmented_cac']
        scores = {
            channel: (ltv / cac if cac else Decimal('0'))
            for channel, cac in segmented.items()
        }
        liquidity_mode = self._liquidity_mode(runway_months, forecast)

        feasible: list[Scenario] = []
        rejection_reasons: dict[str, tuple[str, ...]] = {}
        scenario_scores: dict[str, Decimal] = {}
        evidence: list[str] = [
            f'objective={self._policy.objective}',
            f'runway_months={q2(runway_months)}',
            f'liquidity_mode={liquidity_mode}',
        ]
        for scenario in scenarios:
            reasons = self._scenario_rejections(finance_input, runway_months, scenario)
            scenario_score = self._score_scenario(finance_input, runway_months, forecast, scenario, liquidity_mode)
            scenario_scores[scenario.name] = scenario_score
            if reasons:
                rejection_reasons[scenario.name] = reasons
                continue
            feasible.append(scenario)
            evidence.append(f'candidate={scenario.name}:score={scenario_score}')

        ranked_candidates = self._ranker.rank(tuple(feasible or list(scenarios)))
        base_order = {item.name: idx for idx, item in enumerate(ranked_candidates)}
        ranked = tuple(sorted(ranked_candidates, key=lambda item: (scenario_scores[item.name], -base_order[item.name]), reverse=True))
        selected = ranked[0] if ranked else scenarios[0]
        adjusted_scores = self._apply_scenario_channel_bias(scores, selected)
        allocation_rationale = self._allocation_rationale(adjusted_scores, liquidity_mode, selected)
        allocations = self._channel_allocator.allocate(
            sum(finance_input.channel_spend.values(), start=Decimal('0')),
            adjusted_scores,
            self._constraints,
        )
        runway_guard = self._runway_guard.check(runway_months, floor=self._policy.runway_guard_floor_months)
        comparison_notes = self._comparison_notes(selected, ranked)
        evidence.extend(comparison_notes)
        evidence.extend(
            (
                f'selected={selected.name}',
                f'selected_score={scenario_scores[selected.name]}',
                f'rejected={sorted(rejection_reasons)}',
            )
        )
        return StrategicFinanceAdvice(
            selected_scenario=selected.name,
            channel_allocation=allocations,
            runway_months=runway_months,
            guard_codes=tuple((*pre_guard_codes, runway_guard.code)),
            scenario_scores=scenario_scores,
            rejection_reasons=rejection_reasons,
            evidence_trail=tuple(evidence),
            allocation_rationale=allocation_rationale,
            liquidity_mode=liquidity_mode,
        )

    def _comparison_notes(self, selected: Scenario, ranked: tuple[Scenario, ...]) -> tuple[str, ...]:
        notes: list[str] = []
        for other in ranked[1:1 + self._policy.comparison_note_limit]:
            delta = self._comparator.compare(selected, other)
            notes.append(f'selected_vs_{other.name}={delta}')
        return tuple(notes)

    def _score_scenario(
        self,
        finance_input: FinancialInput,
        runway_months: Decimal,
        forecast: ForecastSnapshot,
        scenario: Scenario,
        liquidity_mode: str,
    ) -> Decimal:
        del forecast
        unit_margin = finance_input.assumptions.get('contribution_margin_ratio', finance_input.gross_margin_rate)
        growth_delta = scenario.revenue_multiplier - scenario.cost_multiplier
        downside_weight = (
            self._policy.downside_weight_when_protected
            if liquidity_mode in {self._policy.liquidity_mode_preservation, self._policy.liquidity_mode_protection}
            else self._policy.downside_weight_balanced
        )
        capped_runway = min(runway_months, self._policy.max_scored_runway_months)
        runway_bonus = q2(capped_runway / self._policy.runway_bonus_denominator_months)
        efficiency_term = q2(unit_margin * scenario.capital_efficiency_bias)
        risk_penalty = q2(
            (scenario.cash_pressure + scenario.margin_deterioration + scenario.channel_decay + scenario.working_capital_pressure)
            * downside_weight
        )
        debt_penalty = q2(
            (finance_input.debt / (finance_input.revenue or self._policy.debt_penalty_revenue_floor))
            if finance_input.revenue > 0
            else self._policy.zero_debt_penalty
        )
        bias_signal = q2(self._enterprise_inputs.bias_signal(finance_input, scenario))
        downside_penalty = self._downside_tree.score(finance_input, scenario)
        return q2((growth_delta * scenario.probability) + efficiency_term + runway_bonus + bias_signal - risk_penalty - downside_penalty - debt_penalty - scenario.downside_risk)

    def _scenario_rejections(
        self,
        finance_input: FinancialInput,
        runway_months: Decimal,
        scenario: Scenario,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if not self._feasibility.is_feasible(finance_input, scenario):
            reasons.append('fails_cash_feasibility')
        if runway_months < self._policy.cash_pressure_rejection_runway_months and scenario.cash_pressure > self._policy.cash_pressure_rejection_threshold:
            reasons.append('cash_pressure_above_runway_tolerance')
        if runway_months < self._policy.downside_risk_rejection_runway_months and scenario.downside_risk > self._policy.downside_risk_rejection_threshold:
            reasons.append('downside_risk_above_liquidity_tolerance')
        if scenario.downside_tree and sum(scenario.downside_tree_weights.values()) > self._policy.downside_tree_rejection_weight_sum and runway_months < self._policy.downside_tree_rejection_runway_months:
            reasons.append('downside_tree_too_deep_for_current_runway')
        return tuple(reasons)

    def _liquidity_mode(self, runway_months: Decimal, forecast: ForecastSnapshot) -> str:
        policy = self._policy
        liquidity_tail = min(forecast.cashflow[-policy.liquidity_tail_window:], default=policy.liquidity_tail_default)
        if runway_months < policy.liquidity_protection_runway_months or liquidity_tail < policy.liquidity_tail_default:
            return policy.liquidity_mode_protection
        if runway_months < policy.capital_preservation_runway_months:
            return policy.liquidity_mode_preservation
        return policy.liquidity_mode_balanced

    @staticmethod
    def _apply_scenario_channel_bias(
        scores: dict[str, Decimal],
        selected: Scenario,
    ) -> dict[str, Decimal]:
        adjusted: dict[str, Decimal] = {}
        for channel, score in scores.items():
            adjusted[channel] = q2(score * selected.channel_bias.get(channel, Decimal('1')))
        return adjusted

    @staticmethod
    def _allocation_rationale(
        scores: dict[str, Decimal],
        liquidity_mode: str,
        selected: Scenario,
    ) -> tuple[str, ...]:
        top_channels = tuple(key for key, _value in sorted(scores.items(), key=lambda item: item[1], reverse=True))
        return (
            f'liquidity_mode={liquidity_mode}',
            f'selected_scenario={selected.name}',
            f'top_channels={list(top_channels)}',
            f'segment_bias={dict(selected.segment_bias)}',
            f'product_bias={dict(selected.product_bias)}',
            f'entity_bias={dict(selected.entity_bias)}',
        )
