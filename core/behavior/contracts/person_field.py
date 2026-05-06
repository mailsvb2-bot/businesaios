from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.behavior.contracts.micro_spinor import MicroSpinor


@dataclass(frozen=True)
class PersonField:
    entity_id: str
    micro_spinors: tuple[MicroSpinor, ...]
    stable_observables: Mapping[str, float] = field(default_factory=dict)
    dynamic_observables: Mapping[str, float] = field(default_factory=dict)
    structural_observables: Mapping[str, float] = field(default_factory=dict)
    temporal_observables: Mapping[str, float] = field(default_factory=dict)
    market_relative_observables: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
