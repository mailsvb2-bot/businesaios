from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping


@dataclass(frozen=True)
class OperatorRuntimeContext:
    tenant_id: str | None = None
    product: str | None = None
    env: str | None = None
    domain: str | None = None
    channel: str | None = None
    funnel_stage: str | None = None
    actor_role: str | None = None
    safe_mode: bool = False
    operator_catalog_ref: str = "default"
    operator_policy_catalog_ref: str | None = None
    operator_overrides: Mapping[str, tuple[float, float, float, float]] = field(default_factory=dict)
