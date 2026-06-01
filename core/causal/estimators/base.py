from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from core.causal.types import CausalDataset, EffectEstimate

Json = dict[str, Any]


@dataclass(frozen=True)
class EstimatorResult:
    estimate: EffectEstimate
    trace: Json


class CausalEstimator(Protocol):
    """Small interface for estimators."""

    method: str

    def estimate(self, *, dataset: CausalDataset, estimand: str = "ATE") -> EstimatorResult:  # pragma: no cover
        ...


def _counts(dataset: CausalDataset) -> tuple[int, int, int]:
    n = len(dataset.rows)
    nt = 0
    nc = 0
    for r in dataset.rows:
        if float(r.treatment) >= 0.5:
            nt += 1
        else:
            nc += 1
    return n, nt, nc
