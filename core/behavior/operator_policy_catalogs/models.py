from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class OperatorPolicyRule:
    allowed: tuple[str, ...] = field(default_factory=tuple)
    denied: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class OperatorPolicyCatalog:
    catalog_id: str
    by_stage: Mapping[str, OperatorPolicyRule] = field(default_factory=dict)
    by_role: Mapping[str, OperatorPolicyRule] = field(default_factory=dict)
    by_stage_role: Mapping[str, OperatorPolicyRule] = field(default_factory=dict)
