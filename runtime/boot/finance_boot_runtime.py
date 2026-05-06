"""Finance runtime construction. Single responsibility: build StrategicFinanceRuntime."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from runtime.finance import (
    AllocationRepository,
    AssumptionAuditLog,
    AssumptionRegistry,
    AssumptionResolver,
    BoardSummaryBuilder,
    build_economics_snapshot_adapter,
    DecisionAuditRepository,
    EconomicsSnapshotToFinancialInputAdapter,
    FinancialInput,
    ForecastAssumptions,
    ForecastRepository,
    ForecastVersioning,
    RollingForecastService,
    ScenarioRepository,
    StrategicFinanceAdvisoryPolicy,
    StrategicFinanceDecision,
    StrategicFinanceService,
    build_strategic_finance_service,
)
from runtime.finance.event_publisher import FinanceEventPublisher

CANON_BOOT_WIRING_ONLY = True


@dataclass(frozen=True)
class StrategicFinanceRuntime:
    economics_to_finance_input: EconomicsSnapshotToFinancialInputAdapter
    service: StrategicFinanceService
    advisory_policy: StrategicFinanceAdvisoryPolicy
    forecast_repository: ForecastRepository
    scenario_repository: ScenarioRepository
    allocation_repository: AllocationRepository
    decision_audit_repository: DecisionAuditRepository
    board_summary_builder: BoardSummaryBuilder
    assumption_audit_log: AssumptionAuditLog
    event_publisher: FinanceEventPublisher

    @property
    def finance_advisory_service(self) -> StrategicFinanceService:
        return self.service

    def build_financial_input(self, raw: dict) -> FinancialInput:
        return self.economics_to_finance_input.build(raw)

    def evaluate(self, raw: dict) -> StrategicFinanceDecision:
        return self.service.evaluate(self.build_financial_input(raw))

    def run_forecast(self, raw: dict) -> str:
        return self.evaluate(raw).forecast_version

    def run_scenario_evaluation(self, raw: dict) -> dict[str, Any]:
        return self.evaluate(raw).decision_payload

    def run_allocation_rebalance(self, raw: dict) -> dict[str, str]:
        decision = self.evaluate(raw)
        return {k: str(v) for k, v in decision.channel_allocation.items()}

    def __getitem__(self, key: str) -> object:
        mapping = {
            "economics_to_finance_input": self.economics_to_finance_input,
            "finance_advisory_service": self.finance_advisory_service,
            "service": self.service,
            "advisory_policy": self.advisory_policy,
            "forecast_repository": self.forecast_repository,
            "scenario_repository": self.scenario_repository,
            "allocation_repository": self.allocation_repository,
            "decision_audit_repository": self.decision_audit_repository,
            "board_summary_builder": self.board_summary_builder,
            "assumption_audit_log": self.assumption_audit_log,
            "event_publisher": self.event_publisher,
        }
        return mapping[key]


def _publish_finance_event(
    publisher: FinanceEventPublisher,
    event_name: str,
    correlation_id: str,
    tenant_id: str,
    payload: dict[str, Any],
) -> None:
    publisher.publish(event_name, correlation_id=correlation_id, tenant_id=tenant_id, payload=payload)


def _build_finance_runtime_impl() -> StrategicFinanceRuntime:
    registry = AssumptionRegistry()
    assumption_audit_log = AssumptionAuditLog()
    resolver = AssumptionResolver(registry, audit_log=assumption_audit_log)
    assumptions = ForecastAssumptions(resolver)
    versioning = ForecastVersioning()
    advisory_policy = StrategicFinanceAdvisoryPolicy()
    forecast_repository = ForecastRepository()
    scenario_repository = ScenarioRepository()
    allocation_repository = AllocationRepository()
    decision_audit_repository = DecisionAuditRepository()
    board_summary_builder = BoardSummaryBuilder()
    event_publisher = FinanceEventPublisher()
    rolling = RollingForecastService(assumptions, versioning)
    service = build_strategic_finance_service(
        rolling_forecast_service=rolling,
        advisory_policy=advisory_policy,
        forecast_repository=forecast_repository,
        scenario_repository=scenario_repository,
        allocation_repository=allocation_repository,
        decision_audit_repository=decision_audit_repository,
        board_summary_builder=board_summary_builder,
        assumption_audit_log=assumption_audit_log,
        event_publisher=lambda event_name, correlation_id, tenant_id, payload: _publish_finance_event(
            event_publisher, event_name, correlation_id, tenant_id, payload
        ),
    )
    return StrategicFinanceRuntime(
        economics_to_finance_input=build_economics_snapshot_adapter(),
        service=service,
        advisory_policy=advisory_policy,
        forecast_repository=forecast_repository,
        scenario_repository=scenario_repository,
        allocation_repository=allocation_repository,
        decision_audit_repository=decision_audit_repository,
        board_summary_builder=board_summary_builder,
        assumption_audit_log=assumption_audit_log,
        event_publisher=event_publisher,
    )


@lru_cache(maxsize=1)
def build_finance_runtime() -> StrategicFinanceRuntime:
    return _build_finance_runtime_impl()


__all__ = ["StrategicFinanceRuntime", "build_finance_runtime"]
