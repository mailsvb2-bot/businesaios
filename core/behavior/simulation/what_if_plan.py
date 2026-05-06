from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WhatIfPlan:
    plan_id: str
    operator_keys: tuple[str, ...]
    description: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
