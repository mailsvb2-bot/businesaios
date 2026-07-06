from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from application.decisioning.candidate_collection import CandidateCollection
from application.decisioning.candidate_scores import CandidateScoreSet
from core.economics.types import (
    CashflowSignal,
    CostSignal,
    CustomerValueSignal,
    EconomicsSnapshot,
    RevenueSignal,
    SpendSignal,
    UnitEconomicsSnapshot,
)
from kernel.decisioning.decision_types import RecommendationSet


@dataclass(frozen=True)
class EconomicsContext:
    tenant_id: str
    correlation_id: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class EconomicsScoringContext:
    tenant_id: str
    correlation_id: str
    candidates: CandidateCollection


class EconomicsRecommendationBuilderPort(Protocol):
    def build(self, context: EconomicsContext) -> RecommendationSet:
        ...


class CapitalScenarioBuilderPort(Protocol):
    def build(self, context: EconomicsContext) -> RecommendationSet:
        ...


class CapitalAllocationSelectorPort(Protocol):
    def build_recommendations(self, context: EconomicsContext) -> RecommendationSet:
        ...


class RevenueReader(Protocol):
    def read(self) -> RevenueSignal:
        ...


class CostReader(Protocol):
    def read(self) -> CostSignal:
        ...


class SpendReader(Protocol):
    def read(self) -> SpendSignal:
        ...


class CustomerValueReader(Protocol):
    def read(self) -> CustomerValueSignal:
        ...


class CashflowReader(Protocol):
    def read(self) -> CashflowSignal:
        ...


class EconomicsSnapshotRepository(Protocol):
    def save(self, snapshot: EconomicsSnapshot) -> None:
        ...


class EconomicsCandidateScorer(Protocol):
    def score(self, context: EconomicsScoringContext) -> CandidateScoreSet:
        ...


__all__ = [
    "CapitalAllocationSelectorPort",
    "CapitalScenarioBuilderPort",
    "CashflowReader",
    "CostReader",
    "CustomerValueReader",
    "EconomicsCandidateScorer",
    "EconomicsContext",
    "EconomicsRecommendationBuilderPort",
    "EconomicsScoringContext",
    "EconomicsSnapshotRepository",
    "RevenueReader",
    "SpendReader",
    "UnitEconomicsSnapshot",
]
