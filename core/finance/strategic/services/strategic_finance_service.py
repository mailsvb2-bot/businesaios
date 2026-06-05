from __future__ import annotations

from typing import Any
from collections.abc import Callable

from core.finance.strategic.assumptions.assumption_audit_log import AssumptionAuditLog
from core.finance.strategic.builders.board_summary_builder import BoardSummaryBuilder
from core.finance.strategic.explainers.allocation_explainer import AllocationExplainer
from core.finance.strategic.explainers.liquidity_risk_explainer import LiquidityRiskExplainer
from core.finance.strategic.explainers.scenario_decision_explainer import ScenarioDecisionExplainer
from core.finance.strategic.guards.financial_input_integrity_guard import FinancialInputIntegrityGuard
from core.finance.strategic.guards.scenario_integrity_guard import ScenarioIntegrityGuard
from core.finance.strategic.projections.liquidity_projection import LiquidityProjection
from core.finance.strategic.projections.runway_projection import RunwayProjection
from core.finance.strategic.repositories.allocation_repository import AllocationRepository
from core.finance.strategic.repositories.decision_audit_repository import DecisionAuditRepository
from core.finance.strategic.repositories.forecast_repository import ForecastRepository
from core.finance.strategic.repositories.scenario_repository import ScenarioRepository
from core.finance.strategic.scenarios.scenario_catalog import ScenarioCatalog
from core.finance.strategic.services.advisory_policy import StrategicFinanceAdvisoryPolicy
from core.finance.strategic.services.rolling_forecast_service import RollingForecastService
from core.finance.strategic.services.strategic_finance_payload import build_decision_payload
from core.finance.strategic.services.strategic_finance_persistence import persist_runtime_artifacts
from core.finance.strategic.services.strategic_finance_service_support import build_artifacts, build_decision_trace
from core.finance.strategic.services.strategic_finance_types import StrategicFinanceDecision
from core.finance.strategic.types import DecisionTrace, FinancialInput


