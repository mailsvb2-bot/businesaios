from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Sequence


Json = Dict[str, Any]


@dataclass(frozen=True)
class CausalRow:
    """One row for causal estimation.

    Conventions:
    - treatment is numeric in [0,1] for binary treatments.
    - outcome is a real number.
    - covariates are a flat mapping of scalar features (numbers/booleans/strings).

    We keep covariates untyped at the boundary and let feature encoders decide.
    """

    unit_id: str
    timestamp_ms: int
    treatment: float
    outcome: float
    covariates: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CausalDataset:
    """Validated dataset for effect estimation."""

    rows: Sequence[CausalRow]

    def validate(self) -> None:
        if not isinstance(self.rows, (list, tuple)):
            raise TypeError("rows must be a sequence")
        if not self.rows:
            raise ValueError("dataset is empty")
        for r in self.rows:
            if not str(r.unit_id or "").strip():
                raise ValueError("row.unit_id is required")
            if int(r.timestamp_ms) <= 0:
                raise ValueError("row.timestamp_ms must be positive")
            t = float(r.treatment)
            if t != t:  # NaN
                raise ValueError("row.treatment is NaN")
            y = float(r.outcome)
            if y != y:
                raise ValueError("row.outcome is NaN")


@dataclass(frozen=True)
class EffectEstimate:
    """A single causal effect estimate with uncertainty."""

    estimand: str  # e.g. ATE / ATT / CATE
    effect: float
    stderr: float | None = None
    ci95_low: float | None = None
    ci95_high: float | None = None
    n: int = 0
    n_treated: int = 0
    n_control: int = 0
    method: str = ""
    notes: str = ""
    diagnostics: Json = field(default_factory=dict)


@dataclass(frozen=True)
class CausalQuery:
    """What effect we want to estimate."""

    treatment_name: str
    outcome_name: str
    covariate_names: Sequence[str] = field(default_factory=tuple)
    estimand: str = "ATE"
    method: str = "auto"  # auto | diff_in_means | stratified | ipw | dr | did

    # For time-series / Diff-in-Diff
    time_feature: str = "timestamp_ms"
    pre_period_ms: int | None = None
    post_period_ms: int | None = None


@dataclass(frozen=True)
class CausalResult:
    query: CausalQuery
    estimate: EffectEstimate
    trace: Json = field(default_factory=dict)
