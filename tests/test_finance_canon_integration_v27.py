
from __future__ import annotations

from datetime import UTC, datetime

from core.economics.enums import BudgetPressureLevel, EconomicsSignalStatus, GuardSeverity, MarginHealthStatus, PaybackRiskLevel
from core.economics.guard import GuardTrigger
from core.economics.ids import EconomicsSnapshotId
from core.economics.types import (
    BudgetEnvelope,
    CACSnapshot,
    CashflowSignal,
    CostSignal,
    CustomerValueSignal,
    EconomicsEvaluation,
    EconomicsReadModel,
    EconomicsSnapshot,
    LTVSnapshot,
    MarginSnapshot,
    PaybackSnapshot,
    RevenueSignal,
    SpendSignal,
    UnitEconomics,
)
from core.finance.builders.cashflow_builder import build_cashflow_snapshot
from core.finance.explainers.cashflow_explainer import explain_cashflow
from core.finance.strategic.adapters.economics_snapshot_adapter import EconomicsSnapshotToFinancialInputAdapter
from runtime.boot.finance_boot import build_finance_runtime


def _snapshot() -> EconomicsSnapshot:
    return EconomicsSnapshot(
        snapshot_id=EconomicsSnapshotId('econ_1'),
        built_at=datetime.now(UTC),
        read_model=EconomicsReadModel(
            revenue=RevenueSignal(period_days=30, gross_revenue=1200.0, net_revenue=1000.0, orders=10),
            cost=CostSignal(period_days=30, cogs=200.0, fixed_costs=100.0, variable_costs=150.0),
            spend=SpendSignal(period_days=30, marketing_spend=120.0, sales_spend=80.0, operations_spend=50.0),
            customer_value=CustomerValueSignal(
                active_customers=50,
                new_customers=10,
                returning_customers=40,
                average_order_value=100.0,
                purchase_frequency_30d=1.2,
                gross_retention_30d=0.9,
                contribution_margin_ratio=0.4,
            ),
            cashflow=CashflowSignal(cash_in=1100.0, cash_out=700.0, runway_days=90, unrestricted_cash=500.0),
        ),
        unit_economics=UnitEconomics(
            gross_profit=400.0,
            contribution_profit=250.0,
            contribution_margin_ratio=0.4,
            revenue_per_customer=20.0,
            contribution_per_customer_period=5.0,
            contribution_per_customer_day=0.16,
            variable_cost_ratio=0.2,
            period_days=30,
        ),
        margin=MarginSnapshot(gross_margin_ratio=0.5, net_margin_ratio=0.2, status=MarginHealthStatus.STRONG),
        budget_envelope=BudgetEnvelope(available_growth_budget=100.0, protected_cash_reserve=200.0, recommended_spend_cap=80.0, pressure_level=BudgetPressureLevel.LOW),
        payback=PaybackSnapshot(cac_payback_days=30.0, risk_level=PaybackRiskLevel.LOW),
        ltv=LTVSnapshot(ltv=200.0),
        cac=CACSnapshot(blended_cac=20.0, attributed_new_customers=10),
        evaluation=EconomicsEvaluation(
            budget_pressure_status=EconomicsSignalStatus.HEALTHY,
            margin_health_status=EconomicsSignalStatus.HEALTHY,
            ltv_cac_status=EconomicsSignalStatus.HEALTHY,
            payback_risk_status=EconomicsSignalStatus.HEALTHY,
            scores={'health': 1.0},
        ),
        guard_triggers=[GuardTrigger(code='ok', severity=GuardSeverity.INFO, message='ok')],
        metadata={'tenant_id': 'tenant-1'},
    )


def test_finance_builder_and_explainer_are_consistent() -> None:
    snapshot = build_cashflow_snapshot('tenant-1', revenue=100.0, expenses=25.0)
    text = explain_cashflow(snapshot)
    assert 'revenue=100.0' in text
    assert 'cashflow=75.0' in text


def test_finance_runtime_uses_economics_snapshot_as_single_input_flow() -> None:
    econ = _snapshot()
    adapter = EconomicsSnapshotToFinancialInputAdapter()
    finance_input = adapter.build(econ)
    runtime = build_finance_runtime()
    decision = runtime['finance_advisory_service'].evaluate(finance_input)
    assert decision.decision_payload['advisory_only'] is True
    assert 'core.ai.decision_core' in decision.decision_payload['source']
    assert finance_input.metadata['source'] == 'core.economics.snapshot'