class StrategicFinanceService:
    """Strategic finance domain service.

    This service never bypasses the host platform decision ring. It only
    prepares a canonical advisory payload that the host `core.ai.decision_core`
    can merge into the single platform decision.
    """

    def __init__(
        self,
        rolling_forecast_service: RollingForecastService,
        advisory_policy: StrategicFinanceAdvisoryPolicy | None = None,
        forecast_repository: ForecastRepository | None = None,
        scenario_repository: ScenarioRepository | None = None,
        allocation_repository: AllocationRepository | None = None,
        decision_audit_repository: DecisionAuditRepository | None = None,
        board_summary_builder: BoardSummaryBuilder | None = None,
        assumption_audit_log: AssumptionAuditLog | None = None,
        event_publisher: Callable[[str, str, str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._rolling = rolling_forecast_service
        self._advisory_policy = advisory_policy or StrategicFinanceAdvisoryPolicy()
        self._scenario_catalog = ScenarioCatalog()
        self._input_guard = FinancialInputIntegrityGuard()
        self._scenario_guard = ScenarioIntegrityGuard()
        self._runway = RunwayProjection()
        self._liquidity = LiquidityProjection()
        self._forecast_repository = forecast_repository or ForecastRepository()
        self._scenario_repository = scenario_repository or ScenarioRepository()
        self._allocation_repository = allocation_repository or AllocationRepository()
        self._decision_audit_repository = decision_audit_repository or DecisionAuditRepository()
        self._board_summary_builder = board_summary_builder or BoardSummaryBuilder()
        self._assumption_audit_log = assumption_audit_log
        self._event_publisher = event_publisher
        self._scenario_explainer = ScenarioDecisionExplainer()
        self._allocation_explainer = AllocationExplainer()
        self._liquidity_explainer = LiquidityRiskExplainer()

    def evaluate(self, finance_input: FinancialInput) -> StrategicFinanceDecision:
        input_guard = self._input_guard.check(finance_input)
        if not input_guard.ok:
            raise ValueError(input_guard.message)

        forecast = self._rolling.build(finance_input)
        liquidity_path = self._liquidity.project(finance_input.cash, forecast.cashflow)
        runway_months = self._runway.project(finance_input.cash, forecast.burn_rate)

        scenarios = self._scenario_catalog.build()
        scenario_guard = self._scenario_guard.check(scenarios)
        if not scenario_guard.ok:
            raise ValueError(scenario_guard.message)

        artifacts = build_artifacts(
            finance_input=finance_input,
            forecast=forecast,
            liquidity_path=liquidity_path,
            runway_months=runway_months,
            scenarios=scenarios,
            advisory_policy=self._advisory_policy,
            scenario_explainer=self._scenario_explainer,
            allocation_explainer=self._allocation_explainer,
            liquidity_explainer=self._liquidity_explainer,
            board_summary_builder=self._board_summary_builder,
            assumption_records=(self._assumption_audit_log.records() if self._assumption_audit_log is not None else ()),
            pre_guard_codes=(input_guard.code, scenario_guard.code),
        )
        payload = build_decision_payload(
            finance_input=finance_input,
            forecast=forecast,
            advisory=artifacts.advisory,
            liquidity_path=liquidity_path,
            scenario_explanation=artifacts.scenario_explanation,
            allocation_explanation=artifacts.allocation_explanation,
            liquidity_explanation=artifacts.liquidity_explanation,
            board_summary=artifacts.board_summary,
            trace_bundle=artifacts.trace_bundle,
            assumption_records=(self._assumption_audit_log.records() if self._assumption_audit_log is not None else ()),
            objective=self._advisory_policy.objective,
        )
        self._persist_runtime_artifacts(
            finance_input,
            forecast.assumptions_version,
            artifacts.advisory,
            payload,
        )
        return StrategicFinanceDecision(
            forecast_version=forecast.assumptions_version,
            selected_scenario=artifacts.advisory.selected_scenario,
            channel_allocation=artifacts.advisory.channel_allocation,
            runway_months=artifacts.advisory.runway_months,
            guard_codes=artifacts.advisory.guard_codes,
            decision_payload=payload,
        )

    def trace(self, finance_input: FinancialInput) -> DecisionTrace:
        decision = self.evaluate(finance_input)
        return build_decision_trace(
            decision=decision,
            finance_input=finance_input,
            objective=self._advisory_policy.objective,
        )


    def _persist_runtime_artifacts(
        self,
        finance_input: FinancialInput,
        forecast_version: str,
        advisory: Any,
        payload: dict[str, Any],
    ) -> None:
        persist_runtime_artifacts(
            forecast_repository=self._forecast_repository,
            scenario_repository=self._scenario_repository,
            allocation_repository=self._allocation_repository,
            decision_audit_repository=self._decision_audit_repository,
            publish_runtime_event=self._publish_runtime_event,
            finance_input=finance_input,
            forecast_version=forecast_version,
            advisory=advisory,
            payload=payload,
        )

    def _publish_runtime_event(
        self,
        event_name: str,
        finance_input: FinancialInput,
        payload: dict[str, Any],
    ) -> None:
        if self._event_publisher is None:
            return
        self._event_publisher(
            event_name,
            finance_input.correlation_id,
            finance_input.tenant_id,
            payload,
        )


def build_strategic_finance_service(
    *,
    rolling_forecast_service: RollingForecastService,
    advisory_policy: StrategicFinanceAdvisoryPolicy | None = None,
    forecast_repository: ForecastRepository | None = None,
    scenario_repository: ScenarioRepository | None = None,
    allocation_repository: AllocationRepository | None = None,
    decision_audit_repository: DecisionAuditRepository | None = None,
    board_summary_builder: BoardSummaryBuilder | None = None,
    assumption_audit_log: AssumptionAuditLog | None = None,
    event_publisher: Callable[[str, str, str, dict[str, Any]], None] | None = None,
) -> StrategicFinanceService:
    return StrategicFinanceService(
        rolling_forecast_service=rolling_forecast_service,
        advisory_policy=advisory_policy,
        forecast_repository=forecast_repository,
        scenario_repository=scenario_repository,
        allocation_repository=allocation_repository,
        decision_audit_repository=decision_audit_repository,
        board_summary_builder=board_summary_builder,
        assumption_audit_log=assumption_audit_log,
        event_publisher=event_publisher,
    )
