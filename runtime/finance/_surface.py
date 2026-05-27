from __future__ import annotations

"""Canonical runtime finance boundary surface."""

from core.finance.builders.cashflow_builder import build_cashflow_snapshot
from core.finance.contracts import FinanceSnapshot
from core.finance.explainers.cashflow_explainer import explain_cashflow
from core.finance.strategic.adapters.economics_snapshot_adapter import (
    EconomicsSnapshotToFinancialInputAdapter,
    build_economics_snapshot_adapter,
)
from core.finance.strategic.assumptions.assumption_audit_log import AssumptionAuditLog
from core.finance.strategic.assumptions.assumption_registry import AssumptionRegistry
from core.finance.strategic.assumptions.assumption_resolver import AssumptionResolver
from core.finance.strategic.builders.board_summary_builder import BoardSummaryBuilder
from core.finance.strategic.events.allocation_recommended import AllocationRecommended
from core.finance.strategic.events.forecast_revised import ForecastRevised
from core.finance.strategic.events.scenario_selected import ScenarioSelected
from core.finance.strategic.forecasting.forecast_assumptions import ForecastAssumptions
from core.finance.strategic.forecasting.forecast_versioning import ForecastVersioning
from core.finance.strategic.repositories.allocation_repository import AllocationRepository
from core.finance.strategic.repositories.decision_audit_repository import DecisionAuditRepository
from core.finance.strategic.repositories.forecast_repository import ForecastRepository
from core.finance.strategic.repositories.scenario_repository import ScenarioRepository
from core.finance.strategic.services.advisory_policy import StrategicFinanceAdvisoryPolicy
from core.finance.strategic.services.rolling_forecast_service import RollingForecastService
from core.finance.strategic.services.strategic_finance_service import (
    StrategicFinanceDecision,
    StrategicFinanceService,
    build_strategic_finance_service,
)
from core.finance.strategic.types import FinancialInput
from runtime.finance.event_publisher import FinanceEventPublisher, PublishedFinanceEvent
from runtime.finance.job_orchestrator import FinanceJobOrchestrator, FinanceJobRunRecord
from runtime.finance.job_spec import FinanceJobSpec

CANON_RUNTIME_FINANCE_PUBLIC_API = True

__all__ = [
    'CANON_RUNTIME_FINANCE_NAMESPACE',
    "AllocationRecommended",
    "AllocationRepository",
    "AssumptionAuditLog",
    "AssumptionRegistry",
    "AssumptionResolver",
    "BoardSummaryBuilder",
    "build_cashflow_snapshot",
    "build_economics_snapshot_adapter",
    "build_strategic_finance_service",
    "CANON_RUNTIME_FINANCE_PUBLIC_API",
    "DecisionAuditRepository",
    "EconomicsSnapshotToFinancialInputAdapter",
    "explain_cashflow",
    "FinanceEventPublisher",
    "FinanceJobOrchestrator",
    "FinanceJobRunRecord",
    "FinanceJobSpec",
    "FinanceSnapshot",
    "FinancialInput",
    "ForecastAssumptions",
    "ForecastRepository",
    "ForecastRevised",
    "ForecastVersioning",
    "PublishedFinanceEvent",
    "RollingForecastService",
    "ScenarioRepository",
    "ScenarioSelected",
    "StrategicFinanceAdvisoryPolicy",
    "StrategicFinanceDecision",
    "StrategicFinanceService",
]

CANON_RUNTIME_FINANCE_NAMESPACE = True


