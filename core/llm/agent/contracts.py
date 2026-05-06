from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

Json = Dict[str, Any]


@dataclass(frozen=True)
class LLMTaskContext:
    """Stable, serializable context for LLM tasks."""

    tenant_id: str
    user_id: str = ""
    product_id: str = ""
    locale: str = "ru"

    business: Json = field(default_factory=dict)
    offer: Json = field(default_factory=dict)
    audience: Json = field(default_factory=dict)
    campaign: Json = field(default_factory=dict)
    metrics: Json = field(default_factory=dict)
    constraints: Json = field(default_factory=dict)

    correlation_key: str = ""


@dataclass(frozen=True)
class LLMTaskResult:
    """Normalized task result."""

    text: str
    json: Json = field(default_factory=dict)
    meta: Json = field(default_factory=dict)
