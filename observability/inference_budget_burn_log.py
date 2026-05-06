from __future__ import annotations

from dataclasses import dataclass
from time import time


CANON_OBSERVABILITY_INFERENCE_BUDGET_BURN_LOG = True


@dataclass(frozen=True)
class InferenceBudgetBurnEvent:
    ts: float
    tenant_id: str
    provider_name: str
    tier: str
    estimated_cost_usd: float


class InferenceBudgetBurnLog:
    def __init__(self) -> None:
        self._events: list[InferenceBudgetBurnEvent] = []

    def record(self, *, tenant_id: str, provider_name: str, tier: str, estimated_cost_usd: float) -> None:
        self._events.append(
            InferenceBudgetBurnEvent(
                ts=time(),
                tenant_id=str(tenant_id),
                provider_name=str(provider_name),
                tier=str(tier),
                estimated_cost_usd=round(float(estimated_cost_usd), 6),
            )
        )

    def list_events(self) -> tuple[InferenceBudgetBurnEvent, ...]:
        return tuple(self._events)
