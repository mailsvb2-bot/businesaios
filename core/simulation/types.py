from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Counterfactual:
    baseline_name: str
    candidate_name: str
