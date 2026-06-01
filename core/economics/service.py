from __future__ import annotations

from dataclasses import dataclass, field

from application.decisioning.candidate_scores import CandidateScoreSet
from config.economics_domain_policy import DEFAULT_BUDGET_ENVELOPE_POLICY

from .builders.budget_envelope_builder import BudgetEnvelopeBuilder
from .builders.cac_builder import CACBuilder
from .builders.economics_snapshot_builder import EconomicsSnapshotBuilder
from .builders.evaluation_builder import EconomicsEvaluationBuilder
from .builders.guard_report_builder import EconomicsGuardReportBuilder
from .builders.ltv_builder import LTVBuilder
from .builders.margin_builder import MarginBuilder
from .builders.metadata_builder import EconomicsMetadataBuilder
from .builders.payback_builder import PaybackBuilder
from .builders.policy_advice_builder import EconomicsPolicyAdviceBuilder
from .builders.read_model_builder import EconomicsReadModelBuilder
from .builders.unit_economics_builder import UnitEconomicsBuilder
from .contracts import (
    CashflowReader,
    CostReader,
    CustomerValueReader,
    EconomicsCandidateScorer,
    EconomicsScoringContext,
    EconomicsSnapshotRepository,
    RevenueReader,
    SpendReader,
)
from .types import (
    BudgetEnvelope,
    CashflowSignal,
    CostSignal,
    CustomerValueSignal,
    EconomicsSnapshot,
    RevenueSignal,
    SpendSignal,
    UnitEconomicsSnapshot,
)
from .validators.signal_validator import EconomicsSignalValidator


@dataclass
class EconomicsService:
    revenue_reader: RevenueReader
    cost_reader: CostReader
    customer_value_reader: CustomerValueReader
    spend_reader: SpendReader
    cashflow_reader: CashflowReader
    repository: EconomicsSnapshotRepository
    signal_validator: EconomicsSignalValidator = field(default_factory=EconomicsSignalValidator)
    read_model_builder: EconomicsReadModelBuilder = field(default_factory=EconomicsReadModelBuilder)
    unit_economics_builder: UnitEconomicsBuilder = field(default_factory=UnitEconomicsBuilder)
    margin_builder: MarginBuilder = field(default_factory=MarginBuilder)
    budget_envelope_builder: BudgetEnvelopeBuilder = field(default_factory=BudgetEnvelopeBuilder)
    cac_builder: CACBuilder = field(default_factory=CACBuilder)
    ltv_builder: LTVBuilder = field(default_factory=LTVBuilder)
    payback_builder: PaybackBuilder = field(default_factory=PaybackBuilder)
    evaluation_builder: EconomicsEvaluationBuilder = field(default_factory=EconomicsEvaluationBuilder)
    policy_advice_builder: EconomicsPolicyAdviceBuilder = field(default_factory=EconomicsPolicyAdviceBuilder)
    metadata_builder: EconomicsMetadataBuilder = field(default_factory=EconomicsMetadataBuilder)
    guard_report_builder: EconomicsGuardReportBuilder = field(default_factory=EconomicsGuardReportBuilder)
    snapshot_builder: EconomicsSnapshotBuilder = field(default_factory=EconomicsSnapshotBuilder)
    candidate_scorer: EconomicsCandidateScorer | None = None

    def build_snapshot(self) -> EconomicsSnapshot:
        revenue = self.revenue_reader.read()
        cost = self.cost_reader.read()
        spend = self.spend_reader.read()
        customer_value = self.customer_value_reader.read()
        cashflow = self.cashflow_reader.read()
        self.signal_validator.validate(revenue=revenue, cost=cost, spend=spend, customer_value=customer_value, cashflow=cashflow)
        read_model = self.read_model_builder.build(revenue=revenue, cost=cost, spend=spend, customer_value=customer_value, cashflow=cashflow)
        unit_economics = self.unit_economics_builder.build(revenue=revenue, cost=cost, customer_value=customer_value)
        margin = self.margin_builder.build(revenue=revenue, cost=cost, spend=spend)
        budget = self.budget_envelope_builder.build(cashflow=cashflow, spend=spend, margin=margin)
        cac = self.cac_builder.build(spend=spend, customer_value=customer_value)
        ltv = self.ltv_builder.build(customer_value)
        payback = self.payback_builder.build(cac=cac, unit_economics=unit_economics)
        evaluation = self.evaluation_builder.build(budget=budget, margin=margin, ltv=ltv, cac=cac, payback=payback)
        policy_advice = self.policy_advice_builder.build(budget)
        metadata = self.metadata_builder.build()
        guards = self.guard_report_builder.build(read_model=read_model, margin=margin, spend=spend, budget=budget, cashflow=cashflow, policy_advice=policy_advice)
        snapshot = self.snapshot_builder.build(
            read_model=read_model,
            unit_economics=unit_economics,
            margin=margin,
            budget_envelope=budget,
            payback=payback,
            ltv=ltv,
            cac=cac,
            evaluation=evaluation,
            guard_triggers=guards,
            policy_advice=policy_advice,
            metadata=metadata,
        )
        self.repository.save(snapshot)
        return snapshot

    def score_candidates(self, context: EconomicsScoringContext) -> CandidateScoreSet:
        if self.candidate_scorer is None:
            raise RuntimeError("Economics candidate scorer is not configured")
        return self.candidate_scorer.score(context)


def build_budget_envelope(snapshot: UnitEconomicsSnapshot) -> BudgetEnvelope:
    policy = DEFAULT_BUDGET_ENVELOPE_POLICY
    max_spend = policy.zero_budget if snapshot.margin <= 0 else float(snapshot.margin)
    if max_spend <= policy.zero_budget:
        pressure = policy.extreme_pressure
    elif snapshot.margin < snapshot.cac:
        pressure = policy.high_pressure
    elif snapshot.ltv < snapshot.cac * policy.ltv_cac_medium_ratio:
        pressure = policy.medium_pressure
    else:
        pressure = policy.low_pressure
    from .enums import BudgetPressureLevel
    return BudgetEnvelope(
        available_growth_budget=max_spend,
        protected_cash_reserve=policy.zero_reserve,
        recommended_spend_cap=max_spend,
        pressure_level=BudgetPressureLevel(pressure),
    )
