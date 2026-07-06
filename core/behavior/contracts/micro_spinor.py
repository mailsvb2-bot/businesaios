from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class MicroSpinor:
    spinor_id: str
    entity_id: str
    scope_type: str
    scope_ref: str
    started_at: datetime
    ended_at: datetime
    psi_re: tuple[float, float, float, float]
    psi_im: tuple[float, float, float, float]
    amplitude: tuple[float, float, float, float]
    phase: tuple[float, float, float, float]
    source_event_refs: tuple[str, ...] = field(default_factory=tuple)
    operator_trace: tuple[str, ...] = field(default_factory=tuple)
    quality_score: float = 1.0
    stability_score: float = 1.0
    context: Mapping[str, Any] = field(default_factory=dict)
