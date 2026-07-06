from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuntimeAutonomyGatePolicy:
    """Typed policy surface for runtime autonomy gate normalization.

    This centralizes runtime-only defaults and payload contract keys so queue,
    executor, and tenant gate surfaces do not silently drift.
    """

    contract_presence_keys: tuple[str, ...] = (
        'autonomy_tier',
        'approval_policy',
        'constraints',
        'economy',
        'previous_feedback',
        'business_id',
    )
    estimated_cost_keys: tuple[str, ...] = ('estimated_cost', 'cost')
    max_run_cost_keys: tuple[str, ...] = ('max_run_cost',)
    default_autonomy_tier: str = 'supervised'
    zero_cost: float = 0.0


@dataclass(frozen=True)
class RuntimeAutonomyCostEnvelope:
    estimated_cost: float
    max_run_cost: float

    @property
    def exceeds_run_budget(self) -> bool:
        return self.max_run_cost > 0.0 and self.estimated_cost > self.max_run_cost


DEFAULT_RUNTIME_AUTONOMY_GATE_POLICY = RuntimeAutonomyGatePolicy()


def has_runtime_autonomy_contract(
    payload: Mapping[str, Any],
    *,
    policy: RuntimeAutonomyGatePolicy = DEFAULT_RUNTIME_AUTONOMY_GATE_POLICY,
) -> bool:
    return any(key in payload for key in policy.contract_presence_keys)



def coerce_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return float(default)



def extract_runtime_autonomy_cost_envelope(
    *,
    payload: Mapping[str, Any],
    economy: Mapping[str, Any],
    constraints: Mapping[str, Any],
    policy: RuntimeAutonomyGatePolicy = DEFAULT_RUNTIME_AUTONOMY_GATE_POLICY,
) -> RuntimeAutonomyCostEnvelope:
    estimated_cost = policy.zero_cost
    for key in policy.estimated_cost_keys:
        if key in payload:
            estimated_cost = coerce_float(payload.get(key), default=policy.zero_cost)
            break

    max_run_cost = policy.zero_cost
    for key in policy.max_run_cost_keys:
        if key in economy:
            max_run_cost = coerce_float(economy.get(key), default=policy.zero_cost)
            break
        if key in constraints:
            max_run_cost = coerce_float(constraints.get(key), default=policy.zero_cost)
            break

    return RuntimeAutonomyCostEnvelope(
        estimated_cost=estimated_cost,
        max_run_cost=max_run_cost,
    )


__all__ = [
    'DEFAULT_RUNTIME_AUTONOMY_GATE_POLICY',
    'RuntimeAutonomyCostEnvelope',
    'RuntimeAutonomyGatePolicy',
    'coerce_float',
    'extract_runtime_autonomy_cost_envelope',
    'has_runtime_autonomy_contract',
]
