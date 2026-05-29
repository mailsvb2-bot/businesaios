from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timezone

from ..ids import EconomicsSnapshotId
from ..types import (
    BudgetEnvelope,
    CACSnapshot,
    EconomicsEvaluation,
    EconomicsReadModel,
    EconomicsSnapshot,
    LTVSnapshot,
    MarginSnapshot,
    PaybackSnapshot,
    UnitEconomics,
)
from .explanation_builder import EconomicsExplanationBuilder


@dataclass
class EconomicsSnapshotBuilder:
    explanation_builder: EconomicsExplanationBuilder = field(default_factory=EconomicsExplanationBuilder)

    def build(
        self,
        *,
        read_model: EconomicsReadModel,
        unit_economics: UnitEconomics,
        margin: MarginSnapshot,
        budget_envelope: BudgetEnvelope,
        payback: PaybackSnapshot,
        ltv: LTVSnapshot,
        cac: CACSnapshot,
        evaluation: EconomicsEvaluation,
        guard_triggers: list,
        policy_advice: dict,
        metadata: dict,
        built_at: datetime | None = None,
    ) -> EconomicsSnapshot:
        snapshot = EconomicsSnapshot(
            snapshot_id=EconomicsSnapshotId.new(),
            built_at=built_at or datetime.now(UTC),
            read_model=read_model,
            unit_economics=unit_economics,
            margin=margin,
            budget_envelope=budget_envelope,
            payback=payback,
            ltv=ltv,
            cac=cac,
            evaluation=evaluation,
            guard_triggers=list(guard_triggers),
            explanations={},
            policy_advice=dict(policy_advice),
            metadata=dict(metadata),
        )
        return replace(snapshot, explanations=self.explanation_builder.build(snapshot))
